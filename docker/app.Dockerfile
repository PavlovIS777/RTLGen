FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    iverilog \
    && rm -rf /var/lib/apt/lists/*

COPY configs/requirements.docker.txt /tmp/requirements.docker.txt
RUN pip install --no-cache-dir -r /tmp/requirements.docker.txt

CMD ["sh", "-lc", "tail -f /dev/null"]
