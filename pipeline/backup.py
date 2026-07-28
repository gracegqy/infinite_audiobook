"""WAL-consistent snapshot of the SQLite DB.

Why this exists: `data/library/` is expensive to regenerate but regenerable —
the DB is not. Ratings, resume positions and all-time story history exist only
here, and nothing else in the project can reconstruct them. The RUNBOOK has
required a backup since Phase 2, conditioned on "before Phase 5's worker runs
unattended"; the worker now runs, so this closes it.

Uses sqlite3's backup API rather than copying the file: a plain `cp` of a
WAL-mode database while the app is writing can capture a torn state, which is
the one moment a backup most needs to be correct.

Two destinations, because they answer different failure modes (Entry 37 closed
the second one):

  - `backups/`, on this machine — corruption, a bad migration, my own mistakes.
    Always on.
  - an OFF-MACHINE copy — losing the Mac. This is the half Phase 7 owed, and it
    is **off until Grace names a destination** in Settings. See OFFSITE_SUGGESTION.

What is deliberately NOT backed up: `data/library/`. It is tens of GB of audio
and it is REGENERABLE — every story row carries its source_ref, so the library
rebuilds from the DB by re-fetching and re-rendering (hours of TTS, $0 for
Kokoro). The DB is the irreplaceable half: ratings, resume positions and
all-time history exist nowhere else and nothing can reconstruct them. Backing
up the regenerable part at cloud-storage prices to save a re-render would be
the wrong trade; if that judgement ever changes, the library files are plain
mp4/json on disk and rsync handles them.

The off-machine copy carries titles, authors, ratings and resume positions. It
carries NO credentials — keys live in `.env` and never in the DB, which is
exactly why this snapshot is safe to put in cloud storage (DESIGN §10).

Run: .venv/bin/python -m pipeline.backup
     .venv/bin/python -m pipeline.backup --keep 5
     .venv/bin/python -m pipeline.backup --local-only  # skip the off-machine copy

The worker takes one of these on the `backup_interval_s` cadence, so a
running scheduler means backups happen without anyone remembering to.
"""
import datetime
import pathlib
import shutil
import sqlite3
import sys

from . import config, db

BACKUP_DIR = config.ROOT / "backups"
DEFAULT_KEEP = 10
# OFF BY DEFAULT, deliberately (Entry 37). An earlier version of this file
# defaulted to iCloud Drive, which meant installing the code was enough to start
# copying Grace's listening history into a cloud account she had not chosen.
# "Off-machine" is by definition data leaving the machine, so the destination is
# HERS to name: nothing is copied anywhere until `backup_offsite_dir` is set in
# the app's Settings tab. An empty or missing setting disables the copy
# entirely, and the local snapshot in backups/ still runs.
#
# Suggested value, shown as the placeholder in Settings rather than applied:
#   ~/Library/Mobile Documents/com~apple~CloudDocs/horror_readaloud_backups
# Any path works — an external disk or a NAS mount avoids cloud storage
# altogether.
OFFSITE_SUGGESTION = ("~/Library/Mobile Documents/com~apple~CloudDocs/"
                      "horror_readaloud_backups")


def offsite_dir(conn=None) -> pathlib.Path | None:
    """The off-machine destination, or None when unset — which is the default.
    Read from the DB so Grace changes it in Settings, never by editing code."""
    try:
        own = conn is None
        conn = conn or db.connect()
        raw = db.get_setting(conn, "backup_offsite_dir")
        if own:
            conn.close()
    except Exception:
        raw = None
    raw = (raw or "").strip()
    return pathlib.Path(raw).expanduser() if raw else None


def copy_offsite(src: pathlib.Path, keep: int, log=print) -> pathlib.Path | None:
    """Copy a finished snapshot off-machine and VERIFY it there.

    Verified at the destination rather than trusted: a cloud-sync folder can
    accept a write and then fail to materialise it, and an unverified
    off-machine backup is exactly the kind that is discovered to be empty on
    the day it is needed.
    """
    dest_dir = offsite_dir()
    if dest_dir is None:
        log("[backup] off-machine copy OFF — set a destination in Settings to "
            "enable it. The local snapshot in backups/ still protects against "
            "corruption, but NOT against losing the Mac.")
        return None
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        check = sqlite3.connect(dest)
        try:
            stories = check.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
            integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            check.close()
        if integrity != "ok":
            raise RuntimeError(f"off-machine copy failed integrity_check: "
                               f"{integrity}")
        log(f"[backup] off-machine: {dest} — {stories} stories, integrity ok")
        for p in (sorted(dest_dir.glob("app-*.db"))[:-keep] if keep > 0 else []):
            p.unlink()
            log(f"[backup] pruned off-machine {p.name}")
        return dest
    except Exception as e:
        # A failed off-machine copy must not lose the local backup that already
        # succeeded — report loudly and keep going.
        log(f"[backup] WARNING: off-machine copy FAILED: {e}")
        return None


def backup(keep: int = DEFAULT_KEEP, log=print,
           offsite: bool = True) -> pathlib.Path:
    if not config.DB_PATH.exists():
        raise FileNotFoundError(f"no database at {config.DB_PATH}")
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"app-{stamp}.db"

    src = sqlite3.connect(config.DB_PATH)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    # Verify rather than trust: a backup nobody has read is a guess.
    check = sqlite3.connect(dest)
    try:
        stories = check.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
        progress = check.execute("SELECT COUNT(*) FROM progress").fetchone()[0]
        ratings = check.execute("SELECT COUNT(*) FROM ratings").fetchone()[0]
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if integrity != "ok":
        raise RuntimeError(f"backup failed integrity_check: {integrity}")
    log(f"[backup] {dest} ({dest.stat().st_size / 1e6:.2f} MB) — "
        f"{stories} stories, {progress} progress rows, {ratings} ratings, "
        f"integrity ok")

    old = sorted(BACKUP_DIR.glob("app-*.db"))[:-keep] if keep > 0 else []
    for p in old:
        p.unlink()
        log(f"[backup] pruned {p.name}")

    if offsite:
        copy_offsite(dest, keep, log=log)
    return dest


def latest_backup_age_s(now: float | None = None) -> float | None:
    """Seconds since the newest local snapshot, or None if there is none.
    Derived from the FILES rather than a stored timestamp, so a snapshot
    deleted by hand correctly reads as "no recent backup"."""
    import time
    snaps = sorted(BACKUP_DIR.glob("app-*.db"),
                   key=lambda p: p.stat().st_mtime) if BACKUP_DIR.exists() else []
    if not snaps:
        return None
    return (now if now is not None else time.time()) - snaps[-1].stat().st_mtime


def maybe_backup(conn, log=print, now: float | None = None):
    """Take a snapshot if the cadence says one is due. Called by the worker
    loop, which is the only thing running unattended — Phase 7 owed a SCHEDULE
    and this is it, driven by a settings row rather than a plist so the cadence
    stays editable like every other knob (Entry 37).

    Never raises: a failed backup must not kill the replenishment loop. It
    logs, and the next cycle tries again.
    """
    try:
        interval = db.effective_backup_interval_s(conn)
        if interval <= 0:
            return None
        age = latest_backup_age_s(now)
        if age is not None and age < interval:
            return None
        return backup(log=log)
    except Exception as e:
        log(f"[backup] WARNING: scheduled backup failed: {e}")
        return None


def main(argv: list[str]) -> int:
    keep = DEFAULT_KEEP
    if "--keep" in argv:
        keep = int(argv[argv.index("--keep") + 1])
    backup(keep=keep, offsite="--local-only" not in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
