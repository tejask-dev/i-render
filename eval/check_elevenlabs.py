"""Exercise optional narration using an in-process workbench and a fully mocked provider."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, patch

import httpx

from backend import main, speech


async def check():
    key, voice = "mock-only-key", "mock_voice-1"
    audio = b"ID3" + b"mock audio"
    upstream = httpx.MockTransport(lambda _: httpx.Response(503))
    real_client = httpx.AsyncClient

    def provider_client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return real_client(transport=upstream, **kwargs)

    async with real_client(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver") as browser:
        async def speak(text="Read this.", **kwargs):
            response = await browser.post("/api/speak", json={"text": text}, **kwargs)
            assert key not in response.text and "private upstream message" not in response.text
            return response

        async def available():
            config = await browser.get("/api/config")
            assert key not in config.text and voice not in config.text
            return config.raise_for_status().json()["elevenlabs_voice_available"]

        with (patch.dict(os.environ, {"ELEVENLABS_API_KEY": "", "ELEVENLABS_VOICE_ID": "", "ELEVENLABS_MODEL": ""}),
              patch.object(main.vision, "vision_source", AsyncMock(return_value=None)),
              patch.object(speech.httpx, "AsyncClient", side_effect=provider_client) as provider):
            assert not await available() and (await speak()).status_code == 503
            os.environ.update(ELEVENLABS_API_KEY=key, ELEVENLABS_VOICE_ID="../bad/voice")
            assert not await available() and (await speak()).status_code == 503
            os.environ["ELEVENLABS_VOICE_ID"] = voice
            assert await available()
            for invalid in ("", "  \t", "x" * 1201, " " * 1200 + "x"):
                assert (await speak(invalid)).status_code == 422
            assert (await speak(headers={"Origin": "https://elsewhere.example"})).status_code == 403
            provider.assert_not_called()

            requests = []

            def recorded(request):
                requests.append(request)
                return httpx.Response(200, headers={"Content-Type": "audio/mpeg"}, stream=httpx.ByteStream(audio))

            upstream = httpx.MockTransport(recorded)
            for configured, expected in (("", "eleven_multilingual_v2"), ("mock_model", "mock_model")):
                os.environ["ELEVENLABS_MODEL"] = configured
                text = "x" * 1200
                result = await speak(text)
                assert result.status_code == 200 and result.content == audio
                assert result.headers["content-type"] == "audio/mpeg" and result.headers["cache-control"] == "no-store"
                req = requests[-1]
                assert req.method == "POST" and str(req.url) == (
                    f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128")
                assert req.headers["xi-api-key"] == key and json.loads(req.content) == {"text": text, "model_id": expected}

            for status, mime, body, expected in (
                (200, "application/json", b"private upstream message", 502),
                (200, "audio/mpeg", b"", 502),
                (200, "audio/mpeg", b"x" * (speech.MAX_MP3_BYTES + 1), 502),
                (401, "text/plain", b"private upstream message", 502),
                (302, "text/plain", b"private upstream message", 502),
                (429, "text/plain", b"private upstream message", 429),
            ):
                upstream = httpx.MockTransport(lambda _: httpx.Response(status, headers={"content-type": mime},
                                                                        stream=httpx.ByteStream(body)))
                assert (await speak()).status_code == expected

            def unreachable(request):
                raise httpx.ConnectError("private upstream message", request=request)

            upstream = httpx.MockTransport(unreachable)
            assert (await speak()).status_code == 502
            started, release = asyncio.Event(), asyncio.Event()

            async def delayed(request):
                started.set()
                await release.wait()
                return recorded(request)

            upstream = httpx.MockTransport(delayed)
            first = asyncio.create_task(speak())
            try:
                await asyncio.wait_for(started.wait(), 2)
                assert (await asyncio.wait_for(speak(), 1)).status_code == 429
            finally:
                release.set()
            assert (await first).status_code == 200
            release.clear()
            with patch.object(speech, "NARRATION_TIMEOUT", 0.02):
                assert (await speak()).status_code == 504
            release.set()
            assert (await speak()).status_code == 200


if __name__ == "__main__":
    asyncio.run(check())
    print("PASS mocked ElevenLabs configuration, request and MP3 response, size/type limits, origin, concurrency and timeout")
