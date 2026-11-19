# Build context is the repository root (see docker-compose.yml) so the synthetic samples
# can be copied in for demo seeding.
FROM python:3.11.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/data ./data
COPY backend/scripts/entrypoint.sh ./entrypoint.sh
COPY samples/synthetic ./samples/synthetic

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/uploads \
    && chown -R appuser /data \
    && chmod +x ./entrypoint.sh
USER appuser

ENV UPLOAD_DIR=/data/uploads \
    SAMPLES_DIR=/app/samples/synthetic

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

ENTRYPOINT ["./entrypoint.sh"]
