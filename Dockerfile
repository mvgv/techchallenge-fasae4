# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

# CPU por padrão. Para GPU: TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128 (cu121 não suporta RTX 50xx)
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG EXTRAS=audio,video,reports,dashboard,dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/root/.cache/huggingface \
    YOLO_CONFIG_DIR=/tmp/Ultralytics \
    MPLBACKEND=Agg

# ffmpeg: conversão de áudio/vídeo | libgl1, libglib2.0-0: OpenCV | libsndfile1: soundfile/librosa
# libpango*, libharfbuzz-subset0, fonts-dejavu-core: WeasyPrint (PDF) | curl: healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 libsndfile1 \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Torch (camada grande, muda raramente)
RUN pip install torch torchvision --index-url ${TORCH_INDEX_URL}

# 2) Dependências do projeto SEM o código, para aproveitar o cache de camadas:
#    alterar código em src/ não reinstala dependências.
COPY pyproject.toml README.md ./
RUN mkdir -p src/medwatch \
    && echo '__version__ = "0.1.0"' > src/medwatch/__init__.py \
    && pip install -e ".[${EXTRAS}]"

# 3) Código e arquivos de apoio (o install editável aponta para /app/src)
COPY src ./src
COPY config ./config
COPY db ./db
COPY scripts ./scripts
COPY tests ./tests

RUN mkdir -p /app/data/storage /app/data/references /app/data/samples /app/models

EXPOSE 8000 8501
CMD ["uvicorn", "medwatch.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
