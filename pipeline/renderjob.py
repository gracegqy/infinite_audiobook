"""Render job control + progress (AMENDMENT_06).

Renders run as detached subprocesses (app/server.py spawns `python -m
pipeline.retry`), so the player cannot see into them directly. The
`render_jobs` table is the cross-process channel: the pipeline WRITES progress
and READS control; the server READS progress and WRITES control. WAL already
makes that safe (db.connect).

Control latency is one paragraph: pause/cancel are honored at the next
paragraph boundary, because a paragraph render is not interruptible. At
Kokoro's ~6.9x realtime that is typically a few seconds.

The pure decisions (progress fraction, control→action, staleness) take their
inputs as parameters and live here as the single copy — unit-tested from day
one per CLAUDE.md."""
import dataclasses
import json
import os

# control = what Grace asked for; state = what the render is actually doing.
CONTROLS = ("run", "pause", "cancel")
STATES = ("running", "paused", "done", "cancelled", "failed")
# Phases in walk order. `fetching` has no measurable total (one HTTP GET of a
# whole story) — it reports as indeterminate rather than faking a bar.
PHASES = ("fetching", "tagging", "synthesizing", "encoding")
INDETERMINATE_PHASES = ("fetching", "tagging", "encoding")

POLL_S = 0.5  # pause-loop re-read interval


@dataclasses.dataclass
class RenderJob:
    """Serialized shape shipped to the player — round-trip tested."""
    story_id: str
    phase: str
    control: str
    state: str
    paragraphs_done: int
    paragraphs_total: int | None
    voice: str | None
    pid: int | None
    started_at: str | None = None
    updated_at: str | None = None

    def encode(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False)

    @classmethod
    def decode(cls, s: str) -> "RenderJob":
        return cls(**json.loads(s))

    @classmethod
    def from_row(cls, row) -> "RenderJob":
        return cls(story_id=row["story_id"], phase=row["phase"],
                   control=row["control"], state=row["state"],
                   paragraphs_done=row["paragraphs_done"],
                   paragraphs_total=row["paragraphs_total"],
                   voice=row["voice"], pid=row["pid"],
                   started_at=row["started_at"], updated_at=row["updated_at"])

    def as_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["fraction"] = progress_fraction(self.phase, self.paragraphs_done,
                                          self.paragraphs_total)
        d["active"] = self.state in ("running", "paused")
        return d


# ---- pure logic (no DB, no clock) ----

def progress_fraction(phase: str, done: int, total: int | None) -> float | None:
    """0..1, or None when the phase has no measurable total (an indeterminate
    bar is honest; a fake percentage is not)."""
    if phase in INDETERMINATE_PHASES or not total or total <= 0:
        return None
    return min(1.0, max(0.0, done / total))


def action_for(control: str) -> str:
    """control → what the render loop does at the next paragraph boundary.
    Single copy of this mapping (pipeline checkpoint + tests read it)."""
    if control == "cancel":
        return "cancel"
    if control == "pause":
        return "wait"
    return "continue"


def is_stale(state: str, pid_alive: bool) -> bool:
    """A job whose process died (reboot, kill -9) still reads 'running' in the
    table. Liveness is derived from the pid, never trusted from the row —
    same artifact-over-prose rule the project runs on."""
    return state in ("running", "paused") and not pid_alive


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    return True


# ---- DB accessors ----

def open_job(conn, story_id: str, phase: str = "fetching",
             voice: str | None = None, restore_status: str | None = None,
             pid: int | None = None) -> None:
    """Start (or restart) the job row for a story. Re-opening resets control to
    'run' so a stale 'cancel' from a previous render never kills a new one."""
    conn.execute(
        "INSERT INTO render_jobs(story_id, pid, phase, paragraphs_done, "
        "paragraphs_total, control, state, voice, restore_status, "
        "started_at, updated_at) "
        "VALUES(?,?,?,0,NULL,'run','running',?,?,datetime('now'),datetime('now')) "
        "ON CONFLICT(story_id) DO UPDATE SET "
        "pid=excluded.pid, phase=excluded.phase, paragraphs_done=0, "
        "paragraphs_total=NULL, control='run', state='running', "
        "voice=excluded.voice, restore_status=excluded.restore_status, "
        "started_at=excluded.started_at, updated_at=excluded.updated_at",
        (story_id, pid if pid is not None else os.getpid(), phase, voice,
         restore_status))
    conn.commit()


def set_phase(conn, story_id: str, phase: str,
              paragraphs_total: int | None = None) -> None:
    conn.execute(
        "UPDATE render_jobs SET phase=?, paragraphs_total=COALESCE(?, "
        "paragraphs_total), updated_at=datetime('now') WHERE story_id=?",
        (phase, paragraphs_total, story_id))
    conn.commit()


def set_progress(conn, story_id: str, done: int, total: int | None = None) -> None:
    conn.execute(
        "UPDATE render_jobs SET paragraphs_done=?, paragraphs_total=COALESCE(?, "
        "paragraphs_total), state=CASE WHEN state='paused' THEN 'running' "
        "ELSE state END, updated_at=datetime('now') WHERE story_id=?",
        (done, total, story_id))
    conn.commit()


def set_control(conn, story_id: str, control: str) -> None:
    if control not in CONTROLS:
        raise ValueError(f"bad control {control!r}")
    conn.execute("UPDATE render_jobs SET control=?, updated_at=datetime('now') "
                 "WHERE story_id=?", (control, story_id))
    conn.commit()


def finish(conn, story_id: str, state: str) -> None:
    if state not in STATES:
        raise ValueError(f"bad state {state!r}")
    conn.execute("UPDATE render_jobs SET state=?, control='run', "
                 "updated_at=datetime('now') WHERE story_id=?", (state, story_id))
    conn.commit()


def get(conn, story_id: str) -> RenderJob | None:
    row = conn.execute("SELECT * FROM render_jobs WHERE story_id=?",
                       (story_id,)).fetchone()
    return RenderJob.from_row(row) if row else None


def restore_status_for(conn, story_id: str) -> str | None:
    row = conn.execute("SELECT restore_status FROM render_jobs WHERE story_id=?",
                       (story_id,)).fetchone()
    return row["restore_status"] if row else None


def active(conn, reap: bool = True) -> list[RenderJob]:
    """Active jobs, with dead-process rows reaped first so the player never
    shows a bar for a render that is not running."""
    rows = conn.execute(
        "SELECT * FROM render_jobs WHERE state IN ('running','paused') "
        "ORDER BY started_at").fetchall()
    out = []
    for row in rows:
        job = RenderJob.from_row(row)
        if reap and is_stale(job.state, pid_alive(job.pid)):
            finish(conn, job.story_id, "failed")
            continue
        out.append(job)
    return out


def await_control(conn, story_id: str, sleep) -> str:
    """Block while control='pause'; return 'continue' or 'cancel'.

    `sleep` is injected (never imported time) so tests drive the pause loop
    without real waiting — the clock-as-parameter rule."""
    marked = False
    while True:
        row = conn.execute("SELECT control FROM render_jobs WHERE story_id=?",
                           (story_id,)).fetchone()
        if row is None:
            return "continue"  # job row gone — nothing is controlling this render
        act = action_for(row["control"])
        if act != "wait":
            return act
        if not marked:  # write 'paused' once, not every poll
            conn.execute("UPDATE render_jobs SET state='paused', "
                         "updated_at=datetime('now') WHERE story_id=?", (story_id,))
            conn.commit()
            marked = True
        sleep(POLL_S)
