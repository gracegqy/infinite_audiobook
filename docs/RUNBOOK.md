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
  pool candidate) · `-m pipeline.retry <id> [--voice v]` = $0 re-run ·
  `-m pipeline.mark read|skip "<title>"` = pre-marking.
- Queue worker (Phase 5): `.venv/bin/python -m pipeline.worker` — one cycle;
  `--loop` re-checks every `WORKER_INTERVAL_S`. Consumes the already-paid pool at
  $0 and never spends on its own.
- Pool refill: `-m pipeline.run_story --build-pool`. **Cost depends on
  `curation_mode` in Settings** (Entry 32), not on the flag:
  `free` = $0 · `free_llm` ≈ $0.02 · `llm` ≈ $2 at `POOL_BATCH_SIZE = 40`.
  A paid build estimated over `CURATION_SPEND_CONFIRM_USD` prints the estimate
  and aborts unless re-run with `--yes-spend`.
  Free modes draw on `pipeline/sources.py`; if no registered source covers the
  active channel the build stops and names the reasons rather than running empty.

## Backup
- What matters: `data/library/` (regenerable but expensive in time) and the SQLite DB
  (ratings/progress/history — NOT regenerable).
- `.venv/bin/python scripts/backup_db.py [--keep N]` → WAL-consistent snapshot in
  `backups/` (gitignored), verified with `PRAGMA integrity_check` and row counts,
  keeping the last 10. Uses sqlite3's backup API, not `cp` — copying a WAL database
  mid-write can capture a torn state.
- **Same machine only.** Covers corruption and bad migrations, not losing the Mac,
  and nothing schedules it. Off-machine copy + a schedule are Phase 7 (TASKS §7).

## Definition of "done" for the current milestone
- Phase 0: see TASKS.md §0 gate — repo pushed, ignores proven, smoke test recorded.
