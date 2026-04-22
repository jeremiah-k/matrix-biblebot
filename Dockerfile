# Build stage
FROM python:3.12-slim-bookworm AS builder

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# hadolint ignore=DL3013
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY pyproject.toml MANIFEST.in setup.cfg README.md LICENSE ./
COPY src/ ./src/

RUN python -m pip install --no-cache-dir --timeout=300 --retries=3 \
    --prefix=/install ".[e2e]"

# Runtime stage
FROM python:3.12-slim-bookworm

RUN groupadd --gid 1000 biblebot && \
    useradd --uid 1000 --gid biblebot --shell /bin/bash --create-home biblebot

WORKDIR /app

COPY --from=builder /install /usr/local

RUN mkdir -p /data && chown -R biblebot:biblebot /app /data

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.opencontainers.image.title="Matrix BibleBot" \
      org.opencontainers.image.description="A Matrix bot that fetches Bible verses in response to scripture references" \
      org.opencontainers.image.url="https://github.com/jeremiah-k/matrix-biblebot" \
      org.opencontainers.image.source="https://github.com/jeremiah-k/matrix-biblebot" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1
ENV BIBLEBOT_HOME=/data

USER biblebot

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD biblebot --version || exit 1

CMD ["biblebot"]
