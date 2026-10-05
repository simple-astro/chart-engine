# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder
# pyswisseph ships no wheel for all platforms (e.g. linux/arm64); it compiles a C
# extension from sdist, which needs a toolchain. Kept to the builder stage only so
# the runtime image stays slim (no compiler in the final image).
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY core ./core
RUN pip install --no-cache-dir --prefix=/install ".[llm]"

FROM python:3.11-slim AS runtime
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /install /usr/local
RUN mkdir /data && chown appuser /data
ENV CHART_DB_PATH=/data/profiles.db
USER appuser
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/health').status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
