"""Phase 3 gate driver: curate a fresh batch for the active channel, ingest the
first non-duplicate candidate end-to-end, print the library entry.

Run: .venv/bin/python -m pipeline.run_story
"""
import sys

from . import config, curate, db, fetch, ingest


def main() -> int:
    conn = db.connect()
    channel = db.active_channel(conn)
    print(f"[channel] {channel['name']} (genre={channel['genre']}, "
          f"language={channel['language']})")

    candidates = curate.run_curation(conn, channel)
    for c in candidates:
        if c["source_class"] not in fetch.ENABLED_SOURCE_CLASSES:
            print(f"[skip] {c['title']}: source_class {c['source_class']} not enabled")
            continue
        try:
            sid = ingest.ingest_candidate(conn, c, channel)
        except ingest.DuplicateStory:
            print(f"[skip] {c['title']}: already in history (dedup)")
            continue
        except Exception as e:
            print(f"[skip] {c['title']}: failed — {e}")
            continue
        story_dir = config.LIBRARY_DIR / sid
        print("\n=== GATE ARTIFACTS ===")
        for f in ("story.txt", "meta.json", "audio.m4a", "offsets.json"):
            p = story_dir / f
            print(f"  {p}  ({p.stat().st_size:,} bytes)")
        row = conn.execute("SELECT * FROM stories WHERE id=?", (sid,)).fetchone()
        print(f"  db: status={row['status']} engine={row['tts_engine']}/{row['voice']} "
              f"duration={row['duration_s']}s paras={row['paragraph_count']}")
        return 0
    print("ERROR: no candidate could be ingested", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
