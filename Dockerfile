# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.6 AS uv

FROM python:3.12-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM python:3.12-slim
# git for the gitops_log tool (a clone of voting-gitops, refreshed with git fetch).
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /app /app
COPY docker-entrypoint.sh /usr/local/bin/
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 HOME=/work HOST=0.0.0.0 PORT=8080
# Numeric UID so Kubernetes can verify runAsNonRoot.
USER 1000:1000
EXPOSE 8080
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["ai-sre-agent"]
