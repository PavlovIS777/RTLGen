FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    iverilog \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.docker.txt /app/requirements.docker.txt
RUN pip install --no-cache-dir -r /app/requirements.docker.txt

COPY . /app

CMD ["sh", "-lc", "tail -f /dev/null"]