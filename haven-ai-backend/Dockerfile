# Haven AI backend — production image.
#
# IMPORTANT: build this image on a machine that HAS the large runtime files,
# because they are gitignored and will NOT come from a GitHub checkout:
#   * ml_models/segformer-b2-ade/model.onnx   (~110 MB, Interior Design)
#   * assets/interior/models, assets/interior/textures/*  (~0.9 GB, Interior Design)
# Build + push from your machine:
#   docker build -t <registry>/haven-ai-backend:latest haven-ai-backend
#   docker push <registry>/haven-ai-backend:latest
# then point Render (or any host) at that image. A build straight from the git
# repo will start, but Interior Design and 3D texturing will fail at runtime.

FROM python:3.11-slim

# System libraries the ML wheels load at import time:
#   libgomp1      -> onnxruntime, xgboost, scikit-learn (OpenMP runtime)
#   libglib2.0-0  -> opencv-python-headless
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python deps first so they cache across code changes.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    # Floor-plan OCR: installed with --no-deps on purpose, otherwise it pulls
    # opencv-python and clashes with the headless build (see requirements.txt).
    && pip install --no-deps rapidocr-onnxruntime==1.4.4

# Application code and the (gitignored) model + asset files present at build time.
COPY . .

# The host provides $PORT (Render, Railway, Fly all do). One worker only: each
# worker loads the ONNX segmentation model into memory, so extra workers would
# multiply RAM for little benefit on CPU inference.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
