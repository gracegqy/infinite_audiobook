"""Replenishment worker (DESIGN §7, TASKS Phase 5): keeps the ACTIVE channel's
queue at QUEUE_DEPTH unread stories, at $0 marginal cost.

Cycle, in two stages so the cheap half always runs first:
  1. ACQUIRE — while unread < depth, take the next pool candidate (already paid
     for, AMENDMENT_04 A), fetch/clean/tag it to `text_ready`. The story is
     queue-visible and skippable here, having cost one HTTP GET.
  2. RENDER — synthesize the `text_ready` stories in acquisition order. A skip
     between the two stages costs a fetch, not a ~4.5-min render.

Dedup is all-time: pool.pool_candidates excludes any title already in
`stories` (any status — read, skipped, failed and pre-marked rows all count),
and ingest re-checks the content dedup key after fetching. Nothing repeats.

Never spends money on its own: an empty pool ends the cycle with a message.
Refilling is Grace's explicit `run_story --build-pool` (AMENDMENT_04 A).

Run: .venv/bin/python -m pipeline.worker            # one cycle
     .venv/bin/python -m pipeline.worker --loop     # cycle on the Settings cadence
     .venv/bin/python -m pipeline.worker --acquire-only
"""
import sys
import time

from . import backup, config, db, fetch, ingest, pool, synthesize

# Acquired-but-not-started. `in_progress` is started, so it does not count
# toward the unread queue; read/skipped/failed are history.
UNREAD_STATUSES = ("text_ready", "ready")


# ---- pure logic (DB state and clock as parameters) ----

def unread_shortfall(unread: int, depth: int) -> int:
    """How many stories the queue is short. The single copy of the
    replenishment decision — everything else reads this."""
    return max(0, depth - unread)


def needs_replenishment(unread: int, depth: int) -> bool:
    return unread_shortfall(unread, depth) > 0


def eligible(candidates: list[dict], enabled_source_classes) -> list[dict]:
    """Pool order, minus candidates we cannot even attempt: a source class with
    no fetcher yet (r/NoSleep until its OAuth fetcher exists — probe 4), or a
    reference too incomplete to fetch. Both are skipped WITHOUT a history row,
    so the story stays available to a later batch with a usable reference."""
    return [c for c in candidates
            if c.get("source_class") in enabled_source_classes
            and fetch.usable_ref(c)]


# ---- DB reads ----

def unread_count(conn, channel_id: int) -> int:
    qs = ",".join("?" * len(UNREAD_STATUSES))
    return conn.execute(
        f"SELECT COUNT(*) AS n FROM stories WHERE channel_id=? "
        f"AND status IN ({qs})", (channel_id, *UNREAD_STATUSES)).fetchone()["n"]


def pending_renders(conn, channel_id: int) -> list[str]:
    """text_ready stories in acquisition order — the render queue."""
    return [r["id"] for r in conn.execute(
        f"SELECT id FROM stories WHERE channel_id=? AND status='text_ready' "
        f"ORDER BY {db.ACQUISITION_ORDER}", (channel_id,))]


# ---- the cycle ----

def acquire_stage(conn, channel, log=print) -> dict:
    depth = config.QUEUE_DEPTH
    acquired, skipped = [], []
    candidates = eligible(pool.pool_candidates(conn, channel_id=channel["id"]),
                          fetch.ENABLED_SOURCE_CLASSES)
    i = 0
    while needs_replenishment(unread_count(conn, channel["id"]), depth):
        if i >= len(candidates):
            log(f"[worker] pool exhausted — {unread_count(conn, channel['id'])}"
                f"/{depth} unread. Refill: python -m pipeline.run_story "
                "--build-pool (PAID)")
            break
        c = candidates[i]
        i += 1
        log(f"[worker] acquiring: {c['title']} — {c.get('author') or 'unknown'}")
        try:
            acquired.append(ingest.acquire_candidate(conn, c, channel))
        except ingest.DuplicateStory:
            log(f"[worker] skip (already in history): {c['title']}")
            skipped.append(c["title"])
        except Exception as e:
            # a bad candidate must never wedge the queue: it is recorded as
            # failed history (so it is never re-proposed) and the cycle moves on
            log(f"[worker] skip (failed): {c['title']} — {e}")
            skipped.append(c["title"])
    return {"acquired": acquired, "skipped": skipped}


def render_stage(conn, channel, log=print, render=None) -> dict:
    render = render or ingest.render_ready_story
    rendered, failed = [], []
    for sid in pending_renders(conn, channel["id"]):
        log(f"[worker] rendering {sid}")
        try:
            render(conn, sid)
            rendered.append(sid)
        except synthesize.AbortRender as e:
            # skipped/cancelled mid-render — intended, not a failure
            log(f"[worker] render stopped for {sid}: {e}")
        except Exception as e:
            log(f"[worker] render FAILED for {sid}: {e}")
            failed.append(sid)
    return {"rendered": rendered, "failed": failed}


def cycle(conn, log=print, acquire_only: bool = False) -> dict:
    channel = db.active_channel(conn)
    before = unread_count(conn, channel["id"])
    log(f"[worker] channel={channel['name']} unread={before}/{config.QUEUE_DEPTH}")
    if not needs_replenishment(before, config.QUEUE_DEPTH) \
            and not pending_renders(conn, channel["id"]):
        log("[worker] queue healthy — nothing to do")
        return {"channel": channel["name"], "before": before, "after": before,
                "acquired": [], "skipped": [], "rendered": [], "failed": []}

    out = {"channel": channel["name"], "before": before,
           **acquire_stage(conn, channel, log=log),
           **({"rendered": [], "failed": []} if acquire_only
              else render_stage(conn, channel, log=log))}
    out["after"] = unread_count(conn, channel["id"])
    log(f"[worker] done — unread {before} → {out['after']}/{config.QUEUE_DEPTH}; "
        f"acquired {len(out['acquired'])}, rendered {len(out['rendered'])}")
    return out


def loop_iteration(conn, log=print, acquire_only: bool = False,
                   backup_fn=None, sleep_fn=None) -> int:
    """One turn of the `--loop` body, extracted so a test can execute every
    statement in it and returning the interval it waited.

    Why it is a function at all (audit 2026-08-07, BUG-1): the backup line below
    called a module that was never imported, so `--loop` died with a NameError
    on its FIRST iteration — the backup schedule Entry 37 believed it had
    shipped has never once run. Nothing caught it because the loop lived inside
    `main` and `main` had no test. The invariant this function exists to hold:
    **every statement inside the loop runs in at least one test.**
    """
    try:
        cycle(conn, log=log, acquire_only=acquire_only)
    except Exception as e:  # a bad cycle must not kill the loop
        log(f"[worker] cycle error: {e}")
    # Entry 37: the loop is the only thing that runs unattended, so it is
    # also what carries the backup schedule Phase 7 owed. maybe_backup
    # swallows its own failures for the same reason as the line above.
    (backup_fn or backup.maybe_backup)(conn)
    # Entry 37: re-read the interval EVERY cycle rather than capturing it
    # once. This is what makes the cadence editable from Settings — a
    # captured value would need a restart, and the scheduler keeps this
    # process alive for weeks. It is also why the launchd job carries no
    # interval of its own: its only job is to keep the loop running.
    interval = db.effective_worker_interval_s(conn)
    (sleep_fn or time.sleep)(interval)
    return interval


def main(argv: list[str]) -> int:
    conn = db.connect()
    acquire_only = "--acquire-only" in argv
    if "--loop" not in argv:
        cycle(conn, acquire_only=acquire_only)
        return 0
    print(f"[worker] loop starting at {db.effective_worker_interval_s(conn)}s "
          "— Ctrl-C to stop")
    while True:
        loop_iteration(conn, acquire_only=acquire_only)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
