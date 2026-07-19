#!/bin/zsh
# One-command app server (TASKS Phase 4 output; RUNBOOK).
# Binds the Tailscale interface ONLY (DESIGN §1 / negative spec §10) — resolves
# the live IP via the tailscale CLI, falling back to the last-known address in
# pipeline/config.py. Builds the frontend on first run if dist/ is missing.
set -euo pipefail
cd "$(dirname "$0")/.."

TS_BIN="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
if command -v tailscale >/dev/null 2>&1; then
  IP="$(tailscale ip -4 2>/dev/null | head -1)"
elif [[ -x "$TS_BIN" ]]; then
  IP="$("$TS_BIN" ip -4 2>/dev/null | head -1)"
fi
if [[ -z "${IP:-}" ]]; then
  IP="$(.venv/bin/python -c 'from pipeline import config; print(config.TAILSCALE_IP_FALLBACK)')"
  echo "WARNING: tailscale CLI not found; using last-known IP $IP" >&2
fi
PORT="$(.venv/bin/python -c 'from pipeline import config; print(config.APP_PORT)')"

if [[ ! -d app/frontend/dist ]]; then
  echo "frontend dist/ missing — building once..."
  (cd app/frontend && npm install --no-audit --no-fund && npm run build)
fi

echo "serving on http://$IP:$PORT (Tailscale only)"
exec .venv/bin/uvicorn app.server:app --host "$IP" --port "$PORT"
