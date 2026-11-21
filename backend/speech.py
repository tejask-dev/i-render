"""Short local dictation and opt-in ElevenLabs narration."""

import asyncio
import os
import re
import shutil
import tempfile
from pathlib import Path

import httpx
from fastapi import HTTPException

MODEL = Path.home() / ".cache" / "whisper" / "base.en.pt"
GATE = asyncio.Semaphore(1)
NARRATION_GATE = asyncio.Lock()
MAX_MP3_BYTES = 2 * 1024 * 1024
NARRATION_TIMEOUT = 20


def available():
    return bool(MODEL.is_file() and shutil.which("whisper") and shutil.which("ffmpeg"))


def elevenlabs_settings():
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    if not re.fullmatch(r"[!-~]+", key) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", voice):
        return None
    model = os.environ.get("ELEVENLABS_MODEL", "").strip() or "eleven_multilingual_v2"
    return key, voice, model


async def synthesize(text):
    settings = elevenlabs_settings()
    if settings is None:
        raise HTTPException(503, "ElevenLabs voice is unavailable. Choose the Mac voice.")
    if NARRATION_GATE.locked():
        raise HTTPException(429, "Another narration is in progress. Try again in a moment.")
    key, voice, model = settings
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    headers = {"xi-api-key": key, "Accept": "audio/mpeg", "Accept-Encoding": "identity"}
    try:
        async with NARRATION_GATE, asyncio.timeout(NARRATION_TIMEOUT), httpx.AsyncClient(
            timeout=NARRATION_TIMEOUT, trust_env=False, follow_redirects=False
        ) as client:
            async with client.stream("POST", url, params={"output_format": "mp3_44100_128"},
                                     headers=headers, json={"text": text, "model_id": model}) as response:
                if response.status_code == 429:
                    raise HTTPException(429, "ElevenLabs is busy. Try again later or choose the Mac voice.")
                if response.status_code != 200:
                    raise HTTPException(502, "ElevenLabs could not generate narration. Choose the Mac voice or retry.")
                mime = response.headers.get("content-type", "").partition(";")[0].strip().lower()
                if mime != "audio/mpeg" or response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise HTTPException(502, "ElevenLabs returned an unexpected audio format.")
                audio = bytearray()
                async for chunk in response.aiter_raw():
                    if len(audio) + len(chunk) > MAX_MP3_BYTES:
                        raise HTTPException(502, "The generated narration was too large.")
                    audio.extend(chunk)
                if not audio:
                    raise HTTPException(502, "ElevenLabs returned empty audio.")
                return bytes(audio)
    except (TimeoutError, httpx.TimeoutException):
        raise HTTPException(504, "Narration timed out. Choose the Mac voice or retry.") from None
    except httpx.RequestError:
        raise HTTPException(502, "Could not reach ElevenLabs. Choose the Mac voice or retry.") from None


async def run(*command, data=None, timeout=30):
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE if data else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(process.communicate(data), timeout)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise HTTPException(
            422, "Could not hear this recording. Try again or type your answer."
        )


async def transcribe(data):
    if not available():
        raise HTTPException(503, "Local dictation is unavailable. Type your answer.")
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Keep your answer under 12 seconds.")
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        fmt = "matroska"
    elif data.startswith(b"OggS"):
        fmt = "ogg"
    elif data[4:8] == b"ftyp":
        fmt = "mov"
    else:
        raise HTTPException(415, "Use your browser’s record button.")
    if GATE.locked():
        raise HTTPException(
            429, "Another answer is being transcribed. Try again in a moment."
        )
    async with GATE:
        with tempfile.TemporaryDirectory(prefix="rendi-speech-") as folder:
            wav = Path(folder) / "answer.wav"
            try:
                await run(
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "pipe",
                    "-f",
                    fmt,
                    "-i",
                    "pipe:0",
                    "-vn",
                    "-t",
                    "14",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-c:a",
                    "pcm_s16le",
                    str(wav),
                    data=data,
                    timeout=8,
                )
                await run(
                    "whisper",
                    str(wav),
                    "--model",
                    "base.en",
                    "--model_dir",
                    str(MODEL.parent),
                    "--language",
                    "en",
                    "--device",
                    "cpu",
                    "--fp16",
                    "False",
                    "--threads",
                    "4",
                    "--temperature",
                    "0",
                    "--beam_size",
                    "1",
                    "--output_format",
                    "txt",
                    "--output_dir",
                    folder,
                    timeout=45,
                )
            except TimeoutError as exc:
                raise HTTPException(
                    504, "Dictation timed out. Tap to retry or type your answer."
                ) from exc
            transcript = wav.with_suffix(".txt")
            text = transcript.read_text().strip()[:600] if transcript.is_file() else ""
            if not text:
                raise HTTPException(
                    422, "No speech was detected. Try again or type your answer."
                )
            return text
