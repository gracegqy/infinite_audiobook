"""DB snapshots (pipeline/backup.py).

This module had no tests at all until the 2026-08-07 audit (DEBT-2), which is
awkward for the one piece of code whose whole job is to still work on the day
everything else has failed. What is under test is the DECISION and the
GUARANTEE: that a snapshot is really readable afterwards, that pruning keeps
the newest rather than the oldest, that the cadence can say "not yet", and that
a failing backup never takes the worker loop down with it.

Everything is redirected at a tmp_path — both `config.DB_PATH` (the source, and
what `offsite_dir` opens) and `backup.BACKUP_DIR`, which is rooted at the repo
rather than under HR_DATA_DIR and so is NOT redirected by the sandbox env var.
"""
import os
import sqlite3

import pytest

from pipeline import backup, config, db


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """A temp DB with 3 stories + a temp backups/ dir. Returns (conn, dir)."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "app.db")
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
    conn = db.connect(config.DB_PATH)
    for i in range(3):
        conn.execute(
            "INSERT INTO stories(id, channel_id, dedup_key, title, source_class,"
            " source_ref, source_url, license_class, language, status) "
            "VALUES(?,1,?,?,'gutenberg','1','https://example.org/x','pd','en',"
            "'ready')", (f"s{i}", f"k{i}", f"Story {i}"))
    conn.commit()
    return conn, tmp_path / "backups"


def stamped(dirpath, name, mtime=None):
    """A decoy snapshot file, optionally aged."""
    dirpath.mkdir(exist_ok=True)
    p = dirpath / name
    p.write_bytes(b"")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


# ---- the guarantee: a snapshot is readable afterwards ----

def test_snapshot_round_trips_and_carries_the_same_stories(sandbox):
    conn, bdir = sandbox
    dest = backup.backup(log=lambda *a: None, offsite=False)

    assert dest.exists() and dest.parent == bdir
    check = sqlite3.connect(dest)
    try:
        assert check.execute("SELECT COUNT(*) FROM stories").fetchone()[0] == 3
        assert {r[0] for r in check.execute("SELECT title FROM stories")} \
            == {"Story 0", "Story 1", "Story 2"}
        assert check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        check.close()


def test_a_missing_source_database_raises_rather_than_writing_an_empty_file(
        tmp_path, monkeypatch):
    """The failure mode worth refusing: a "successful" backup of nothing."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "gone.db")
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
    with pytest.raises(FileNotFoundError):
        backup.backup(log=lambda *a: None, offsite=False)
    assert not (tmp_path / "backups").exists()


# ---- pruning ----

def test_keep_prunes_the_oldest_and_never_the_new_one(sandbox):
    conn, bdir = sandbox
    for name in ("app-20260101-000000.db", "app-20260102-000000.db",
                 "app-20260103-000000.db"):
        stamped(bdir, name)

    dest = backup.backup(keep=2, log=lambda *a: None, offsite=False)

    remaining = sorted(p.name for p in bdir.glob("app-*.db"))
    assert len(remaining) == 2
    assert dest.name in remaining              # the fresh one always survives
    assert "app-20260101-000000.db" not in remaining  # oldest went first
    assert "app-20260102-000000.db" not in remaining


def test_keep_zero_disables_pruning(sandbox):
    conn, bdir = sandbox
    stamped(bdir, "app-20260101-000000.db")
    backup.backup(keep=0, log=lambda *a: None, offsite=False)
    assert len(list(bdir.glob("app-*.db"))) == 2


# ---- age, read from the files rather than a stored timestamp ----

def test_age_is_none_when_there_is_no_snapshot(sandbox):
    conn, bdir = sandbox
    assert backup.latest_backup_age_s(now=1000.0) is None


def test_age_comes_from_the_newest_file(sandbox):
    conn, bdir = sandbox
    stamped(bdir, "app-20260101-000000.db", mtime=1000.0)
    stamped(bdir, "app-20260102-000000.db", mtime=5000.0)
    assert backup.latest_backup_age_s(now=5500.0) == 500.0


# ---- the cadence (maybe_backup): the worker loop's only unattended duty ----

def test_maybe_backup_is_off_at_interval_zero(sandbox):
    """0 disables scheduled snapshots — even with no snapshot on disk at all,
    which is the case that would otherwise always look overdue."""
    conn, bdir = sandbox
    db.set_setting(conn, "backup_interval_s", "0")
    assert backup.maybe_backup(conn, log=lambda *a: None, now=9e9) is None
    assert not bdir.exists()


def test_maybe_backup_takes_the_first_snapshot_when_none_exists(sandbox):
    conn, bdir = sandbox
    db.set_setting(conn, "backup_interval_s", "3600")
    dest = backup.maybe_backup(conn, log=lambda *a: None)
    assert dest is not None and dest.exists()


def test_maybe_backup_waits_until_the_interval_has_elapsed(sandbox):
    """Injected clock, per the CLAUDE.md rule that time-dependent behaviour
    takes `now` as a parameter — otherwise this test would take an hour."""
    conn, bdir = sandbox
    db.set_setting(conn, "backup_interval_s", "3600")
    stamped(bdir, "app-20260101-000000.db", mtime=10_000.0)

    assert backup.maybe_backup(conn, log=lambda *a: None,
                               now=10_000.0 + 3599) is None   # not yet
    dest = backup.maybe_backup(conn, log=lambda *a: None,
                               now=10_000.0 + 3601)           # due
    assert dest is not None and dest.exists()


def test_maybe_backup_never_raises_into_the_worker_loop(sandbox, monkeypatch):
    """It is called from `worker.loop_iteration`, where an exception would kill
    the only unattended process in the project."""
    conn, bdir = sandbox
    db.set_setting(conn, "backup_interval_s", "3600")
    monkeypatch.setattr(backup, "backup", lambda *a, **k: 1 / 0)
    logs = []
    assert backup.maybe_backup(conn, log=logs.append) is None
    assert any("scheduled backup failed" in m for m in logs)


# ---- off-machine copy (standing debt 2) ----

def test_off_machine_copy_stays_off_until_a_destination_is_set(sandbox):
    """Entry 37's binding decision: installing the code must not start copying
    Grace's listening history anywhere. Unset means OFF, and says so."""
    conn, bdir = sandbox
    logs = []
    dest = backup.backup(log=logs.append)  # offsite=True, the default
    assert dest.exists()
    assert backup.offsite_dir() is None
    assert any("off-machine copy OFF" in m for m in logs)


def test_a_destination_set_in_settings_gets_a_verified_copy(sandbox, tmp_path):
    conn, bdir = sandbox
    offsite = tmp_path / "offsite"
    db.set_setting(conn, "backup_offsite_dir", str(offsite))

    dest = backup.backup(log=lambda *a: None)

    copies = list(offsite.glob("app-*.db"))
    assert [p.name for p in copies] == [dest.name]
    check = sqlite3.connect(copies[0])
    try:
        assert check.execute("SELECT COUNT(*) FROM stories").fetchone()[0] == 3
    finally:
        check.close()
