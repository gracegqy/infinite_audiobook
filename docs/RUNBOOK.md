# RUNBOOK — infinite_audiobook

Operating manual for the running system.

**Verification status (Entry 38):** the scheduler, backup and budget commands below
were run and their output checked. The cold-start sequence, key rotation and restore
are written from the code and have **not** been executed end-to-end — the cold-start
test is itself the Phase 7 gate, and it is still owed.

## Resume prompt (paste into any new session)

> Resume infinite_audiobook (~/Code/ACTIVE/infinite_audiobook). Before acting, read STATE.md,
> the latest JOURNAL.md entries, and the current phase in TASKS.md. Trust artifacts over
> prose: re-inspect anything marked [IN PROGRESS], and re-verify any status lacking
> recorded evidence by running its check. Then continue from STATE's "Next actions"
> toward the current phase's gate. Never start work past an unanswered gate — if a gate
> needs me (review, listening test, phone-over-Tailscale test), set everything up and
> tell me exactly what to do. End with the session-close ritual in CLAUDE.md: journal
> entry, STATE reconciled, commit and push.

For a *fresh phase kickoff* (previous gate just cleared), prefer that phase's tailored
prompt in TASKS.md.

## Cold start (new machine, or this one from nothing)

The gate for Phase 7 is that this section alone gets a working system.

```
git clone https://github.com/gracegqy/infinite_audiobook.git
cd infinite_audiobook
python3 -m venv .venv                       # built and verified on Python 3.12
.venv/bin/pip install -r requirements.txt   # kokoro pulls torch — several minutes, ~2 GB
```

Then, in order:

1. **Keys.** Create `.env` at the repo root (gitignored, never committed):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   OPENAI_API_KEY=sk-...
   ```
   `OPENAI_API_KEY` is only the per-story TTS fallback; English/French run free on
   local Kokoro and Chinese on edge-tts, so a missing OpenAI key degrades rather
   than blocks.
2. **Database.** No migration step to run — `db.connect()` creates every table on
   first use (`CREATE TABLE IF NOT EXISTS`) and applies its own migrations. To
   restore instead of starting empty, see **Restoring from a backup** below.
3. **Frontend.** `scripts/serve.sh` builds `app/frontend/dist/` on first run if it is
   missing (`npm install && npm run build`). Requires Node; nothing else does.
4. **Tailscale.** Install and sign in on both Mac and phone. `scripts/serve.sh`
   resolves the live IP via the `tailscale` CLI. If that CLI is missing it falls back
   to `$HR_TAILSCALE_IP` **with a warning**, and if that is unset too it **refuses to
   start** (exit 2) rather than guess a bind address. The fallback is this machine's
   address, so seeing the warning on a *new* machine means the IP is wrong.
5. **Start it:** `scripts/serve.sh`, then open the printed URL on the phone.

### Environment

`.env` carries the two API keys (above). These optional variables are read from the
process environment (`config.py`); each is machine-specific or personal, which is why
none of them is a committed constant:

| variable | effect when unset | notes |
|---|---|---|
| `HR_TAILSCALE_IP` | `serve.sh` exits 2 if the `tailscale` CLI is also missing | fallback bind address only; the live CLI value always wins |
| `HR_CONTACT_EMAIL` | the outbound `User-Agent` drops its contact clause | politeness contact for Gutenberg / wiki fetches |
| `HR_DATA_DIR` | state lives in `./data` | redirects db + library + interim at once; how sandboxed runs avoid the real library |

`data/` is not in the repo, by design — no story text or audio is ever committed. A
cold-started machine has an empty library and refills through the pool (below).

## Accounts & identity

- Repo: `https://github.com/gracegqy/infinite_audiobook` (personal account `gracegqy`;
  commit identity Grace / gracegumails@gmail.com — the 2026-07 commits carry the
  uchicago address, accepted in Entry 39; HTTPS + macOS keychain credential). Visibility
  is whatever GitHub says, not what this line remembers.
- **Claude Code's filesystem sandbox blocks `git push`** — `credential.helper` is
  `osxkeychain` and keychain reads are denied, so the helper returns nothing and git
  tries to prompt on a non-TTY ("could not read Username… Device not configured").
  Pushing from your own terminal always works; an agent session needs a sandbox
  override for that one command.
- API keys live in `.env`, read server-side only. **A key appearing in frontend code,
  a URL, or the Settings screen is a bug, full stop** — `data/app.db` is copied into
  `backups/` unencrypted, so a key stored in settings would turn every snapshot into
  a credential.

### Key rotation

1. Issue the new key on the provider dashboard (console.anthropic.com /
   platform.openai.com); leave the old one live.
2. Edit `.env` — it is the only place either key is read from.
3. Restart the server (`Ctrl-C`, `scripts/serve.sh`). Both the server and the worker
   read `.env` at process start, so a running process keeps the old key. If the
   scheduler is installed, bounce the loop too — `scripts/scheduler.sh uninstall`
   then `install` is the path this runbook can vouch for. (`launchctl kickstart -k
   gui/$UID/com.gracegu.infinite-audiobook.worker` should also work but is untested,
   since the job has never been installed.)
4. Verify before revoking: a `$0` re-render proves the OpenAI path
   (`-m pipeline.retry <id>` only calls OpenAI on fallback), and
   `-m pipeline.run_story --build-pool` on `free_llm` proves the Anthropic path for
   about $0.05.
5. Revoke the old key.
6. Set spend caps on both provider dashboards. The app's own cap (below) cannot see
   the provider balance — it only knows what this app spent.

## Run

- **App server:** `scripts/serve.sh` — binds the Tailscale interface **only**, never
  `0.0.0.0` (DESIGN §1 / negative spec §10). Prints `serving on http://<ip>:8123`.
- **Phone:** Tailscale connected → `http://<mac-tailscale-ip>:8123` in Safari (the URL
  `serve.sh` prints; `tailscale ip -4` on the Mac gives the same address), or the
  saved home-screen PWA. Phone-over-Tailscale is the definition of "working" for
  anything player-facing; desktop localhost does not count.
- **Queue worker:** `.venv/bin/python -m pipeline.worker` runs one cycle;
  `--loop` cycles on the `worker_interval_s` setting, re-read every cycle;
  `--acquire-only` takes from the pool without rendering. **The worker never
  spends** (AMENDMENT_04 A) — it consumes the already-paid pool and stops with a
  message when the pool is empty.
- **Pipeline, by hand:** `-m pipeline.run_story` (ingest the next pool candidate) ·
  `-m pipeline.retry <id> [--voice v]` = $0 re-render ·
  `-m pipeline.mark read|skip "<title>"` = pre-marking.
- **Voice audition samples:** `.venv/bin/python scripts/render_voice_samples.py` →
  `data/voice_samples/` (one-time; $0 for en/fr, zh calls edge-tts).
- **Never point scripts or browser automation at the live server or `data/`** — use
  `scripts/ui_sandbox.sh` (a DB snapshot on 127.0.0.1) or `HR_DATA_DIR`. Before
  restarting the server, check whether you are listening: `progress.updated_at`
  advancing means a live client.

### Pool refill (the only thing that spends)

```
.venv/bin/python -m pipeline.run_story --build-pool
```

Cost depends on `curation_mode` in Settings, not on the flag:

| mode | cost at `POOL_BATCH_SIZE = 40` | notes |
|---|---|---|
| `free` | $0 | no model call — so it cannot use the taste profile at all |
| `free_llm` | **$0.0512** (measured, Entry 37) | current setting |
| `llm` | ~$2.40 | web search fees scale with batch size |

Free modes draw on the registry in `pipeline/sources.py`; if no registered source
covers the active channel the build stops and names the reasons rather than running
empty. A paid build estimated over `CURATION_SPEND_CONFIRM_USD` ($1.00) prints the
estimate and aborts unless re-run with `--yes-spend`.

## Scheduler (launchd) — **Grace runs this, never Claude**

`install` writes a plist outside the repo and starts a background process that
survives reboots and renders audio unattended. The script refuses to run
non-interactively (exit 3), which is the shape an agent invocation has.

```
bash scripts/scheduler.sh status      # loaded? and the operative cadence
bash scripts/scheduler.sh install     # load the job; starts immediately
bash scripts/scheduler.sh uninstall   # unload and remove
tail -f data/interim/worker_loop.log  # confirm it is working, not just loaded
```

- Runs from any directory (fixed Entry 38 — `status` used to need the repo root).
- **The plist carries no cadence.** Its only duty is keeping `worker --loop` alive;
  how often the loop cycles is `worker_interval_s` in Settings, re-read every cycle,
  so changing it applies on the next tick with no reinstall and no plist edit.
- `-u` in the plist's ProgramArguments is load-bearing: launchd redirects stdout to a
  file and Python block-buffers a non-tty, so without it the log stays empty for
  hours and an unattended job looks broken.
- Because the worker cannot spend, a scheduler running unattended cannot run up a
  bill.

## Settings (the app's Settings tab, or `PUT /api/settings`)

Every operational knob is a DB row, not a constant — the code defaults are first-run
fallbacks only, and `GET /api/settings` reports the operative value.

| setting | meaning | notes |
|---|---|---|
| `curation_mode` | `free` / `free_llm` / `llm` | only the two `*_llm` modes can use the taste profile |
| `curation_model` | curation model id | default `claude-sonnet-5` |
| `default_voice.<lang>` | TTS voice per language | en = `am_adam` |
| `worker_interval_s` | loop cadence | minimum 60s — the loop fetches and runs TTS |
| `spend_cap_usd` | rolling cap | **0 means unlimited** |
| `spend_cap_period` | `day` / `week` / `month` | rolling window over the `curation_runs` ledger |
| `backup_interval_s` | automatic snapshot cadence | 0 disables automatic snapshots |
| `backup_offsite_dir` | off-machine destination | **empty = OFF**, which is the default |

### Spend cap

Enforced before **every** paid path including `free_llm` — a guard that only covers
the expensive path is how the cheap path becomes the leak. It is a rolling window
over the `curation_runs` ledger, compared in UTC (what `CURRENT_TIMESTAMP` writes).
`pipeline.budget.status()` is the single source for both the Settings readout and
the guard, so the screen cannot show a different number than the one enforced.

```
.venv/bin/python -c "from pipeline import db, budget; print(budget.status(db.connect()))"
```

A breach raises `CapExceeded` and the build exits 4 having spent $0.

**Sizing note:** the cap counts what the ledger holds, including old experiments. It
is currently $8.00/month against $4.86 already in the window (July's `llm` runs), so
a $2 cap would refuse every build on arrival. Lower it once those age out (~2026-08-27).

## Backup

What matters is the **SQLite DB** — ratings, progress, history, none of it
regenerable. `data/library/` is deliberately *not* backed up: it is regenerable from
the DB, at the cost of re-rendering time.

```
.venv/bin/python -m pipeline.backup [--keep N] [--local-only]
```

WAL-consistent snapshot into `backups/` (gitignored), verified with
`PRAGMA integrity_check` and row counts, keeping the last 10. Uses sqlite3's backup
API, not `cp` — copying a WAL database mid-write can capture a torn state. The worker
also calls this on `backup_interval_s`.

### Off-machine copy — **OFF by default, opt-in**

Nothing leaves the Mac until you type a path into `backup_offsite_dir` in Settings;
blank turns it off, and the local snapshot is unaffected. The path is not validated
for existence, because it may be an external disk or a network mount that is not
attached right now.

The copy is **verified at the destination** (integrity check + row count), not
trusted — a cloud-sync folder can accept a write and then fail to materialise it, and
an unverified off-machine backup is the kind discovered to be empty on the day it is
needed. A failed off-machine copy warns loudly and keeps the local snapshot.

> A cloud folder such as iCloud Drive is an ordinary local directory from inside the
> tooling — a plain file copy, no authentication, with the sync daemon uploading it
> afterwards. That is exactly why the destination is a human decision and why this
> setting ships empty (Entry 37).

**Local snapshots alone do not survive losing the Mac.** They cover corruption and
bad migrations. Until `backup_offsite_dir` is set, that is the accepted risk.

### Restoring from a backup

```
cp backups/app-<stamp>.db data/app.db     # server stopped
```
Delete any stale `data/app.db-wal` / `-shm` alongside it. Story text and audio under
`data/library/` are referenced by the DB — restoring an older DB does not delete
files, but a story added after that snapshot becomes invisible to the app.

## Troubleshooting

| symptom | cause / fix |
|---|---|
| Phone can't reach the app | Tailscale disconnected on either device; or serve.sh printed the fallback-IP warning. Re-check the printed URL. |
| Worker log empty for hours | the `-u` flag is missing from the plist — reinstall via `scheduler.sh`. |
| `scheduler.sh status` says `loaded: no` after install | check `launchctl list \| grep horror`; the plist may have failed to load. |
| Pool build exits 4, $0 spent | spend cap breached. Raise `spend_cap_usd` or wait for the window to roll. |
| Pool build stops naming a channel | no registered free source covers it — use `llm` mode or add an adapter. |
| A story renders with random pauses | hard-wrapped source text reaching TTS; the clean stage must unwrap lines within paragraphs (probe 1b). |
| A finished story "resumes" to its end and instantly pauses | end-of-file persisted as a resume point — on `ended` the position must be cleared and the story marked read (Entry 10). |
| `afconvert`: "format 'aac' is unknown" under a sandbox | Mach lookups blocked; needs `sandbox.network.allowMachLookup` for `com.apple.audio.*` and `com.apple.coremedia.*` (Entry 37). |

## Definition of "done" for the current milestone

**Phase 7 — hardening & audit** (TASKS §7). Gate: an audit report exists; every severe
finding fixed or explicitly risk-accepted in JOURNAL; **a cold-start test from this
runbook alone succeeds**. Still owed at Entry 38: the independent `/code-review`,
`/security-review`, the fresh-session audit, and the cold-start test itself — this
section is written but has not been executed end-to-end on a clean machine.

Phase 6 is also re-opened: its gate passed at batch 12, production is batch 40.
