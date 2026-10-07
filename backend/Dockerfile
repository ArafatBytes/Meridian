# =============================================================================
# Meridian backend — FastAPI + the YOLOv9/MediaPipe/CLIP vision stack
# =============================================================================
# Dev-oriented: code is bind-mounted and uvicorn reloads. Hardening (non-root,
# pinned digests, no reload, multi-stage slimming) is a Phase 6 item — see
# IMPLEMENTATION_PLAN.md S31/S37.
#
# First build takes 5–12 minutes, almost entirely torch and its dependencies.
# Rebuilds after a code change are instant: requirements are a separate layer.
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Keep every model download inside one mounted volume. Without this, CLIP
    # (~600 MB) re-downloads on every container recreate.
    HF_HOME=/cache/huggingface \
    TORCH_HOME=/cache/torch \
    YOLO_CONFIG_DIR=/cache/ultralytics \
    MPLCONFIGDIR=/cache/matplotlib

# -----------------------------------------------------------------------------
# System packages
# -----------------------------------------------------------------------------
# libgl1 + libglib2.0-0 are the ones that matter and the ones the previous
# Dockerfile was missing: without them `import cv2` and `import mediapipe` fail
# at startup with "libGL.so.1: cannot open shared object file". The geospatial
# libs are for shapely/pyproj; libmagic1 for python-magic.
RUN apt-get update && apt-get install --no-install-recommends -y \
        gcc \
        g++ \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
        libpq-dev \
        libgeos-dev \
        libproj-dev \
        libmagic1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Python dependencies
# -----------------------------------------------------------------------------
# CPU-only torch, installed first and deliberately from PyTorch's CPU index.
# The default PyPI wheel bundles the CUDA runtime: ~2.5 GB of GPU libraries that
# cannot be used here. The later `-r requirements.txt` sees torch as already
# satisfied and leaves it alone.
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# YOLOv9c weights, baked in
# -----------------------------------------------------------------------------
# crime_vision_service calls YOLO('yolov9c.pt') with a bare filename, which
# ultralytics resolves against the working directory and otherwise downloads on
# demand. Two problems with letting that happen at runtime: the first AI request
# stalls ~3 minutes behind an 82 MB download, and because /app is a container
# layer rather than a mounted volume, the file is lost on every
# `docker compose up --force-recreate`.
#
# Downloading it here makes startup deterministic and offline-capable, as a
# cached layer that only re-runs if this line changes.
RUN python -c "from ultralytics import YOLO; YOLO('yolov9c.pt')" \
    && test -f yolov9c.pt \
    && echo "yolov9c.pt: $(stat -c%s yolov9c.pt) bytes"

# -----------------------------------------------------------------------------
# Application
# -----------------------------------------------------------------------------
# Copied so the image can run standalone; docker-compose bind-mounts over this
# for live reload during development.
COPY . .

RUN mkdir -p logs uploads /cache

EXPOSE 8000

# Uses urllib from the standard library. The previous healthcheck imported
# `requests`, which is not in requirements.txt, so it failed every time and the
# container was permanently marked unhealthy.
#
# start-period is 90s: importing torch, mediapipe, cv2 and transformers takes
# 15–40s on a cold start, and a shorter window kills the container mid-import.
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=5).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
