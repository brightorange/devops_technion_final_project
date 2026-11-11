# ---- Stage 1: build — install dependencies into a virtualenv ----
FROM python:3.14.8-slim-trixie AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only requirements first: this layer is cached until requirements change,
# so editing app code doesn't trigger a full reinstall.
COPY requirements.txt .
RUN pip install -r requirements.txt


# ---- Stage 2: test — dev dependencies and test sources, for CI only ----
# Built with `docker build --target test`. Tests run on the exact Python and
# dependency set that ships. The runtime stage below copies only app code, so
# nothing from here reaches the released image.
FROM builder AS test

WORKDIR /src
# Requirements first so the install layer survives code edits.
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
COPY . .


# ---- Stage 3: prune — strip pip and setuptools out of the virtualenv ----
# The runtime never installs packages, and pip vendors its own copies of
# certifi, urllib3 and msgpack, which are the only remaining source of
# HIGH/CRITICAL CVEs. This must happen before the venv is copied into the
# runtime stage: deleting files in a later layer leaves them in layer history,
# where image scanners still find them.
FROM builder AS prune

RUN find /opt/venv/lib -maxdepth 3 \
        \( -name 'pip' -o -name 'pip-*' \
        -o -name 'setuptools' -o -name 'setuptools-*' \
        -o -name 'pkg_resources' \) \
        -exec rm -rf {} + \
    && rm -f /opt/venv/bin/pip*


# ---- Stage 4: runtime — only the virtualenv and app code ----
FROM python:3.14.8-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Patch OS packages the base image ships with known fixes for, and remove the
# base image's own pip/setuptools for the same reason as the prune stage. Both
# happen in one layer so nothing vulnerable is left behind in layer history.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && find /usr/local/lib/python3.* -maxdepth 2 \
        \( -name 'pip' -o -name 'pip-*' \
        -o -name 'setuptools' -o -name 'setuptools-*' \
        -o -name 'pkg_resources' \) \
        -exec rm -rf {} + \
    && rm -f /usr/local/bin/pip*

# Numeric UID so Kubernetes can verify runAsNonRoot.
RUN useradd --system --uid 10001 --no-create-home app

WORKDIR /app
COPY --from=prune /opt/venv /opt/venv
# Code stays owned by root: the app user can read it but not modify it.
COPY app ./app
COPY migrations ./migrations
COPY wsgi.py gunicorn.conf.py ./

USER 10001
EXPOSE 8000

# Used by docker / docker-compose. Kubernetes ignores it and uses its own probes.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')"]

# Bind, workers and logging now live in gunicorn.conf.py, alongside the
# Prometheus multiprocess hooks that need them.
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
