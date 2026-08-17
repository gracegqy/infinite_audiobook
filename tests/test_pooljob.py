"""Pool-build job control + progress (Entry 43).

The properties worth pinning are the ones that keep a bar honest: a fraction
only where a total exists, liveness derived from the pid rather than trusted
from the row, and a re-opened job never inheriting a stale cancel.
"""
import pytest

from pipeline import db, pooljob


@pytest.fixture()
def conn(tmp_path):
    return db.connect(tmp_path / "app.db")


def test_roundtrip_survives_encode_decode():
    """Every serialized shape gets this test the day it is written (CLAUDE.md)."""
    job = pooljob.PoolJob(channel_id=1, phase="verifying", control="run",
                          state="running", checked=12, total=79, usable=4,
                          pid=999, note=None, started_at="t", updated_at="t")
    assert pooljob.PoolJob.decode(job.encode()) == job


@pytest.mark.parametrize("phase,checked,total,expected", [
    ("verifying", 0, 79, 0.0),
    ("verifying", 40, 80, 0.5),
    ("verifying", 99, 80, 1.0),      # clamped, never over 100%
    ("verifying", 5, None, None),    # no total yet → indeterminate
    ("verifying", 5, 0, None),
    ("gathering", 5, 79, None),      # one catalog read has no steps
    ("selecting", 5, 79, None),      # one model call has no steps
    ("acquiring", 1, 3, None),
])
def test_fraction_only_where_a_total_exists(phase, checked, total, expected):
    assert pooljob.progress_fraction(phase, checked, total) == expected


def test_control_maps_to_one_action():
    assert pooljob.action_for("cancel") == "cancel"
    assert pooljob.action_for("run") == "continue"
    # anything unrecognised keeps working rather than stopping a live build
    assert pooljob.action_for("nonsense") == "continue"


def test_open_clears_a_stale_cancel(conn):
    """A cancel left over from the previous build must never kill a new one —
    the render's Entry-27 lesson, applied before it could bite here."""
    pooljob.open_job(conn, 1)
    pooljob.set_control(conn, 1, "cancel")
    assert pooljob.cancelled(conn, 1)
    pooljob.open_job(conn, 1)
    assert not pooljob.cancelled(conn, 1)
    assert pooljob.get(conn, 1).state == "running"


def test_open_resets_counters_and_note(conn):
    pooljob.open_job(conn, 1)
    pooljob.set_phase(conn, 1, "verifying", total=50)
    pooljob.set_progress(conn, 1, 30, 9)
    pooljob.finish(conn, 1, "failed", "network died")
    pooljob.open_job(conn, 1)
    job = pooljob.get(conn, 1)
    assert (job.checked, job.usable, job.total, job.note) == (0, 0, None, None)


def test_phase_and_state_reject_garbage(conn):
    pooljob.open_job(conn, 1)
    with pytest.raises(ValueError):
        pooljob.set_phase(conn, 1, "hallucinating")
    with pytest.raises(ValueError):
        pooljob.finish(conn, 1, "vibing")
    with pytest.raises(ValueError):
        pooljob.set_control(conn, 1, "pause")  # a build has no pause


def test_active_reaps_a_job_whose_process_died(conn):
    """A killed build still reads 'running'. A bar on screen has to mean a
    build that is actually walking, so liveness comes from the pid."""
    pooljob.open_job(conn, 1, pid=2 ** 22)  # far above any real pid
    assert pooljob.active(conn) == []
    job = pooljob.get(conn, 1)
    assert job.state == "failed" and "died" in job.note


def test_active_keeps_a_live_job(conn):
    pooljob.open_job(conn, 1)  # defaults to this process's pid
    assert [j.channel_id for j in pooljob.active(conn)] == [1]


def test_as_dict_carries_a_label_and_liveness(conn):
    pooljob.open_job(conn, 1)
    pooljob.set_phase(conn, 1, "verifying", total=10)
    pooljob.set_progress(conn, 1, 5, 2)
    d = pooljob.get(conn, 1).as_dict()
    assert d["fraction"] == 0.5 and d["active"] is True
    assert d["label"] == "checking candidates"
    pooljob.finish(conn, 1, "done", "acquired 3 story(ies)")
    assert pooljob.get(conn, 1).as_dict()["active"] is False
