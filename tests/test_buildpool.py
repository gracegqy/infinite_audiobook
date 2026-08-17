"""Pool builds started from the app (Entry 43).

AMENDMENT_04 A allows builds that are "Grace-initiated only" and requires that
an empty pool produce "a notice with the cost estimate". A button is an
initiation; these tests pin the part that makes that true rather than merely
convenient — every refusal the CLI performs, the button performs too, and it
performs it BEFORE a process exists.
"""
import pytest
from fastapi.testclient import TestClient

from app.server import create_app
from pipeline import budget, buildpool, config, db, freepool, pooljob, worker


@pytest.fixture()
def conn(tmp_path):
    return db.connect(tmp_path / "app.db")


def _no_op_stages(monkeypatch, acquired=("s1",)):
    calls = {}

    def acquire(c, ch, log=print):
        calls["acquire"] = True
        return {"acquired": list(acquired), "skipped": []}

    def render(c, ch, log=print, render=None):
        calls["render"] = True

    monkeypatch.setattr(worker, "acquire_stage", acquire)
    monkeypatch.setattr(worker, "render_stage", render)
    return calls


def _cap_exceeded():
    return budget.CapExceeded(spent=8.0, estimate=0.05, cap=8.0, period="month")


# ---- the module: what it refuses, and what it does after a build ----

def test_free_mode_builds_acquires_and_finishes_the_job(conn, monkeypatch):
    db.set_setting(conn, "curation_mode", "free")
    monkeypatch.setattr(freepool, "build_pool",
                        lambda *a, **k: [{"title": "x"}])
    calls = _no_op_stages(monkeypatch)
    rc = buildpool.run(conn, db.active_channel(conn), log=lambda *a: None)
    assert rc == 0 and calls == {"acquire": True, "render": True}
    job = pooljob.get(conn, 1)
    assert job.state == "done" and "acquired 1" in job.note


def test_free_mode_never_consults_the_budget(conn, monkeypatch):
    """`free` makes no model call at all, so it is the one mode that skips the
    cap check — the same carve-out run_story makes, not a second policy."""
    db.set_setting(conn, "curation_mode", "free")
    monkeypatch.setattr(freepool, "build_pool", lambda *a, **k: [])
    monkeypatch.setattr(budget, "check", lambda *a, **k: pytest.fail(
        "free mode must not need the cap"))
    _no_op_stages(monkeypatch)
    assert buildpool.run(conn, db.active_channel(conn), log=lambda *a: None) == 0


def test_an_expensive_build_refuses_without_approval(conn, monkeypatch):
    """The button's version of --yes-spend. A button that could quietly start a
    $2.40 build would make "Grace-initiated" mean "Grace-initiated once"."""
    db.set_setting(conn, "curation_mode", "llm")
    monkeypatch.setattr(freepool, "build_pool", lambda *a, **k: pytest.fail(
        "must not build"))
    monkeypatch.setattr("pipeline.curate.run_curation", lambda *a, **k: pytest.fail(
        "must not start a paid run"))
    rc = buildpool.run(conn, db.active_channel(conn), approved_spend=False,
                       log=lambda *a: None)
    assert rc == 3
    job = pooljob.get(conn, 1)
    assert job.state == "failed" and "approve the spend" in job.note


def test_a_breached_cap_stops_the_build_before_it_starts(conn, monkeypatch):
    db.set_setting(conn, "curation_mode", "free_llm")
    monkeypatch.setattr(budget, "check", lambda *a, **k: (_ for _ in ()).throw(
        _cap_exceeded()))
    monkeypatch.setattr(freepool, "build_pool", lambda *a, **k: pytest.fail(
        "must not build past the cap"))
    rc = buildpool.run(conn, db.active_channel(conn), log=lambda *a: None)
    assert rc == 4 and "spend cap reached" in pooljob.get(conn, 1).note


def test_a_cancelled_build_keeps_the_pool_and_acquires_nothing(conn, monkeypatch):
    db.set_setting(conn, "curation_mode", "free")

    def build(c, ch, **kw):
        pooljob.set_control(c, ch["id"], "cancel")   # the phone pressed stop
        return [{"title": "verified before the stop"}]
    monkeypatch.setattr(freepool, "build_pool", build)
    monkeypatch.setattr(worker, "acquire_stage", lambda *a, **k: pytest.fail(
        "a cancelled build must not go on to acquire"))
    rc = buildpool.run(conn, db.active_channel(conn), log=lambda *a: None)
    assert rc == 0
    job = pooljob.get(conn, 1)
    assert job.state == "cancelled" and "kept" in job.note


def test_a_failed_build_says_why_in_the_job_row(conn, monkeypatch):
    db.set_setting(conn, "curation_mode", "free")
    monkeypatch.setattr(freepool, "build_pool", lambda *a, **k: (
        _ for _ in ()).throw(RuntimeError("gutenberg unreachable")))
    rc = buildpool.run(conn, db.active_channel(conn), log=lambda *a: None)
    assert rc == 1
    job = pooljob.get(conn, 1)
    assert job.state == "failed" and "gutenberg unreachable" in job.note


def test_acquisition_failure_does_not_lose_the_pool(conn, monkeypatch):
    """The pool is the expensive half; a failed fetch afterwards must not read
    as "the build failed" without saying the pool survived."""
    db.set_setting(conn, "curation_mode", "free")
    monkeypatch.setattr(freepool, "build_pool", lambda *a, **k: [{"title": "x"}])
    monkeypatch.setattr(worker, "acquire_stage", lambda *a, **k: (
        _ for _ in ()).throw(RuntimeError("no network")))
    assert buildpool.run(conn, db.active_channel(conn), log=lambda *a: None) == 1
    assert "pool built" in pooljob.get(conn, 1).note


def test_the_estimate_is_one_function_both_sides_call(conn):
    """The number on the button and the number enforced must be the same one —
    the budget lesson (Entry 37), applied to the new entry point."""
    db.set_setting(conn, "curation_mode", "free")
    assert buildpool.estimate_for(conn, "free") == (0.0, "no model call at all")
    db.set_setting(conn, "curation_mode", "llm")
    usd, how = buildpool.estimate_for(conn, "llm")
    assert usd > config.CURATION_SPEND_CONFIRM_USD and "searches" in how


# ---- the API: every refusal happens before a process exists ----

@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "app.db"
    conn = db.connect(db_path)
    db.set_setting(conn, "curation_mode", "free")
    conn.close()
    spawned = []
    app = create_app(db_path=db_path, library_dir=tmp_path / "lib",
                     samples_dir=tmp_path / "s",
                     rerender_runner=lambda sid, voice: None,
                     build_runner=lambda cid, approve: spawned.append((cid, approve)))
    c = TestClient(app)
    c.spawned = spawned
    c.db_path = db_path
    return c


def test_channels_report_pool_state_and_the_estimate(client):
    body = client.get("/api/channels").json()
    ch = body["channels"][0]
    assert ch["pool_candidates"] == 0          # the notice AMENDMENT_04 A wants
    assert ch["build"] is None
    assert ch["free_sources"] and ch["no_free_source_reason"] is None
    assert body["build_estimate_usd"] == 0.0 and body["curation_mode"] == "free"
    assert body["build_needs_approval"] is False


def test_build_spawns_once_and_refuses_a_second(client):
    assert client.post("/api/channels/1/build").json()["started"] is True
    assert client.spawned == [(1, False)]
    conn = db.connect(client.db_path)
    pooljob.open_job(conn, 1)                  # the subprocess's first act
    assert client.post("/api/channels/1/build").status_code == 409
    assert client.spawned == [(1, False)], "no second process"


def test_build_404s_on_an_unknown_channel(client):
    assert client.post("/api/channels/99/build").status_code == 404
    assert client.spawned == []


def test_build_refuses_a_channel_no_free_source_covers(client):
    """Never an empty pool and never a silent switch to the paid path — the
    screen says which sources declined and why (sources.NoFreeSource's rule,
    moved in front of the spawn)."""
    client.put("/api/channels/1", json={"genre": "", "extra_criteria": ""})
    r = client.post("/api/channels/1/build")
    assert r.status_code == 422 and "gutenberg-catalog" in r.json()["detail"]
    assert client.spawned == []


def test_an_expensive_mode_needs_approval_in_the_body(client):
    client.put("/api/settings", json={"curation_mode": "llm"})
    r = client.post("/api/channels/1/build")
    assert r.status_code == 409 and "approve the spend" in r.json()["detail"]
    assert client.spawned == []
    assert client.post("/api/channels/1/build",
                       json={"approve_spend": True}).json()["started"] is True
    assert client.spawned == [(1, True)]


def test_a_breached_cap_refuses_at_the_api(client, monkeypatch):
    client.put("/api/settings", json={"curation_mode": "free_llm"})
    monkeypatch.setattr(budget, "check", lambda *a, **k: (_ for _ in ()).throw(
        _cap_exceeded()))
    r = client.post("/api/channels/1/build")
    assert r.status_code == 409 and "spend cap reached" in r.json()["detail"]
    assert client.spawned == []


def test_cancel_sets_control_and_pool_jobs_lists_it(client):
    conn = db.connect(client.db_path)
    pooljob.open_job(conn, 1)
    pooljob.set_phase(conn, 1, "verifying", total=40)
    pooljob.set_progress(conn, 1, 10, 3)
    builds = client.get("/api/pool-jobs").json()["builds"]
    assert len(builds) == 1 and builds[0]["fraction"] == 0.25
    assert builds[0]["usable"] == 3
    body = client.post("/api/channels/1/build/cancel").json()
    assert body["control"] == "cancel"
    assert pooljob.cancelled(db.connect(client.db_path), 1)


def test_cancel_404s_when_there_is_no_build(client):
    assert client.post("/api/channels/1/build/cancel").status_code == 404
