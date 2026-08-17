"""Pool build as a background job, driven from the app (Entry 43).

This is `run_story --build-pool` with two differences and no new authority:

  1. it reports progress into `pool_jobs` so the phone can see the walk, and
     reads `control` so the phone can stop it;
  2. it continues into ONE worker acquire+render cycle, so a build that
     succeeds ends with stories rendering instead of with a full pool and a
     still-empty queue.

**It does not decide to spend.** AMENDMENT_04 A allows builds that are
"Grace-initiated only", and the initiation is the button press that spawned this
process — the server checks coverage, the spend cap, and (over
CURATION_SPEND_CONFIRM_USD) an explicit approval BEFORE spawning, exactly as the
CLI checks them before calling. `--approved-spend` carries that decision in; this
module never infers it, and without it an expensive mode refuses here too rather
than trusting the caller.

Run (the server does this; you can too):
    .venv/bin/python -m pipeline.buildpool --channel 2
"""
import sys

from . import (budget, config, curate, db, freepool, ingest, pooljob, worker)


class Progress:
    """The build's view of its own job row. Passed into freepool.build_pool,
    which knows nothing about tables — it just calls these three."""

    def __init__(self, conn, channel_id: int):
        self.conn, self.channel_id = conn, channel_id

    def phase(self, phase: str, total: int | None = None) -> None:
        pooljob.set_phase(self.conn, self.channel_id, phase, total)

    def verified(self, checked: int, usable: int) -> None:
        pooljob.set_progress(self.conn, self.channel_id, checked, usable)

    def cancelled(self) -> bool:
        return pooljob.cancelled(self.conn, self.channel_id)


def estimate_for(conn, mode: str) -> tuple[float, str]:
    """(usd, how) for a build in `mode` at the production batch size. The single
    copy — the server quotes this on the button and this module re-checks it, so
    the number on screen and the number enforced cannot drift (the budget
    lesson, Entry 37)."""
    if mode == "free":
        return 0.0, "no model call at all"
    if mode == "free_llm":
        return curate.estimate_selection_cost(config.POOL_BATCH_SIZE)
    return curate.estimate_cost(db.effective_curation_model(conn),
                                config.POOL_BATCH_SIZE)


def run(conn, channel, approved_spend: bool = False, log=print) -> int:
    """One build + one worker cycle, with the job row narrating. Returns the
    process exit code."""
    cid = channel["id"]
    mode = db.effective_curation_mode(conn)
    log(f"[buildpool] channel={channel['name']} curation_mode={mode}")
    pooljob.open_job(conn, cid, phase="gathering")

    est, how = estimate_for(conn, mode)
    if mode != "free":
        try:
            budget.check(conn, est)
        except budget.CapExceeded as e:
            pooljob.finish(conn, cid, "failed", str(e))
            log(f"ERROR: {e} (estimate: {how})")
            return 4
    if est > config.CURATION_SPEND_CONFIRM_USD and not approved_spend:
        # The same second word the CLI demands (`--yes-spend`). A button that
        # could quietly start a $2.40 build would make "Grace-initiated" mean
        # "Grace-initiated something, once".
        note = (f"a build in {mode} mode is estimated at ${est:.2f} "
                f"({how}) — approve the spend to start it")
        pooljob.finish(conn, cid, "failed", note)
        log(f"ERROR: {note}")
        return 3

    try:
        progress = Progress(conn, cid)
        if mode in ("free", "free_llm"):
            freepool.build_pool(conn, channel, limit=config.POOL_BATCH_SIZE,
                                use_llm=(mode == "free_llm"), log=log,
                                progress=progress)
        else:
            # The paid path has no progress hooks of its own (it is one long
            # model call, not a walk), so the bar stays indeterminate here
            # rather than inventing steps.
            progress.phase("selecting")
            curate.run_curation(conn, channel, batch=config.POOL_BATCH_SIZE)
    except Exception as e:
        pooljob.finish(conn, cid, "failed", f"{type(e).__name__}: {e}")
        log(f"ERROR: build failed — {type(e).__name__}: {e}")
        return 1

    if pooljob.cancelled(conn, cid):
        pooljob.finish(conn, cid, "cancelled",
                       "stopped during verification; verified candidates kept")
        log("[buildpool] cancelled — verified candidates kept, nothing acquired")
        return 0

    # Acquisition is the worker's $0 path and needs no separate permission —
    # it is what the scheduler does unattended today. Chaining it is the whole
    # point: a full pool and an empty queue still looks like nothing happened.
    pooljob.set_phase(conn, cid, "acquiring")
    try:
        out = worker.acquire_stage(conn, channel, log=log)
        pooljob.set_progress(conn, cid, len(out["acquired"]),
                             len(out["acquired"]))
        pooljob.finish(conn, cid, "done",
                       f"acquired {len(out['acquired'])} story(ies)")
    except Exception as e:
        pooljob.finish(conn, cid, "failed",
                       f"pool built, acquisition failed: {type(e).__name__}: {e}")
        log(f"ERROR: acquisition failed — {type(e).__name__}: {e}")
        return 1

    # Renders open their own render_jobs rows, so RenderBar takes the story from
    # here and this job is already `done` — the pool bar must not sit at 100%
    # for the half hour a render takes.
    worker.render_stage(conn, channel, log=log, render=ingest.render_ready_story)
    return 0


def main(argv: list[str]) -> int:
    conn = db.connect()
    if "--channel" in argv:
        cid = int(argv[argv.index("--channel") + 1])
        row = conn.execute("SELECT * FROM channels WHERE id=?", (cid,)).fetchone()
        if row is None:
            print(f"ERROR: no channel {cid}", file=sys.stderr)
            return 2
    else:
        row = db.active_channel(conn)
    return run(conn, row, approved_spend="--approved-spend" in argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
