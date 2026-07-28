"""Ingest driver (AMENDMENT_04 flow): draws from the already-paid candidate
pool at $0; a new PAID curation batch only runs with the explicit --build-pool
flag (no silent spend). Announces each candidate BEFORE fetching so Grace can
Ctrl-C and pre-mark known stories (pipeline.mark).

Run: .venv/bin/python -m pipeline.run_story                 # $0: consume pool
     .venv/bin/python -m pipeline.run_story --build-pool    # refill pool (cost
                                                            # depends on
                                                            # curation_mode)
     .venv/bin/python -m pipeline.run_story --build-pool --yes-spend
                                        # approve a paid build over
                                        # config.CURATION_SPEND_CONFIRM_USD
"""
import sys

from . import config, curate, db, fetch, freepool, ingest, pool, sources


def main(argv: list[str]) -> int:
    conn = db.connect()
    channel = db.active_channel(conn)
    print(f"[channel] {channel['name']} (genre={channel['genre']}, "
          f"language={channel['language']})")

    if "--build-pool" in argv:
        # Entry 29/32: which builder runs is Grace's `curation_mode` setting —
        # free is $0, free_llm ~$0.03, llm paid. Never chosen automatically.
        mode = db.effective_curation_mode(conn)
        print(f"[pool] curation_mode={mode}")
        try:
            if mode in ("free", "free_llm"):
                candidates = freepool.build_pool(
                    conn, channel, limit=config.POOL_BATCH_SIZE,
                    use_llm=(mode == "free_llm"))
            else:
                # --build-pool opts into spending, but not into an AMOUNT.
                # Entry 29 shipped an unbounded paid loop; the estimate is now
                # on screen before the call, and a big one needs a second word.
                if not curate.confirm_spend(
                        db.effective_curation_model(conn),
                        config.POOL_BATCH_SIZE,
                        approved="--yes-spend" in argv):
                    return 3
                candidates = curate.run_curation(conn, channel,
                                                 batch=config.POOL_BATCH_SIZE)
        except sources.NoFreeSource as e:
            # A channel no free source covers is a real answer, not a crash —
            # and the fix is Grace's (switch mode, or add a source), so say both.
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
    else:
        candidates = pool.pool_candidates(conn)
        if not candidates:
            mode = db.effective_curation_mode(conn)
            cost = {"free": "$0, no API call",
                    "free_llm": f"~$0.03 on {db.effective_curation_model(conn)}, "
                                "no web search"}.get(
                        mode, f"PAID on {db.effective_curation_model(conn)}")
            print("Pool is empty. Refill with:  python -m pipeline.run_story "
                  f"--build-pool  ({cost}; curation_mode={mode}, "
                  f"~{config.POOL_BATCH_SIZE} candidates). Switch modes in the "
                  "app's Settings tab.")
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
