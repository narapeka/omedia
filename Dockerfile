# syntax=docker/dockerfile:1

FROM --platform=$BUILDPLATFORM node:24-bookworm-slim AS frontend-builder
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMEDIA_DATA_DIR=/data \
    OMEDIA_HOST=0.0.0.0 \
    OMEDIA_PORT=7108
LABEL org.opencontainers.image.licenses="GPL-3.0-only"

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml backend/uv.lock ./backend/
COPY backend/app ./backend/app
RUN uv sync --project backend --frozen --no-dev

COPY data/common.example.yaml ./data/common.example.yaml
COPY --from=frontend-builder /src/frontend/dist ./frontend/dist

ENV PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 7108
VOLUME ["/data"]

CMD ["omedia-server"]
