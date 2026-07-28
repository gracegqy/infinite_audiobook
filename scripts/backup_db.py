"""WAL-consistent snapshot of the SQLite DB.

Why this exists: `data/library/` is expensive to regenerate but regenerable —
the DB is not. Ratings, resume positions and all-time story history exist only
here, and nothing else in the project can reconstruct them. The RUNBOOK has
required a backup since Phase 2, conditioned on "before Phase 5's worker runs
unattended"; the worker now runs, so this closes it.

Uses sqlite3's backup API rather than copying the file: a plain `cp` of a
WAL-mode database while the app is writing can capture a torn state, which is
the one moment a backup most needs to be correct.

Honest limitation: this writes to the SAME MACHINE. It protects against
corruption, a bad migration, and my own mistakes — not against losing the Mac.
An off-machine copy is Phase 7's hardening task.

Run: .venv/bin/python scripts/backup_db.py
     .venv/bin/python scripts/backup_db.py --keep 5
"""
import datetime
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from pipeline import config  # noqa: E402

BACKUP_DIR = pathlib.Path(__file__).resolve().parents[1] / "backups"
DEFAULT_KEEP = 10


def backup(keep: int = DEFAULT_KEEP, log=print) -> pathlib.Path:
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
    return dest


def main(argv: list[str]) -> int:
    keep = DEFAULT_KEEP
    if "--keep" in argv:
        keep = int(argv[argv.index("--keep") + 1])
    backup(keep=keep)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
