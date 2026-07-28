#!/usr/bin/env bash
# Scheduler (Entry 37, Grace's proposal (i)) — installs/removes the launchd job
# that keeps the replenishment worker running.
#
# ⚠ GRACE RUNS THIS, NOT CLAUDE. `install` writes a plist into
# ~/Library/LaunchAgents — outside the repo — and starts a background process
# that survives reboots and renders audio unattended. Both are hers to consent
# to, not something a coding session should do on her behalf (Entry 37: it was
# done unasked once, and removed). Claude may EDIT this script and run
# `status`; it must never run `install` or `uninstall`.
#
# The job deliberately carries NO cadence: it is a KeepAlive wrapper whose only
# duty is "the loop is running". How OFTEN the loop cycles is a settings row
# (`worker_interval_s`), re-read every cycle by pipeline/worker.py — so the
# number can be changed from the app's Settings tab and takes effect on the
# next tick, with no reinstall, no plist edit and no restart. Putting the
# interval in the plist would have made the app's own setting a lie.
#
# The worker NEVER spends money (AMENDMENT_04 A): it consumes the already-paid
# pool and stops with a message when the pool is empty. So a scheduler running
# unattended cannot run up a bill; the spend cap covers the builds Grace starts.
#
#   scripts/scheduler.sh install     # load the job (starts immediately)
#   scripts/scheduler.sh uninstall   # unload and remove it
#   scripts/scheduler.sh status      # is it loaded, and what is the cadence
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Run from the repo root whatever directory the caller was in. `status` imports
# `pipeline`, which resolves off the cwd, not off $PY — so without this the
# script only worked when invoked from the root, and a runbook reader following
# it from $HOME got a ModuleNotFoundError. Every other path below is absolute,
# so this is safe for all subcommands.
cd "$ROOT"
LABEL="com.gracegu.horror-readaloud.worker"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PY="$ROOT/.venv/bin/python"
LOG="$ROOT/data/interim/worker_loop.log"

usage() { sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 2; }

case "${1:-}" in
install)
  [ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
  # A second, deliberate speed bump. This writes outside the repo and starts a
  # persistent background job, so it refuses to run non-interactively — which
  # is exactly the shape an automated agent invocation has.
  if [ ! -t 0 ] && [ "${HR_SCHEDULER_CONFIRM:-}" != "yes" ]; then
    echo "refusing to install non-interactively." >&2
    echo "run this yourself in a terminal, or set HR_SCHEDULER_CONFIRM=yes if" >&2
    echo "you really mean it from a script." >&2
    exit 3
  fi
  mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
  cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <!-- -u is load-bearing: launchd redirects stdout to a FILE, and Python
         block-buffers a non-tty. Without it the [worker] lines sit in a 8KB
         buffer for hours while only stderr (torch's warnings) reaches the log,
         which makes an unattended job look broken and undebuggable. -->
    <string>-u</string>
    <string>-m</string>
    <string>pipeline.worker</string>
    <string>--loop</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <!-- KeepAlive, not StartInterval: the cadence is a settings row the loop
       re-reads each cycle. launchd only guarantees the loop is alive. -->
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST_EOF
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "installed $LABEL"
  echo "  plist:  $PLIST"
  echo "  log:    $LOG"
  echo "  cadence: set in the app's Settings tab (worker_interval_s), not here"
  ;;
uninstall)
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "uninstalled $LABEL"
  ;;
status)
  if launchctl list | grep -q "$LABEL"; then
    echo "loaded:  yes"
    launchctl list | grep "$LABEL" | awk '{print "  pid/exit: "$1"/"$2}'
  else
    echo "loaded:  no"
  fi
  echo -n "cadence: "
  # Says WHERE the number came from. "from settings" printed over a default
  # would be a small lie, and the whole point of this design is that the
  # setting is the operative value.
  "$PY" -c "
from pipeline import db
conn = db.connect()
stored = db.get_setting(conn, 'worker_interval_s')
src = 'settings' if stored else 'default — never set in Settings'
print(f'{db.effective_worker_interval_s(conn)}s (from {src})')
"
  ;;
*) usage ;;
esac
