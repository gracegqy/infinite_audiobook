# RUNBOOK — horror_readaloud   *(stub — grows with each phase; completed at Phase 7)*

## Accounts & identity
- Repo: private, `https://github.com/gracegqy/horror_readaloud` (personal account
  `gracegqy`; commit identity Grace / graceguqianying@uchicago.edu; HTTPS + macOS
  keychain credential).
- API keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` in `.env` at repo root (gitignored).
  Set spend caps on both provider dashboards. Keys are read server-side only — a key
  appearing in frontend code or a URL is a bug, full stop.

## Run (filled in as phases land)
- Phase 4+: one command starts FastAPI (serving API + built frontend + audio). TBD here.
- Phone access: Tailscale app on phone → `http://<mac-tailnet-name>:<port>`. The server
  binds to the Tailscale interface, never 0.0.0.0. TBD exact bind config.

## Backup
- What matters: `data/library/` (regenerable but expensive in time) and the SQLite DB
  (ratings/progress/history — NOT regenerable). Backup plan decided in Phase 2, in place
  before Phase 5's worker runs unattended.

## Definition of "done" for the current milestone
- Phase 0: see TASKS.md §0 gate — repo pushed, ignores proven, smoke test recorded.
