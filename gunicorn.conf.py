"""
Gunicorn configuration for production deployment.

Usage:
    gunicorn backend.main:app -c gunicorn.conf.py

Environment override (useful in Docker):
    WEB_CONCURRENCY=4 gunicorn backend.main:app -c gunicorn.conf.py
"""
import multiprocessing
import os

# ─── Workers ─────────────────────────────────────────────────────────────────
# Standard recommendation: (2 × CPU cores) + 1
# Capped at 8 to avoid overwhelming SQLite write serialisation.
# Override via WEB_CONCURRENCY env var for fine-tuning without editing this file.
workers = int(os.getenv("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 8)))

# uvicorn worker: required for ASGI apps (FastAPI).
worker_class = "uvicorn.workers.UvicornWorker"

# ─── Binding ─────────────────────────────────────────────────────────────────
bind = os.getenv("BIND", "0.0.0.0:8000")

# ─── Timeouts ────────────────────────────────────────────────────────────────
# How long a worker may be silent before the master kills and restarts it.
# Keep generous enough for slow DB writes (SQLite busy_timeout = 5 s).
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
keepalive = 5           # seconds to keep idle connections open (behind nginx)
graceful_timeout = 10   # seconds to finish in-flight requests on SIGTERM

# ─── Connection handling ─────────────────────────────────────────────────────
worker_connections = 1000   # max simultaneous connections per worker (uvicorn)

# ─── Self-healing ────────────────────────────────────────────────────────────
# Restart workers periodically to prevent memory leaks in long-running processes.
max_requests = 1000
max_requests_jitter = 100   # ± random offset prevents thundering herd restarts

# ─── Pre-loading ─────────────────────────────────────────────────────────────
# IMPORTANT: DO NOT enable preload_app with SQLite.
# With preload the parent process opens SQLAlchemy connections BEFORE fork;
# child workers then share corrupted connection state.
# Set to True only when using PostgreSQL / MySQL.
preload_app = os.getenv("DATABASE_URL", "").startswith("postgresql") or \
              os.getenv("DATABASE_URL", "").startswith("mysql")

# ─── Logging ─────────────────────────────────────────────────────────────────
accesslog = "-"      # stdout (captured by Docker / systemd)
errorlog = "-"       # stderr
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ─── TLS (optional) ──────────────────────────────────────────────────────────
# Set SSL_CERTFILE / SSL_KEYFILE env vars to enable HTTPS.
# Example: SSL_CERTFILE=certs/cert.pem SSL_KEYFILE=certs/key.pem gunicorn …
_cert = os.getenv("SSL_CERTFILE", "")
_key  = os.getenv("SSL_KEYFILE", "")
if _cert and _key:
    certfile = _cert
    keyfile  = _key
