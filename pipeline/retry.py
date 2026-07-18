"""Re-run the pipeline for an existing story row without a new curation call:
failed/stranded rows, or a voice re-render of a ready story (AMENDMENT_04 D).

Run: .venv/bin/python -m pipeline.retry <story_id>
     .venv/bin/python -m pipeline.retry <story_id> --voice am_michael
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
    voice = None
    if "--voice" in argv:
        i = argv.index("--voice")
        voice = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    sid = ingest.retry_story(conn, argv[0], voice_override=voice)
    print(f"retried OK: {sid}" + (f" (voice {voice})" if voice else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
