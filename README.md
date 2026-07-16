# Irodori TTS RunPod Serverless Worker

RunPod Serverless worker that provides Japanese speech synthesis using [Irodori TTS 500M v3](https://huggingface.co/Aratako/Irodori-TTS-500M-v3).

## Deploy from RunPod Hub

1. Open this repository's listing in RunPod Hub.
2. Select **Deploy** and then **Create Endpoint**.
3. Keep the endpoint type queue-based and deploy with one of the configured GPU pools.
4. Copy the generated Endpoint ID.
5. Create a RunPod API key with read and write permissions.
6. Configure your API client with the RunPod API key and Endpoint ID.

The first request can take several minutes while the worker starts, downloads model files, and loads the model into GPU memory. Workers can scale down to zero when idle.

## Request format

Send a synchronous request to `https://api.runpod.ai/v2/ENDPOINT_ID/runsync`:

```json
{
  "input": {
    "input": "こんにちは",
    "voice": "none",
    "response_format": "wav",
    "irodori": {
      "num_steps": 16,
      "seed": 42
    }
  }
}
```

The `irodori` object is accepted for compatibility with clients that use this request format. The container-wide `NUM_STEPS` environment variable controls inference steps in the current upstream API image. The current upstream API does not provide a per-request seed setting.

To use a reference voice, add a Base64-encoded WAV file as `ref_wav_b64`. Reference audio is uploaded with a unique temporary voice ID and deleted after each request.

Successful output:

```json
{
  "audio_b64": "BASE64_ENCODED_WAV",
  "mime_type": "audio/wav"
}
```

## Local checks

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
bash -n start.sh
python3 -m json.tool .runpod/hub.json >/dev/null
python3 -m json.tool .runpod/tests.json >/dev/null
docker build --platform linux/amd64 -t runpod-irodori-tts:local .
```

The base image is large. Allocate at least 30 GB for the container disk and enough local storage for the Docker build cache.

## Publish the base image

`Dockerfile.publish` bootstraps the public base image directly from the upstream Irodori TTS API image. Use it only when publishing a new base image version:

```bash
docker build \
  --platform linux/amd64 \
  --file Dockerfile.publish \
  --tag docker.io/katalive/irodori-tts:latest \
  .
docker push docker.io/katalive/irodori-tts:latest
```

The Docker Hub repository must be public so RunPod Hub can pull the image without registry credentials. The root `Dockerfile` consumes this published image during normal RunPod Hub builds.

## Environment variables

| Name | Default | Purpose |
| --- | --- | --- |
| `IRODORI_API_URL` | `http://127.0.0.1:8880` | Local Irodori TTS API URL |
| `IRODORI_MODEL_ID` | `irodori-tts-500m-v3` | Upstream model ID |
| `IRODORI_REQUEST_TIMEOUT` | `180` | Speech request timeout in seconds |
| `IRODORI_READY_TIMEOUT` | `600` | Local API startup timeout in seconds |
| `MAX_TEXT_LENGTH` | `500` | Maximum input length in Unicode characters |
| `MAX_REFERENCE_AUDIO_BYTES` | `10485760` | Maximum decoded reference audio size |
| `MODEL_DEVICE` | `cuda` | Upstream model device |
| `CODEC_DEVICE` | `cuda` | Upstream codec device |
| `MODEL_PRECISION` | `bf16` | Upstream model precision |
| `CODEC_PRECISION` | `bf16` | Upstream codec precision |
| `NUM_STEPS` | `16` in Hub config | Container-wide inference steps |

## Upstream software

This worker builds on `docker.io/katalive/irodori-tts:latest`, which packages the MIT-licensed [arianpg/irodori-tts-api](https://github.com/arianpg/irodori-tts-api) and [Aratako/Irodori-TTS](https://github.com/Aratako/Irodori-TTS). Their licenses and model terms apply independently.

## License

The worker-specific code in this repository is available under the MIT License. See [LICENSE](LICENSE).
