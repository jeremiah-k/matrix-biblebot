# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /src

RUN python -m venv /opt/biblebot

COPY pyproject.toml MANIFEST.in setup.cfg README.md LICENSE ./
COPY src/ ./src/

RUN /opt/biblebot/bin/python -m pip install --upgrade pip setuptools wheel && \
    /opt/biblebot/bin/python -m pip install ".[e2e]"

FROM python:3.12-slim-bookworm AS runtime

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

ENV BIBLEBOT_HOME=/data \
    PATH=/opt/biblebot/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 1000 biblebot && \
    useradd --uid 1000 --gid biblebot --shell /usr/sbin/nologin --create-home biblebot && \
    install -d --owner=biblebot --group=biblebot --mode=0700 /data

COPY --from=builder /opt/biblebot /opt/biblebot

WORKDIR /data
USER 1000:1000

CMD ["biblebot"]
