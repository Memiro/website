FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_CACHE=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-default-groups

COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-editable --no-default-groups


FROM python:3.14-slim-bookworm
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
ENV DJANGO_SETTINGS_MODULE=memiro.settings

RUN adduser --system --group --no-create-home appuser && \
    chown -R appuser:appuser /app

COPY --from=builder /app/.venv /app/.venv

USER appuser
CMD ["sh", "-c", "django-admin migrate --noinput && gunicorn memiro.wsgi:application --bind 0.0.0.0:8000"]
