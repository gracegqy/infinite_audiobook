"""Ingest driver (AMENDMENT_04 flow): draws from the already-paid candidate
pool at $0; a new PAID curation batch only runs with the explicit --build-pool
flag (no silent spend). Announces each candidate BEFORE fetching so Grace can
Ctrl-C and pre-mark known stories (pipeline.mark).

Run: .venv/bin/python -m pipeline.run_story                 # $0: consume pool
     .venv/bin/python -m pipeline.run_story --build-pool    # PAID: refill pool
"""
import sys

from . import config, curate, db, fetch, ingest, pool


def main(argv: list[str]) -> int:
    conn = db.connect()
    channel = db.active_channel(conn)
    print(f"[channel] {channel['name']} (genre={channel['genre']}, "
          f"language={channel['language']})")

    if "--build-pool" in argv:
        candidates = curate.run_curation(conn, channel,
                                         batch=config.POOL_BATCH_SIZE)
    else:
        candidates = pool.pool_candidates(conn)
        if not candidates:
            print("Pool is empty. Refill with:  python -m pipeline.run_story "
                  f"--build-pool  (PAID: ~{config.POOL_BATCH_SIZE} candidates on "
                  f"{config.CURATION_MODEL}, expect a few dollars; recent "
                  "batches ran $0.90-$2.13 for 8)")
            return 1
        print(f"[pool] {len(candidates)} unconsumed candidate(s), $0 marginal")

    for c in candidates:
        # announce BEFORE any fetch cost (AMENDMENT_04 B)
        print(f"\n[next up] {c['title']} — {c.get('author') or 'unknown'} "
              f"({c['source_class']}:{c.get('source_ref')})")
        for ev in (c.get("evidence") or [])[:2]:
            print(f"          evidence: {ev}")
        print('          (Ctrl-C now and `python -m pipeline.mark read "<title>"` '
              "if you already know it)")
        if c["source_class"] not in fetch.ENABLED_SOURCE_CLASSES:
            print(f"[skip] source_class {c['source_class']} not enabled")
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
        print("\n=== INGESTED ===")
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
    sys.exit(main(sys.argv[1:]))
