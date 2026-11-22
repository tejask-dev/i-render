"""RoomProof provider service: a FastAPI app for the paired iPhone, separate from the workbench app.

Run with `python -m backend.roomproof` (port 8767). Every route needs the pairing bearer token.
"""

import base64
import binascii
import hmac
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from ..vision import VisionError, read_image
from . import gemini, tinyfish
from .errors import ApiError
from .jobs import JobManager

CONTRACT_VERSION = 1
MAX_TEXT = 4000
MAX_IMAGE = 10 * 1024 * 1024
MAX_IMAGE_BASE64 = (MAX_IMAGE + 2) // 3 * 4
ANALYZE_BODY = MAX_IMAGE_BASE64 + 64 * 1024
SOURCING_BODY = 16 * 1024
MAX_ANALYSES = 2
log = logging.getLogger("roomproof")


class Wire(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)


MM = Annotated[int, Field(ge=-1_000_000, le=1_000_000)]
Label = Annotated[str, Field(max_length=200)]
RequestID = Annotated[str, Field(pattern=r"^[A-Za-z0-9._:-]{1,100}$")]
Revision = Annotated[int, Field(ge=0, le=2**53)]


class RectMM(Wire):
    xMM: MM
    zMM: MM
    widthMM: MM
    depthMM: MM


class KeptItem(Wire):
    id: Label
    label: Label
    widthMM: MM
    depthMM: MM
    heightMM: MM
    centerXMM: MM
    centerZMM: MM
    quarterTurns: MM


class RoomSpec(Wire):
    widthMM: MM
    depthMM: MM
    heightMM: MM
    doorReserve: RectMM
    kept: KeptItem
    source: Label
    confirmed: bool
    otherObjectsCleared: bool


class DesignBrief(Wire):
    budgetCents: Annotated[int, Field(ge=0, le=1_000_000_000)]
    preferClosedStorage: bool
    style: Annotated[str, Field(max_length=400)]
    chairPullbackMM: MM
    notes: Annotated[str, Field(max_length=MAX_TEXT)]


class AnalyzeRequest(Wire):
    requestId: RequestID
    revision: Revision
    text: Annotated[str, Field(max_length=MAX_TEXT)]
    room: RoomSpec
    brief: DesignBrief
    imageBase64: Annotated[str, Field(max_length=MAX_IMAGE_BASE64)] | None = None


class SourcingRequest(Wire):
    requestId: RequestID
    revision: Revision
    storeLocation: str

    @field_validator("storeLocation")
    @classmethod
    def plain_place(cls, value):
        # The place name is quoted inside a browser-agent goal, so it stays a plain name.
        value = " ".join(value.split())
        if not 1 <= len(value) <= 80 or not all(ch.isalnum() or ch in " ,.'’-()" for ch in value):
            raise ValueError("use a plain city or store name of at most 80 characters")
        return value


def _problem(error):
    return JSONResponse(error.body(), status_code=error.status_code)


class PairingGate:
    """Refuses every request without the pairing token, before any body is read. No token configured: refuse all."""

    def __init__(self, app, token):
        self.app = app
        self.token = token.encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        if scope["type"] != "http":
            return await send({"type": "websocket.close", "code": 1008})
        if not self.token:
            error = ApiError(503, "pairing_not_configured",
                             "ROOMPROOF_PAIR_TOKEN is not set on the Mac. Restart RoomProof with a pairing token.")
            return await _problem(error)(scope, receive, send)
        scheme, _, supplied = dict(scope["headers"]).get(b"authorization", b"").partition(b" ")
        if scheme.lower() != b"bearer" or not hmac.compare_digest(supplied.strip(), self.token):
            response = _problem(ApiError(401, "unauthorized", "Pair this iPhone with the Mac's RoomProof token."))
            response.headers["WWW-Authenticate"] = "Bearer"
            return await response(scope, receive, send)

        async def private(message):
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), (b"cache-control", b"no-store")]
            await send(message)
        await self.app(scope, receive, private)


async def read_json(request, limit, model):
    too_large = ApiError(413, "payload_too_large", "The request is too large. Choose a photo under 10 MB.")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise too_large
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise too_large
    try:
        return model.model_validate_json(bytes(body))
    except ValidationError as exc:
        # Field paths and rule text only: the rejected input is never echoed back.
        details = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'body'}: {e['msg']}" for e in exc.errors()[:3])
        raise ApiError(422, "invalid_request", f"The request does not match the RoomProof contract ({details}).") from exc


def decode_photo(encoded):
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApiError(400, "invalid_image", "The photo was not sent as valid base64.") from exc
    if len(data) > MAX_IMAGE:
        raise ApiError(413, "image_too_large", "Choose a photo under 10 MB.")
    try:
        return read_image(data)
    except VisionError as exc:
        raise ApiError(exc.status_code, "image_too_large" if exc.status_code == 413 else "invalid_image", str(exc)) from exc


def create_app(*, transport=None, clock=time.monotonic, gemini_deadline=gemini.DEADLINE,
               attempt_timeout=tinyfish.ATTEMPT_TIMEOUT):
    """`transport` replaces the provider network in tests; production leaves it unset."""
    jobs = JobManager(transport=transport, clock=clock, attempt_timeout=attempt_timeout)
    analyses = 0

    @asynccontextmanager
    async def lifespan(app):
        yield
        await jobs.close()

    app = FastAPI(title="RoomProof", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.jobs = jobs
    app.add_middleware(PairingGate, token=os.environ.get("ROOMPROOF_PAIR_TOKEN", "").strip())

    @app.exception_handler(ApiError)
    async def api_error(request, exc):
        return _problem(exc)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        if exc.status_code == 404:
            return _problem(ApiError(404, "not_found", "RoomProof has no such endpoint."))
        if exc.status_code == 405:
            return _problem(ApiError(405, "method_not_allowed", "RoomProof does not accept this method here."))
        return _problem(ApiError(exc.status_code, "request_failed", "RoomProof could not handle this request."))

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        log.error("Unhandled %s on %s", type(exc).__name__, request.url.path)
        return _problem(ApiError(500, "internal_error", "RoomProof hit an unexpected problem. Try again.", True))

    @app.get("/api/roomproof/health")
    async def health():
        # Says only whether keys are present; it does not call either provider.
        return {"contractVersion": CONTRACT_VERSION, "geminiConfigured": bool(gemini.configured_key()),
                "tinyfishConfigured": bool(tinyfish.configured_key())}

    @app.post("/api/roomproof/analyze")
    async def analyze(request: Request):
        nonlocal analyses
        if analyses >= MAX_ANALYSES:
            raise ApiError(429, "busy", "Another analysis is still running. Try again shortly.", True)
        analyses += 1
        try:
            body = await read_json(request, ANALYZE_BODY, AnalyzeRequest)
            gemini.require_configuration()
            image = None
            if body.imageBase64 is not None:
                image = await run_in_threadpool(decode_photo, body.imageBase64)
            if not body.text.strip() and image is None:
                raise ApiError(422, "invalid_request", "Describe the workspace or attach a photo.")
            answer = await gemini.analyze(body.text, body.room.model_dump(), body.brief.model_dump(), image,
                                          transport=transport, deadline=gemini_deadline)
        finally:
            analyses -= 1
        # Only preferences come back. The room, budget and confirmation flags stay as the phone holds them.
        return {"contractVersion": CONTRACT_VERSION, "requestId": body.requestId, "revision": body.revision,
                "preferClosedStorage": answer["preferClosedStorage"], "style": answer["style"],
                "questions": answer["questions"], "summary": answer["summary"],
                "provider": "gemini", "model": answer["model"]}

    @app.post("/api/roomproof/sourcing")
    async def sourcing(request: Request):
        body = await read_json(request, SOURCING_BODY, SourcingRequest)
        job = jobs.submit(body.requestId, body.revision, body.storeLocation)
        return JSONResponse({"jobId": job.id, "requestId": job.request_id, "revision": job.revision}, status_code=202)

    @app.get("/api/roomproof/jobs/{job_id}")
    async def job_status(job_id: str):
        return jobs.get(job_id).view()

    return app


app = create_app()
