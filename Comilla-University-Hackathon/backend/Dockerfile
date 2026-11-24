# Ek Call backend image (FastAPI + agent + ML models on CPU).
#
# Build and run with docker-compose.yml in this folder:  docker compose up -d --build backend
# Not in the image (see .dockerignore): .env (passed in as environment), the models (mounted read-only
# at /app/data/models), the databases (Postgres and Chroma containers).

# ---------------------------------------------------------------- 1. build: install packages into a venv
FROM python:3.11-slim AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH" PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Same order as requirements.txt says: CPU PyTorch first (the default one would pull GPU libraries),
# then the rest, then the BanglaBERT text normaliser (from git). Own layer, so code changes reuse it.
RUN pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu --timeout 600 --retries 10
COPY requirements.txt .
RUN pip install -r requirements.txt \
    && pip install git+https://github.com/csebuetnlp/normalizer

# ---------------------------------------------------------------- 2. run: only the venv and the code
FROM python:3.11-slim

RUN useradd --create-home --uid 1000 ekcall
COPY --from=build /venv /venv
ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

WORKDIR /app
COPY --chown=ekcall:ekcall . .
RUN mkdir -p data/models && chown ekcall:ekcall data data/models
USER ekcall

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# One worker on purpose: voice jobs and the call silence counter live in this process's memory.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
