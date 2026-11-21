"""A successful Whisper process can leave no transcript for a silent recording."""

import asyncio
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from backend import speech


async def main():
    with patch.object(speech, "available", return_value=True), patch.object(speech, "run", new=AsyncMock()):
        try:
            await speech.transcribe(b"OggS")
        except HTTPException as error:
            assert error.status_code == 422 and "type" in error.detail
        else:
            raise AssertionError("missing transcript accepted")
    print("Missing Whisper transcript returns a recoverable typed-answer response.")


if __name__ == "__main__":
    asyncio.run(main())
