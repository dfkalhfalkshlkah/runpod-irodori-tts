FROM docker.io/katalive/irodori-tts:latest

LABEL org.opencontainers.image.title="RunPod Irodori TTS Worker" \
      org.opencontainers.image.description="RunPod Serverless worker for Irodori TTS 500M v3" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/dfkalhfalkshlkah/runpod-irodori-tts"

COPY requirements.txt /app/requirements-worker.txt
RUN pip install --no-cache-dir --requirement /app/requirements-worker.txt

COPY handler.py /app/handler.py
COPY start.sh /app/start-worker.sh
RUN chmod 0755 /app/start-worker.sh

WORKDIR /app
CMD ["/app/start-worker.sh"]
