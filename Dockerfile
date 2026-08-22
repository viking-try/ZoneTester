# Zoneguard — single image, three roles (api | worker | beat) selected at runtime via $ROLE.
#
# CRITICAL: base must ship OpenSSL >= 3.5 or live post-quantum (ML-KEM / X25519MLKEM768)
# detection silently fails. python:3.13-slim-trixie (Debian trixie) ships OpenSSL 3.5+.
# Do NOT downgrade to python:3.13-slim (bookworm, OpenSSL 3.0) or PQC probing breaks silently.
FROM python:3.13-slim-trixie

RUN openssl version | grep -E "OpenSSL 3\.(5|[6-9]|[1-9][0-9])" || \
    (echo "FATAL: base image OpenSSL is too old for PQC (ML-KEM) detection" && openssl version && exit 1)

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        libpq5 \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# dev deps (pytest, bandit, etc.) installed too — image is used for both runtime and CI/test.
RUN pip install --no-cache-dir -r requirements-dev.txt

RUN apt-get purge -y gcc libpq-dev && apt-get autoremove -y

COPY app ./app
COPY scripts ./scripts
COPY tests ./tests
COPY docs ./docs

RUN sed -i 's/\r$//' scripts/entrypoint.sh && chmod +x scripts/entrypoint.sh

RUN useradd --create-home --shell /usr/sbin/nologin zoneguard \
    && chown -R zoneguard:zoneguard /srv
USER zoneguard

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    ROLE=api

EXPOSE 8000

ENTRYPOINT ["/srv/scripts/entrypoint.sh"]
