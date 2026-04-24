FROM ghcr.io/ggml-org/llama.cpp:server-cuda

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir huggingface_hub==0.34.4

WORKDIR /app

COPY docker/llm_entrypoint.py /app/llm_entrypoint.py
RUN chmod +x /app/llm_entrypoint.py

ENTRYPOINT ["python", "/app/llm_entrypoint.py"]