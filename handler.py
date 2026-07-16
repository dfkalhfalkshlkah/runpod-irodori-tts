"""RunPod Serverless handler for Irodori TTS."""

from __future__ import annotations

import base64
import binascii
import os
import uuid
from typing import Any

import requests

IRODORI_API_URL = os.environ.get("IRODORI_API_URL", "http://127.0.0.1:8880").rstrip("/")
IRODORI_MODEL_ID = os.environ.get("IRODORI_MODEL_ID", "irodori-tts-500m-v3")
IRODORI_REQUEST_TIMEOUT = float(os.environ.get("IRODORI_REQUEST_TIMEOUT", "180"))
MAX_TEXT_LENGTH = int(os.environ.get("MAX_TEXT_LENGTH", "500"))
MAX_REFERENCE_AUDIO_BYTES = int(os.environ.get("MAX_REFERENCE_AUDIO_BYTES", "10485760"))


class InputError(ValueError):
    """Raised when a RunPod job contains invalid input."""


def _read_bounded_integer(
    value: Any,
    *,
    default: int,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputError(f"'{field}' must be an integer")
    if not minimum <= value <= maximum:
        raise InputError(f"'{field}' must be between {minimum} and {maximum}")
    return value


def _parse_job_input(job: dict[str, Any]) -> tuple[str, bytes | None]:
    job_input = job.get("input")
    if not isinstance(job_input, dict):
        raise InputError("'input' must be an object")

    text = job_input.get("input")
    if not isinstance(text, str) or not text.strip():
        raise InputError("'input.input' must be a non-empty string")
    text = text.strip()
    if len(text) > MAX_TEXT_LENGTH:
        raise InputError(f"'input.input' must not exceed {MAX_TEXT_LENGTH} characters")

    options = job_input.get("irodori", {})
    if not isinstance(options, dict):
        raise InputError("'input.irodori' must be an object")
    _read_bounded_integer(
        options.get("num_steps"),
        default=16,
        field="input.irodori.num_steps",
        minimum=1,
        maximum=100,
    )
    _read_bounded_integer(
        options.get("seed"),
        default=42,
        field="input.irodori.seed",
        minimum=0,
        maximum=2**32 - 1,
    )

    encoded_reference = job_input.get("ref_wav_b64")
    if encoded_reference is None:
        return text, None
    if not isinstance(encoded_reference, str) or not encoded_reference:
        raise InputError("'input.ref_wav_b64' must be a non-empty Base64 string")

    try:
        reference_audio = base64.b64decode(encoded_reference, validate=True)
    except (binascii.Error, ValueError) as error:
        raise InputError("'input.ref_wav_b64' is not valid Base64") from error
    if not reference_audio:
        raise InputError("'input.ref_wav_b64' decoded to an empty file")
    if len(reference_audio) > MAX_REFERENCE_AUDIO_BYTES:
        raise InputError(
            f"'input.ref_wav_b64' exceeds the {MAX_REFERENCE_AUDIO_BYTES}-byte limit"
        )

    return text, reference_audio


def _raise_for_upstream(response: requests.Response, operation: str) -> None:
    if response.ok:
        return
    message = response.text.replace("\n", " ")[:300]
    print(
        f"[ERROR] Irodori TTS {operation} failed with status "
        f"{response.status_code}: {message}",
        flush=True,
    )
    raise RuntimeError(
        f"Irodori TTS {operation} failed with status {response.status_code}"
    )


def _upload_reference(session: requests.Session, audio: bytes) -> str:
    voice_id = f"runpod_{uuid.uuid4().hex}"
    response = session.post(
        f"{IRODORI_API_URL}/v1/audio/voice_contents",
        data={"voice_id": voice_id},
        files={"file": (f"{voice_id}.wav", audio, "audio/wav")},
        timeout=30,
    )
    _raise_for_upstream(response, "reference upload")
    response_data = response.json()
    returned_id = response_data.get("id") if isinstance(response_data, dict) else None
    if returned_id != voice_id:
        raise RuntimeError("Irodori TTS returned an invalid reference voice ID")
    return voice_id


def _delete_reference(session: requests.Session, voice_id: str) -> None:
    try:
        response = session.delete(
            f"{IRODORI_API_URL}/v1/audio/voice_contents/{voice_id}",
            timeout=15,
        )
        if not response.ok:
            print(
                f"[WARN] Failed to delete temporary reference voice {voice_id}: "
                f"status {response.status_code}",
                flush=True,
            )
    except requests.RequestException as error:
        print(
            f"[WARN] Failed to delete temporary reference voice {voice_id}: "
            f"{type(error).__name__}",
            flush=True,
        )


def synthesize(job: dict[str, Any], session: requests.Session | None = None) -> dict[str, str]:
    """Validate a RunPod job and return Base64-encoded WAV audio."""
    text, reference_audio = _parse_job_input(job)
    active_session = session or requests.Session()
    voice_id: str | None = None

    try:
        if reference_audio is not None:
            voice_id = _upload_reference(active_session, reference_audio)

        response = active_session.post(
            f"{IRODORI_API_URL}/v1/audio/speech",
            json={
                "model": IRODORI_MODEL_ID,
                "input": text,
                "voice": voice_id or "none",
                "response_format": "wav",
                "speed": 1.0,
            },
            timeout=IRODORI_REQUEST_TIMEOUT,
        )
        _raise_for_upstream(response, "speech synthesis")
        if not response.content:
            raise RuntimeError("Irodori TTS returned empty audio")

        return {
            "audio_b64": base64.b64encode(response.content).decode("ascii"),
            "mime_type": "audio/wav",
        }
    finally:
        if voice_id is not None:
            _delete_reference(active_session, voice_id)
        if session is None:
            active_session.close()


def handler(job: dict[str, Any]) -> dict[str, str]:
    """RunPod handler entry point."""
    return synthesize(job)


if __name__ == "__main__":
    import runpod

    print("[INFO] Starting RunPod Irodori TTS worker", flush=True)
    runpod.serverless.start({"handler": handler})
