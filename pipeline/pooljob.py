"""Pool-build job control + progress (Entry 43), the pool-build sibling of
`renderjob`.

Same shape and the same reasons: the build runs as a detached subprocess
(app/server.py spawns `python -m pipeline.buildpool`), so the player cannot see
into it. The `pool_jobs` table is the cross-process channel — the build WRITES
progress and READS control, the server READS progress and WRITES control, and
WAL makes that safe.

What differs from a render, and why this is not just a second story_id column:

  - the unit is a CHANNEL, not a story: a build is what happens *before* any
    story exists, which is precisely the window that used to look like nothing
    happening;
  - only `verifying` has a measurable total, and it is a count of candidates
    rather than paragraphs;
  - there is no pause. A paused render holds a finished file; a paused build
    holds open HTTP walks against Gutenberg, and "stop" is the thing you
    actually want from a phone.

Liveness and the pid rule are imported from `renderjob` rather than restated —
one copy, per CLAUDE.md's centralize-on-the-second-copy rule.
"""
import dataclasses
import json
import os

from .renderjob import is_stale, pid_alive  # noqa: F401  (re-exported)

CONTROLS = ("run", "cancel")
STATES = ("running", "done", "cancelled", "failed")
# Walk order. Only `verifying` can report a fraction: gathering is one catalog
# read, selecting is one model call, and acquiring is a handful of fetches whose
# count is known but whose duration is not. The rest report indeterminate rather
# than fake a bar — renderjob's rule, unchanged.
PHASES = ("gathering", "verifying", "selecting", "acquiring")
INDETERMINATE_PHASES = ("gathering", "selecting", "acquiring")

PHASE_LABELS = {
    "gathering": "finding candidates",
    "verifying": "checking candidates",
    "selecting": "choosing",
    "acquiring": "downloading stories",
}


@dataclasses.dataclass
class PoolJob:
    """Serialized shape shipped to the player — round-trip tested."""
    channel_id: int
    phase: str
    control: str
    state: str
    checked: int
    total: int | None
    usable: int
    pid: int | None
    note: str | None = None
    started_at: str | None = None
    updated_at: str | None = None

    def encode(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False)

    @classmethod
    def decode(cls, s: str) -> "PoolJob":
        return cls(**json.loads(s))

    @classmethod
    def from_row(cls, row) -> "PoolJob":
        return cls(channel_id=row["channel_id"], phase=row["phase"],
                   control=row["control"], state=row["state"],
                   checked=row["checked"], total=row["total"],
                   usable=row["usable"], pid=row["pid"], note=row["note"],
                   started_at=row["started_at"], updated_at=row["updated_at"])

    def as_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["fraction"] = progress_fraction(self.phase, self.checked, self.total)
        d["active"] = self.state == "running"
        d["label"] = PHASE_LABELS.get(self.phase, self.phase)
        return d


# ---- pure logic (no DB, no clock) ----

def progress_fraction(phase: str, checked: int, total: int | None) -> float | None:
    """0..1, or None when the phase has no measurable total."""
    if phase in INDETERMINATE_PHASES or not total or total <= 0:
        return None
    return min(1.0, max(0.0, checked / total))


def action_for(control: str) -> str:
    """control → what the build loop does at the next candidate boundary.
    Single copy of the mapping (the build checks it, the tests read it)."""
    return "cancel" if control == "cancel" else "continue"


# ---- DB accessors ----

def open_job(conn, channel_id: int, phase: str = "gathering",
             pid: int | None = None) -> None:
    """Start (or restart) the job row for a channel. Re-opening resets control
    to 'run' so a stale 'cancel' from a previous build never kills a new one —
    the render's lesson, applied before it could bite here."""
    conn.execute(
        "INSERT INTO pool_jobs(channel_id, pid, phase, checked, total, usable, "
        "control, state, note, started_at, updated_at) "
        "VALUES(?,?,?,0,NULL,0,'run','running',NULL,datetime('now'),datetime('now')) "
        "ON CONFLICT(channel_id) DO UPDATE SET "
        "pid=excluded.pid, phase=excluded.phase, checked=0, total=NULL, "
        "usable=0, control='run', state='running', note=NULL, "
        "started_at=excluded.started_at, updated_at=excluded.updated_at",
        (channel_id, pid if pid is not None else os.getpid(), phase))
    conn.commit()


def set_phase(conn, channel_id: int, phase: str, total: int | None = None) -> None:
    if phase not in PHASES:
        raise ValueError(f"bad phase {phase!r}")
    conn.execute(
        "UPDATE pool_jobs SET phase=?, total=?, updated_at=datetime('now') "
        "WHERE channel_id=?", (phase, total, channel_id))
    conn.commit()


def set_progress(conn, channel_id: int, checked: int, usable: int) -> None:
    conn.execute(
        "UPDATE pool_jobs SET checked=?, usable=?, updated_at=datetime('now') "
        "WHERE channel_id=?", (checked, usable, channel_id))
    conn.commit()


def set_control(conn, channel_id: int, control: str) -> None:
    if control not in CONTROLS:
        raise ValueError(f"bad control {control!r}")
    conn.execute("UPDATE pool_jobs SET control=?, updated_at=datetime('now') "
                 "WHERE channel_id=?", (control, channel_id))
    conn.commit()


def cancelled(conn, channel_id: int) -> bool:
    """The build's own checkpoint, read between candidates."""
    row = conn.execute("SELECT control FROM pool_jobs WHERE channel_id=?",
                       (channel_id,)).fetchone()
    return bool(row) and action_for(row["control"]) == "cancel"


def finish(conn, channel_id: int, state: str, note: str | None = None) -> None:
    if state not in STATES:
        raise ValueError(f"bad state {state!r}")
    conn.execute("UPDATE pool_jobs SET state=?, control='run', note=?, "
                 "updated_at=datetime('now') WHERE channel_id=?",
                 (state, note, channel_id))
    conn.commit()


def get(conn, channel_id: int) -> PoolJob | None:
    row = conn.execute("SELECT * FROM pool_jobs WHERE channel_id=?",
                       (channel_id,)).fetchone()
    return PoolJob.from_row(row) if row else None


def active(conn, reap: bool = True) -> list[PoolJob]:
    """Running builds, with dead-process rows reaped first so a bar on screen
    always means a build that is actually walking."""
    rows = conn.execute("SELECT * FROM pool_jobs WHERE state='running' "
                        "ORDER BY started_at").fetchall()
    out = []
    for row in rows:
        job = PoolJob.from_row(row)
        if reap and is_stale(job.state, pid_alive(job.pid)):
            finish(conn, job.channel_id, "failed",
                   "the build process died (reboot, or killed)")
            continue
        out.append(job)
    return out
