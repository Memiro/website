FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependencies first: this layer survives source edits.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

# The admin's static files are baked into the image; the compose volume
# nginx reads is refreshed from here when the admin container starts.
COPY .config ./.config
RUN APP_CONFIG_PATH=/app/.config/config.docker.toml \
    /app/.venv/bin/memiro django collectstatic --no-input

ENV PATH="/app/.venv/bin:$PATH"
