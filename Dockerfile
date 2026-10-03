# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/biblebot \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /src

COPY pyproject.toml uv.lock MANIFEST.in README.md LICENSE ./
COPY src/ ./src/

RUN uv sync --locked --no-dev --extra e2e --no-editable

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
