"""Pre-extraction marking (AMENDMENT_04 B): record read/skip verdicts before any
fetch or render cost is incurred; also flips existing rows (a skip mid-render
triggers the synthesize abort hook).

Run: .venv/bin/python -m pipeline.mark read "yellow wallpaper"
     .venv/bin/python -m pipeline.mark skip "the willows"
"""
import sys

from . import db, ingest, pool

STATUS_BY_VERB = {"read": "read", "skip": "skipped"}


def mark(conn, verb: str, title_fragment: str) -> str:
    status = STATUS_BY_VERB[verb]
    frag = title_fragment.strip().lower()
    row = conn.execute(
        "SELECT id, title, status FROM stories WHERE lower(title) LIKE ?",
        (f"%{frag}%",)).fetchone()
    if row:
        db.set_status(conn, row["id"], status)
        return f"{row['id']}: {row['status']} -> {status}"
    candidate = pool.find_candidate(conn, title_fragment)
    if candidate:
        sid = ingest.record_provisional(
            conn, candidate, db.active_channel(conn), status,
            note="marked by Grace pre-extraction")
        return f"{sid}: pool candidate -> {status} (never fetched)"
    sid = ingest.record_provisional(
        conn, {"title": title_fragment}, db.active_channel(conn), status,
        note="marked by Grace by title (not in pool)")
    return f"{sid}: new provisional row -> {status}"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in STATUS_BY_VERB:
        print(__doc__)
        return 1
    conn = db.connect()
    print(mark(conn, argv[0], argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
