#!/usr/bin/env bash
# start-https.sh — run backend (HTTPS) + Streamlit (HTTPS) locally
#
# Usage:
#   bash start-https.sh          # backend :9443 | frontend :8443
#   BACKEND_PORT=9443 FRONTEND_PORT=8443 bash start-https.sh
#
# Pre-requisites:
#   ./certs/cert.pem and ./certs/key.pem must exist.
#   Run `python -m scripts.gen_cert` to create them.

set -euo pipefail

CERT="certs/cert.pem"
KEY="certs/key.pem"
BACKEND_PORT="${BACKEND_PORT:-9443}"
FRONTEND_PORT="${FRONTEND_PORT:-8443}"

if [[ ! -f "$CERT" || ! -f "$KEY" ]]; then
  echo "Cert not found. Generating self-signed cert …"
  .venv/bin/python -m scripts.gen_cert
fi

export PYTHONPATH="$(pwd)"
export BACKEND_URL="https://localhost:${BACKEND_PORT}"

echo "Starting backend  → https://localhost:${BACKEND_PORT}"
.venv/bin/uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "${BACKEND_PORT}" \
  --ssl-keyfile "${KEY}" \
  --ssl-certfile "${CERT}" \
  --reload &

BACKEND_PID=$!

sleep 2

echo "Starting frontend → https://localhost:${FRONTEND_PORT}"
.venv/bin/streamlit run ui/app.py \
  --server.port "${FRONTEND_PORT}" \
  --server.sslCertFile "${CERT}" \
  --server.sslKeyFile "${KEY}" \
  --server.headless true &

FRONTEND_PID=$!

echo ""
echo "─────────────────────────────────────────────────"
echo "  Backend  : https://localhost:${BACKEND_PORT}"
echo "  Frontend : https://localhost:${FRONTEND_PORT}"
echo "  API docs : https://localhost:${BACKEND_PORT}/docs"
echo "─────────────────────────────────────────────────"
echo "Press Ctrl-C to stop both services."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
