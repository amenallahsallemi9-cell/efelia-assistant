# Image multi-architecture (amd64 / arm64 — compatible Apple Silicon)
FROM python:3.12-slim-bookworm

# Tesseract (OCR en français) pour les pages scannées
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dépendances d'abord (cache Docker), puis le code
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --extra dev

COPY . .
RUN uv sync --frozen --extra dev

RUN useradd --create-home --uid 1000 efelia \
    && mkdir -p /data/dossiers \
    && chown -R efelia:efelia /data /app
USER efelia

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
