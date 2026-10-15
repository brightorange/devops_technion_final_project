# ---- Stage 1: build — install dependencies into a virtualenv ----
FROM python:3.13.16-slim-trixie AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only requirements first: this layer is cached until requirements change,
# so editing app code doesn't trigger a full reinstall.
COPY requirements.txt .
RUN pip install -r requirements.txt


# ---- Stage 2: runtime — only the virtualenv and app code ----
FROM python:3.13.16-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Numeric UID so Kubernetes can verify runAsNonRoot.
RUN useradd --system --uid 10001 --no-create-home app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 migrations ./migrations
COPY --chown=10001:10001 wsgi.py .

USER 10001
EXPOSE 8000

# Used by docker / docker-compose. Kubernetes ignores it and uses its own probes.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')"]

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "wsgi:app"]
