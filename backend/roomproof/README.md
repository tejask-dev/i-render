# RoomProof provider service

Separate FastAPI app for the paired iPhone. It implements the HTTP API in `contracts/roomproof/README.md` and does not touch the workbench app.

## Run

Double-click `Start RoomProof.command`, or run it from Terminal. First launch creates
`.var/roomproof-config.json` with an unpredictable pairing token and empty provider keys.
This ignored, owner-readable file stays on the Mac. Set the keys there without sharing the
file. Set `ROOMPROOF_HOST` to the Mac's private-hotspot IP to enable phone access; it starts
on loopback only. Copy only the pairing token into the app's Connect to Mac screen.
Restart the launcher after changing these settings. Do not use public Wi-Fi for local HTTP.

Alternatively, use environment variables:

From the repository root, with the project environment:

```sh
export ROOMPROOF_PAIR_TOKEN=...   # required; the service refuses to start without it
export GEMINI_API_KEY=...         # optional GEMINI_MODEL, default gemini-3.5-flash-lite
export TINYFISH_API_KEY=...
export ROOMPROOF_HOST=...         # the Mac's private-hotspot address; default 127.0.0.1 (this Mac only)
.venv/bin/python -m backend.roomproof          # port 8767, or ROOMPROOF_PORT
```

The ASGI app is `backend.roomproof.app:app`. Credentials are read from the environment only and are never logged or returned.

## Check

```sh
.venv/bin/python -m eval.check_roomproof
```

All provider traffic in that check is mocked. It is not evidence of a live Gemini or TinyFish call.

## Behaviour the phone can rely on

- Every route needs `Authorization: Bearer <ROOMPROOF_PAIR_TOKEN>`. Without a configured token every request gets 503 `pairing_not_configured`; a wrong or missing token gets 401 `unauthorized`.
- Every error is `{code, message, retryable}`. Codes: `unauthorized`, `pairing_not_configured`, `invalid_request` (422), `payload_too_large` and `image_too_large` (413), `invalid_image` (400), `busy` (429), `gemini_not_configured`, `gemini_rejected`, `gemini_unavailable`, `gemini_timeout` (504), `gemini_invalid_output` (502), `tinyfish_not_configured`, `request_conflict` (409), `unknown_job` (404), `not_found`, `method_not_allowed`, `internal_error`.
- `/analyze` returns a storage preference, style, questions and a qualitative summary. Gemini receives the user's description, style and storage preferences, notes, retained-item label and optional photo. The native app owns structured budgets and room geometry. The server rejects malformed, unfinished or oversized replies, links, numeric figures, currency and measurement amounts. Qualitative phrases such as “budget-friendly” and “half-open storage” are accepted.
- `/sourcing` checks four pinned pages, with two simultaneous requests across all jobs and a 90-second deadline per attempt. A page gets one retry if the connection could not be established or the provider explicitly rejected the request with HTTP 429. A timeout after submission, a broken stream or a server error ends that page's check. This avoids starting another billable run when the first may have been accepted. The service holds up to four active jobs and purges completed jobs after 30 minutes.
- Job `state`: `queued`, `running` (verified offers appear as they complete), then `done` (four offers), `partial` (one to three) or `failed` (none). `errors` has one fixed-wording line per product that produced no offer. `progress` notes any field left empty.
- An offer is emitted only when the run completed and the page matched the catalog product by name and by article number or page address. It always has `provenance: "live"` and the completion time in `checkedAt`. Identity fields, `closedStorage` and `url` come from the catalog.
- A price needs a single quoted unit price with a currency marker. A plain dollar sign also needs CAD in the extracted currency field. A foreign or ambiguous price leaves `priceCents` null.
- Each dimension needs its own axis label and unit in the quote. An explicitly labeled width × depth × height triple may share a trailing metric unit. Missing or contradictory values leave that axis null. The service sets `dimensionConflict` when the extract reports a conflict or a labeled axis has inconsistent values.
- Verified stock needs a quoted availability statement for the requested locality or an explicitly online status. A contradictory, ambiguous or unscoped statement yields `unknown`.

## Not yet verified against the live providers

Only the request shape and the terminal `COMPLETE` / `COMPLETED` / `result` event come from the contract. The field names requested in `output_schema`, the events before the terminal one, and Gemini's acceptance of the response schema are untested until the coordinator's live gate. An unrecognised result shape surfaces as "the browser run returned no usable result".
