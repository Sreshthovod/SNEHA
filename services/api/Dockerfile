# SNEHA API container (used by render.yaml). No model weights are baked in.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

# Dependencies first for layer caching; no dev tools and no speech models.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-group speech --no-install-project

COPY . .
RUN rm -f sneha_dev.db .env && useradd --create-home sneha \
    && mkdir -p /app/var/media && chown -R sneha /app/var
USER sneha

# Apply migrations, then serve on the port the host provides.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
