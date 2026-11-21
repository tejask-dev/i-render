"""Short, opt-in dictation with a locally installed Whisper model."""

import asyncio
import shutil
import tempfile
from pathlib import Path

from fastapi import HTTPException

MODEL = Path.home() / ".cache" / "whisper" / "base.en.pt"
GATE = asyncio.Semaphore(1)


def available():
    return bool(MODEL.is_file() and shutil.which("whisper") and shutil.which("ffmpeg"))


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
