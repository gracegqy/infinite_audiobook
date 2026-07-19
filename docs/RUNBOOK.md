# RUNBOOK — horror_readaloud   *(stub — grows with each phase; completed at Phase 7)*

## Resume prompt (paste into any new session)

> Resume horror_readaloud (~/Code/ACTIVE/horror_readaloud). Before acting, read STATE.md,
> the latest JOURNAL.md entries, and the current phase in TASKS.md. Trust artifacts over
> prose: re-inspect anything marked [IN PROGRESS], and re-verify any status lacking
> recorded evidence by running its check. Then continue from STATE's "Next actions"
> toward the current phase's gate. Never start work past an unanswered gate — if a gate
> needs me (review, listening test, phone-over-Tailscale test), set everything up and
> tell me exactly what to do. End with the session-close ritual in CLAUDE.md: journal
> entry, STATE reconciled, commit and push.

For a *fresh phase kickoff* (previous gate just cleared), prefer that phase's tailored
prompt in TASKS.md.

## Accounts & identity
- Repo: private, `https://github.com/gracegqy/horror_readaloud` (personal account
  `gracegqy`; commit identity Grace / graceguqianying@uchicago.edu; HTTPS + macOS
  keychain credential).
- API keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` in `.env` at repo root (gitignored).
  Set spend caps on both provider dashboards. Keys are read server-side only — a key
  appearing in frontend code or a URL is a bug, full stop.

## Run (filled in as phases land)
- **App server (Phase 4):** `scripts/serve.sh` — resolves the Mac's Tailscale IP
  (fallback: `TAILSCALE_IP_FALLBACK` in pipeline/config.py), builds the frontend once
  if `app/frontend/dist/` is missing, then runs uvicorn on
  `http://<tailscale-ip>:8123` bound to that interface only, never 0.0.0.0.
- Phone access: Tailscale app on phone connected → open `http://100.117.147.107:8123`
  in Safari (or the saved home-screen PWA). The IP is printed by serve.sh at start.
- Voice audition samples (one-time, $0 for en/fr; zh calls edge-tts):
  `.venv/bin/python scripts/render_voice_samples.py` → data/voice_samples/.
- Pipeline (Phase 3): `.venv/bin/python -m pipeline.run_story` (announce → ingest next
  pool candidate) · `--build-pool` = paid curation, Grace-initiated only ·
  `-m pipeline.retry <id> [--voice v]` = $0 re-run · `-m pipeline.mark read|skip
  "<title>"` = pre-marking.

## Backup
- What matters: `data/library/` (regenerable but expensive in time) and the SQLite DB
  (ratings/progress/history — NOT regenerable). Backup plan decided in Phase 2, in place
  before Phase 5's worker runs unattended.

## Definition of "done" for the current milestone
- Phase 0: see TASKS.md §0 gate — repo pushed, ignores proven, smoke test recorded.
