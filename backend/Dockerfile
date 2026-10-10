# Build from the repo root (needs sample_data/):
#   docker build -f backend/Dockerfile -t terrawatch-api .
FROM python:3.11-slim

# rasterio/fiona/pyproj wheels bundle GDAL/PROJ; weasyprint needs pango.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY backend/requirements.txt .
# CPU-only torch wheel first so requirements.txt doesn't pull the CUDA build.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# TinyCD pretrained weights (same source as `make setup-backend`).
RUN mkdir -p models/tinycd \
    && curl -fsSL -o models/tinycd/levir_best.pth \
       https://github.com/AndreaCodegoni/Tiny_model_4_CD/raw/main/pretrained_models/levir_best.pth

COPY backend/ .
# Wayanad demo pair backs the Wayanad case study.
COPY sample_data/wayanad/before.tif sample_data/wayanad/after.tif data/wayanad/

ENV PYTHONUNBUFFERED=1 PORT=8000
EXPOSE 8000
# Single worker: background analysis jobs run in-process and share one sqlite db.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
