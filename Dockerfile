FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app


FROM base AS builder

# Only the metadata and the package are needed to build the wheel.
COPY pyproject.toml README.md LICENSE ./
COPY app ./app

# The runtime dependencies are installed into their own prefix so the
# builder stays out of the final image.
RUN pip install --no-cache-dir --prefix=/install .


FROM base AS runtime

COPY --from=builder /install /usr/local

# The application runs its own schema migrations on startup.
ENV AUTO_MIGRATE=true \
    ENVIRONMENT=production \
    DEBUG=false \
    DATABASE_URL=sqlite+aiosqlite:///./data/sandheal.db

RUN mkdir -p /app/data \
    && useradd --create-home --uid 10001 sandheal \
    && chown -R sandheal:sandheal /app

USER sandheal

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
