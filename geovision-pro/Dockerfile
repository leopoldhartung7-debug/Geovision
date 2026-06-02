# GeoVision Pro — single container (frontend + backend in one image).
# Used for Hugging Face Spaces (Docker SDK) and any one-URL deployment.
# Build context must be the `geovision-pro/` directory (sees frontend/ + backend/).

# --- Stage 1: build the React frontend ---
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build          # -> /web/dist

# --- Stage 2: Python backend that also serves the built frontend ---
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
        tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
# CPU torch + torchvision (GeoCLIP needs torchvision); installed from the CPU
# index first so the requirements step won't pull the heavy CUDA build.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        torch==2.5.1 torchvision==0.20.1 \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/sql ./sql
# Bundle the compiled frontend so FastAPI serves it at "/"
COPY --from=web /web/dist ./app/static

# Hugging Face Spaces defaults: writable caches under /tmp, SQLite (no Postgres),
# models downloaded lazily on first request, app on port 7860.
ENV HF_HOME=/tmp/hf \
    GEOVISION_DATABASE_URL=sqlite+aiosqlite:////tmp/geovision.db \
    GEOVISION_MODEL_LAZY_LOAD=true \
    GEOVISION_NOMINATIM_EMAIL="" \
    PORT=7860

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
