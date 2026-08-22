#!/usr/bin/env bash
# Server agent — installs/removes the launchd job that keeps the APP SERVER
# (scripts/serve.sh) running, so the library is reachable from the phone without
# a terminal open on the Mac.
#
# ⚠ GRACE RUNS THIS, NOT CLAUDE. `install` writes a plist into
# ~/Library/LaunchAgents — outside the repo — and starts a background process
# that survives reboots. Both are hers to consent to. Claude may EDIT this
# script and run `status`; it must never run `install` or `uninstall`. Same rule
# as scripts/scheduler.sh, whose header is the origin of this one.
#
# NOT the same job as scripts/scheduler.sh. That one keeps the REPLENISHMENT
# WORKER cycling (it renders audio); this one keeps the SERVER answering. They
# carry different labels and are installed independently — you can run the app
# without the worker, and vice versa.
#
# Two details that are load-bearing, both learned on french_passerelle 2026-08-20:
#
#   PATH — launchd hands a job a minimal PATH and does NOT source ~/.zshrc.
#   serve.sh calls `.venv/bin/uvicorn` by absolute path, but it also falls back
#   to `npm install && npm run build` when app/frontend/dist is missing, and that
#   needs node. /opt/homebrew/bin is deliberate: the Cellar path carries a
#   version number and breaks on the next `brew upgrade node`.
#
#   KeepAlive — at login launchd may start this BEFORE Tailscale connects.
#   serve.sh then correctly REFUSES (exit 2, its whole point). KeepAlive plus
#   ThrottleInterval turn that into a retry every 30s instead of a dead service.
#   The restarts in the log at boot are the design, not a fault.
#
#   scripts/server-agent.sh install     # load the job (starts immediately)
#   scripts/server-agent.sh uninstall   # unload and remove it
#   scripts/server-agent.sh status      # is it loaded, and is it answering
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LABEL="com.gracegu.infinite-audiobook.server"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$ROOT/data/interim/server.log"
TS_BIN="/Applications/Tailscale.app/Contents/MacOS/Tailscale"

usage() { echo "usage: scripts/server-agent.sh {install|uninstall|status}" >&2; exit 64; }
[[ $# -eq 1 ]] || usage

case "$1" in
install)
  # Same speed bump scheduler.sh carries, and for the same reason: this writes a
  # plist outside the repo and starts a persistent background process, so it
  # refuses to run non-interactively -- which is exactly the shape an automated
  # agent invocation has. CLAUDE.md says Grace installs launchd jobs and Claude
  # may only run `status`; without this the rule is convention, not a control.
  if [ ! -t 0 ] && [ "${HR_SERVER_AGENT_CONFIRM:-}" != "yes" ]; then
    echo "refusing to install non-interactively." >&2
    echo "run this yourself in a terminal, or set HR_SERVER_AGENT_CONFIRM=yes if" >&2
    echo "you really mean it from a script." >&2
    exit 3
  fi
  mkdir -p "$(dirname "$LOG")"
  cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>$ROOT/scripts/serve.sh</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST_EOF
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "loaded $LABEL"
  echo "  log:  $LOG"
  echo "  test: scripts/server-agent.sh status"
  ;;
uninstall)
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "removed $LABEL"
  ;;
status)
  # Capture first, THEN grep. `launchctl list | grep -q` looks correct and is
  # not: grep -q exits on first match, the pipe closes, launchctl dies of
  # SIGPIPE (141), and `set -o pipefail` reports the pipeline as failed — so a
  # job that IS loaded prints "loaded: no". Hit for real on french_passerelle
  # 2026-08-20. Any short-circuiting consumer (grep -q, head) has this problem
  # under pipefail; reading into a variable removes the pipe.
  LIST="$(launchctl list || true)"
  ROW="$(printf '%s\n' "$LIST" | grep "$LABEL" || true)"
  if [[ -n "$ROW" ]]; then
    echo "loaded:  yes  ($(printf '%s\n' "$ROW" | awk '{print "pid="$1" last-exit="$2}'))"
  else
    echo "loaded:  no"
  fi
  IP="$("$TS_BIN" ip -4 2>/dev/null | head -1 || true)"
  if [[ -z "$IP" ]]; then
    echo "tailscale: NOT CONNECTED — the job will retry every 30s until it is"
    exit 0
  fi
  echo "tailscale: $IP"
  PORT="$(.venv/bin/python -c 'from pipeline import config; print(config.APP_PORT)' 2>/dev/null || echo 8123)"
  CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://$IP:$PORT/" || true)"
  echo "answering: ${CODE:-no response} on http://$IP:$PORT/"
  echo "  (200 = serving. Open that URL on the phone with Tailscale on.)"
  ;;
*) usage ;;
esac
