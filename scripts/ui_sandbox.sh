#!/bin/zsh
# Throwaway app server on a COPY of the library, for driving the UI (browser
# automation, layout checks, screenshots) WITHOUT touching Grace's real state.
#
# Why this exists (JOURNAL Entry 26): headless Chromium autoplays by default, so
# pointing a layout check at the live server played audio and overwrote two real
# resume positions. Never drive the live instance again — drive this.
#
# Binds 127.0.0.1 only (not Tailscale): a scratch copy has no business on the
# network. Different port from the real server so both can run at once.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${UI_SANDBOX_PORT:-8199}"
SB="${UI_SANDBOX_DIR:-${TMPDIR:-/tmp}/hr_ui_sandbox}"

rm -rf "$SB"
mkdir -p "$SB"
# copy the state the UI reads; audio included so the player has something real
if [[ -f data/app.db ]]; then
  # .backup gets a consistent snapshot even with WAL active
  .venv/bin/python -c "
import sqlite3, sys
src = sqlite3.connect('data/app.db'); dst = sqlite3.connect(sys.argv[1])
src.backup(dst); dst.close(); src.close()" "$SB/app.db"
fi
for d in library voice_samples; do
  [[ -d "data/$d" ]] && cp -R "data/$d" "$SB/$d"
done
mkdir -p "$SB/interim"

echo "UI sandbox at http://127.0.0.1:$PORT  (state copy: $SB)"
echo "Real library untouched. Ctrl-C to stop; the copy is discarded next run."
HR_DATA_DIR="$SB" exec .venv/bin/uvicorn app.server:app --host 127.0.0.1 --port "$PORT"
