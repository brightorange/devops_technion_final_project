"""Gunicorn configuration.

Exists mainly for the Prometheus hooks: multiprocess metric collection needs a
shared directory that is empty at start, and dead workers' files have to be
cleaned up or their counters are reported forever.
"""

import os
import shutil

bind = "0.0.0.0:8000"
workers = 2
# Log to stdout: in Kubernetes that is the log transport. A file inside a
# container disappears on restart, and the root filesystem is read-only anyway.
accesslog = "-"


def on_starting(server):
    """Reset the metrics directory before any worker starts.

    The directory lives on an emptyDir volume, which survives a container
    restart within the same pod. Stale files from the previous run would be
    read back and reported as current.
    """
    path = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if path:
        shutil.rmtree(path, ignore_errors=True)
        os.makedirs(path, exist_ok=True)


def child_exit(server, worker):
    """Drop a dead worker's gauges so they stop being reported."""
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
