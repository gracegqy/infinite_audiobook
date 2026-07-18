"""Re-run the pipeline for an existing story row (typically failed) without a
new curation call.

Run: .venv/bin/python -m pipeline.retry <story_id>
     .venv/bin/python -m pipeline.retry --list   # show retryable rows
"""
import sys

from . import db, ingest


def main(argv: list[str]) -> int:
    conn = db.connect()
    if not argv or argv[0] == "--list":
        # stranded mid-walk rows (crash/Ctrl-C during fetch or synthesis) are
        # retryable too, not just clean failures
        for r in conn.execute(
                "SELECT id, status, failure_note FROM stories "
                "WHERE status IN ('failed','queued','fetching','text_ready') "
                "ORDER BY created_at"):
            print(f"{r['id']}  [{r['status']}]  {r['failure_note'] or ''}")
        return 0
    sid = ingest.retry_story(conn, argv[0])
    print(f"retried OK: {sid}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
