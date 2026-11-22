"""In-memory sourcing jobs: deduplicated by request, bounded in number, age and concurrency."""

import asyncio
import secrets
import time
from dataclasses import dataclass, field

from . import tinyfish
from .catalog import CATALOG
from .errors import ApiError

RETENTION = 30 * 60
CONCURRENCY = 2
MAX_ACTIVE = 4
MAX_JOBS = 32
MAX_PROGRESS = 40


@dataclass
class Job:
    id: str
    request_id: str
    revision: int
    store_location: str
    state: str = "queued"
    progress: list = field(default_factory=list)
    offers: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    run_ids: list = field(default_factory=list)  # kept for local diagnosis only, never serialised
    finished: float | None = None
    task: asyncio.Task | None = None

    def note(self, line):
        if len(self.progress) < MAX_PROGRESS:
            self.progress.append(line)

    def view(self):
        return {
            "contractVersion": 1, "jobId": self.id, "requestId": self.request_id, "revision": self.revision,
            "state": self.state, "progress": list(self.progress),
            "offers": [self.offers[e["id"]] for e in CATALOG if e["id"] in self.offers],
            "errors": list(self.errors),
        }


class JobManager:
    def __init__(self, *, transport=None, clock=time.monotonic, attempt_timeout=tinyfish.ATTEMPT_TIMEOUT):
        self.transport = transport
        self.clock = clock
        self.attempt_timeout = attempt_timeout
        self.jobs = {}
        self.by_request = {}
        self.slots = asyncio.Semaphore(CONCURRENCY)

    def _drop(self, job):
        self.jobs.pop(job.id, None)
        self.by_request.pop(job.request_id, None)

    def purge(self):
        now = self.clock()
        for job in [j for j in self.jobs.values() if j.finished is not None and now - j.finished >= RETENTION]:
            self._drop(job)

    def submit(self, request_id, revision, store_location):
        """Start a job, or return the one already started by the same request. Runs no awaits, so it is atomic."""
        self.purge()
        existing = self.by_request.get(request_id)
        if existing is not None:
            if (existing.revision, existing.store_location) == (revision, store_location):
                return existing
            raise ApiError(409, "request_conflict",
                           "This request ID was already used with different details. Start a new refresh.")
        key = tinyfish.configured_key()
        if not key:
            raise ApiError(503, "tinyfish_not_configured", "TINYFISH_API_KEY is not set on the Mac running RoomProof.")
        if sum(job.finished is None for job in self.jobs.values()) >= MAX_ACTIVE:
            raise ApiError(429, "busy", "Earlier retailer checks are still running. Try again shortly.", True)
        while len(self.jobs) >= MAX_JOBS:
            self._drop(min((j for j in self.jobs.values() if j.finished is not None), key=lambda j: j.finished))
        job = Job(secrets.token_hex(16), request_id, revision, store_location)
        job.note(f"Queued {len(CATALOG)} catalog checks.")
        self.jobs[job.id] = self.by_request[request_id] = job
        job.task = asyncio.create_task(self._run(job, key))
        return job

    def get(self, job_id):
        self.purge()
        job = self.jobs.get(job_id)
        if job is None:
            raise ApiError(404, "unknown_job", "This retailer check is no longer held on the Mac. Refresh to start a new one.")
        return job

    async def close(self):
        tasks = [job.task for job in self.jobs.values() if job.task is not None and not job.task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, job, key):
        try:
            await asyncio.gather(*(self._check(job, entry, key) for entry in CATALOG))
        except asyncio.CancelledError:
            job.errors.append("Sourcing was stopped before it finished.")
            raise
        finally:
            found = len(job.offers)
            job.state = "done" if found == len(CATALOG) else "partial" if found else "failed"
            job.finished = self.clock()

    async def _check(self, job, entry, key):
        label = f"{entry['retailer']} {entry['name']}"
        async with self.slots:
            if job.state == "queued":
                job.state = "running"
            job.note(f"{label}: checking the retailer page.")
            for attempt in (1, 2):
                try:
                    extract = await tinyfish.run(key, entry["url"], tinyfish.goal_for(entry, job.store_location),
                                                 transport=self.transport, timeout=self.attempt_timeout)
                    if extract.run_id:
                        job.run_ids.append(extract.run_id)
                    # Live provenance and the check time exist only because this extract actually completed.
                    offer, notes = tinyfish.build_offer(entry, extract.result, job.store_location, extract.completed_at)
                except tinyfish.TinyFishError as error:
                    if error.run_id:
                        job.run_ids.append(error.run_id)
                    if error.safe_to_retry and attempt == 1:
                        job.note(f"{label}: retrying once after the request could not start.")
                        continue
                    job.errors.append(f"{label}: {tinyfish.MESSAGES[error.kind]}")
                    return
                except Exception:
                    job.errors.append(f"{label}: the check stopped unexpectedly.")
                    return
                job.offers[entry["id"]] = offer
                job.note(f"{label}: checked" + (f"; {', '.join(notes)}." if notes else "."))
                return
