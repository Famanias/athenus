# Athenus Backend — Production (multi-stage)
# Optimized image for self-hosted deployment.
FROM python:3.11-slim-bookworm AS runtime-deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

FROM runtime-deps AS app

WORKDIR /app

COPY backend/ /app/

# Non-root execution (Security: least privilege).
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# workers=1: embedded SQLite + Qdrant are single-process file stores; multiple
# uvicorn workers would contend on the same local files.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
