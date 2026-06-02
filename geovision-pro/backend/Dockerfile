FROM python:3.12-slim

# System deps: OpenCV runtime libs + Tesseract OCR (German + English)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
        tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# Install CPU torch + torchvision wheels by default (torchvision is required by
# GeoCLIP). Override with a CUDA base image for GPU. Installing them from the CPU
# index first means the later `-r requirements.txt` won't pull the heavy CUDA build.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        torch==2.5.1 torchvision==0.20.1 \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY sql ./sql

ENV GEOVISION_DEBUG=false
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
