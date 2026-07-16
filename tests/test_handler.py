import base64
from unittest.mock import Mock

import pytest
import requests

import handler


def response(*, content=b"", json_data=None, status=200, text=""):
    result = Mock(spec=requests.Response)
    result.ok = 200 <= status < 300
    result.status_code = status
    result.content = content
    result.text = text
    result.json.return_value = json_data
    return result


def basic_job(**overrides):
    job_input = {
        "input": "こんにちは",
        "voice": "none",
        "response_format": "wav",
        "irodori": {"num_steps": 16, "seed": 42},
    }
    job_input.update(overrides)
    return {"input": job_input}


def test_synthesize_returns_base64_wav():
    session = Mock(spec=requests.Session)
    session.post.return_value = response(content=b"RIFF-test-audio")

    result = handler.synthesize(basic_job(), session=session)

    assert base64.b64decode(result["audio_b64"]) == b"RIFF-test-audio"
    assert result["mime_type"] == "audio/wav"
    _, kwargs = session.post.call_args
    assert kwargs["json"] == {
        "model": "irodori-tts-500m-v3",
        "input": "こんにちは",
        "voice": "none",
        "response_format": "wav",
        "speed": 1.0,
    }


def test_reference_voice_is_uploaded_and_deleted():
    session = Mock(spec=requests.Session)

    def post(url, **kwargs):
        if url.endswith("/voice_contents"):
            voice_id = kwargs["data"]["voice_id"]
            return response(status=201, json_data={"id": voice_id})
        return response(content=b"RIFF-reference-audio")

    session.post.side_effect = post
    session.delete.return_value = response(status=200)
    encoded = base64.b64encode(b"RIFF-reference").decode("ascii")

    handler.synthesize(basic_job(ref_wav_b64=encoded), session=session)

    session.delete.assert_called_once()
    assert "/v1/audio/voice_contents/runpod_" in session.delete.call_args.args[0]


def test_reference_voice_is_deleted_after_synthesis_error():
    session = Mock(spec=requests.Session)

    def post(url, **kwargs):
        if url.endswith("/voice_contents"):
            voice_id = kwargs["data"]["voice_id"]
            return response(status=201, json_data={"id": voice_id})
        return response(status=500, text="model failed")

    session.post.side_effect = post
    session.delete.return_value = response(status=200)
    encoded = base64.b64encode(b"RIFF-reference").decode("ascii")

    with pytest.raises(RuntimeError, match="speech synthesis failed with status 500"):
        handler.synthesize(basic_job(ref_wav_b64=encoded), session=session)

    session.delete.assert_called_once()


@pytest.mark.parametrize(
    "job, message",
    [
        ({}, "'input' must be an object"),
        (basic_job(input="  "), "must be a non-empty string"),
        (basic_job(irodori={"num_steps": 0}), "num_steps' must be between 1 and 100"),
        (basic_job(irodori={"seed": True}), "seed' must be an integer"),
        (basic_job(ref_wav_b64="not-base64"), "is not valid Base64"),
    ],
)
def test_invalid_input_is_rejected_before_upstream_request(job, message):
    session = Mock(spec=requests.Session)

    with pytest.raises(handler.InputError, match=message):
        handler.synthesize(job, session=session)

    session.post.assert_not_called()
