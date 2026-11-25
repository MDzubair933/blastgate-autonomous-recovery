# Multi-stage minimal production container for BlastGate ECS worker
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /install /usr/local
COPY . /app

ENV PYTHONUNBUFFERED=1

# Zero inbound ports - Outbound telemetry only
USER 1000:1000

ENTRYPOINT ["python", "main.py"]
