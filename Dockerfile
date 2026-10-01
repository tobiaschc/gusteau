# syntax=docker/dockerfile:1

# ---- build the web UI ----
FROM node:22-alpine AS ui
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# vite outDir is ../gusteau/static
RUN mkdir -p ../gusteau && npm run build

# ---- runtime ----
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    GUSTEAU_DATA=/data GUSTEAU_PORT=8000 GUSTEAU_HOST=0.0.0.0
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY gusteau/ gusteau/
COPY recipes/ recipes/
COPY aisles.yml products.yml README.md ./
COPY --from=ui /src/gusteau/static gusteau/static
RUN uv sync --frozen --no-dev \
    && useradd --system --uid 1000 --home /app gusteau \
    && mkdir -p /data && chown gusteau /data

USER gusteau
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"GUSTEAU_PORT\"]}/api/health', timeout=3)"
CMD ["gusteau"]
