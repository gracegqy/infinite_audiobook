"""Preference adaptation (DESIGN §8, Phase 6). Ratings aggregate per
(kind, value_norm) into a short taste profile that is injected into the curation
prompt and stored on the run for the gate's before/after diff.

Three judgements are encoded here, because the naive version of each is wrong:

1. **Shrinkage, not raw averages.** With a handful of ratings most tag values
   have n=1, and a single 5 would otherwise outrank a tag averaging 4.5 over
   four stories. Ranking uses a mean shrunk toward the listener's own global
   average (`PRIOR_WEIGHT` pseudo-observations); the DISPLAYED figure stays the
   raw average and its n, per DESIGN §8's format, so the profile never shows a
   number the listener cannot reconcile with the stories she rated.

2. **A kind must discriminate to be worth prompt tokens.** Every story in a
   single-language horror channel carries `language: en` and `origin: western`;
   emitting "liked: en (3.0/5)" spends tokens to say nothing and invites the
   model to treat a constant as a preference. A kind is dropped unless the
   rated stories give it at least two distinct values — which adapts by itself
   when a second language or origin enters the library, rather than hardcoding
   a channel's shape (AMENDMENT_01).

3. **Placeholders are not preferences.** `author: unknown` aggregates every
   anonymous creepypasta into one bogus "author" the curator cannot act on.
   Values that name no entity are dropped from the author kind only.

Everything above the persistence helper is pure and unit-tested.
"""
from . import config

# Ratings run 1..5, so 3 is the indifference point: above it is a like, below a
# dislike, and exactly 3 is genuinely no signal rather than a weak one.
NEUTRAL_SCORE = 3.0

# Pseudo-observations of the listener's global mean mixed into every tag's
# average. 2 is deliberately gentle: it demotes n=1 tags below well-evidenced
# ones without erasing them, since early on n=1 is most of what exists.
PRIOR_WEIGHT = 2.0

# A kind earns prompt space only if the rated stories disagree about it.
MIN_DISTINCT_VALUES_PER_KIND = 2

# Author labels that name no one. Only applied to `author` — "unknown" is a
# legitimate value for other kinds and this must not become a global denylist.
NON_ACTIONABLE_AUTHORS = ("unknown", "anonymous", "n/a", "various", "")


def _actionable(kind: str, value: str) -> bool:
    if kind != "author":
        return bool(value)
    v = value.strip().lower()
    return bool(v) and not any(p == v or p in v for p in NON_ACTIONABLE_AUTHORS
                               if p)


def aggregate(rated_tags: list[tuple[str, str, str, int]]) -> list[dict]:
    """[(story_id, kind, value_norm, score)] → one row per (kind, value_norm)
    with n, the raw average, and the shrunk average used for ranking. Pure.

    Sorted strongest-liked first so callers never depend on input order. The
    prior's centre is the mean over DISTINCT rated stories, not over tag rows —
    a story carrying nine tags would otherwise count nine times and drag the
    centre toward whichever stories happen to be tagged most heavily.
    """
    if not rated_tags:
        return []

    buckets: dict[tuple[str, str], list[int]] = {}
    story_scores: dict[str, int] = {}
    # Distinct values are counted over EVERY stored value, including the
    # placeholders `_actionable` refuses to report. The two filters answer
    # different questions and must not interact: "does this kind vary across
    # the rated stories?" is about the data, while "can the curator act on this
    # label?" is about the output. Counting after the placeholder filter would
    # drop a real author merely because the only other story's author was
    # recorded as "unknown".
    distinct_per_kind: dict[str, set] = {}
    for story_id, kind, value, score in rated_tags:
        story_scores[story_id] = score
        if not kind or not value:
            continue
        distinct_per_kind.setdefault(kind, set()).add(value)
        if not _actionable(kind, value):
            continue
        buckets.setdefault((kind, value), []).append(score)
    if not buckets:
        return []

    global_mean = sum(story_scores.values()) / len(story_scores)

    out = []
    for (kind, value), scores in buckets.items():
        if len(distinct_per_kind[kind]) < MIN_DISTINCT_VALUES_PER_KIND:
            continue  # constant across the rated set: no preference expressed
        n = len(scores)
        avg = sum(scores) / n
        shrunk = (sum(scores) + PRIOR_WEIGHT * global_mean) / (n + PRIOR_WEIGHT)
        out.append({"kind": kind, "value": value, "n": n,
                    "avg": round(avg, 2), "shrunk": round(shrunk, 3)})
    out.sort(key=lambda r: (-r["shrunk"], -r["n"], r["kind"], r["value"]))
    return out


def _take_across_kinds(rows: list[dict], limit: int) -> list[dict]:
    """First `limit` rows, round-robined across tag kinds, each kind keeping its
    own ranking. Same device as curate.apply_class_quotas, for the same reason.

    Without this the cap is a pure ranking cut, and the kinds are wildly
    unbalanced: the tagger emits up to 5 free-text themes per story but exactly
    one era, so themes outnumber eras ~15:2 among liked tags. A ranking cut
    therefore fills the profile with one-off themes and drops era/subgenre —
    the tags that actually transfer to an unseen story, since a new story shares
    a listener's era or subgenre far more often than a specific theme label.
    A kind with few rows simply yields its places to the others.
    """
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        buckets.setdefault(r["kind"], []).append(r)
    out, i = [], 0
    while len(out) < limit:
        progressed = False
        for bucket in buckets.values():
            if i < len(bucket):
                out.append(bucket[i])
                progressed = True
                if len(out) >= limit:
                    break
        if not progressed:  # every kind exhausted
            break
        i += 1
    return out


def apply_overrides(stats: list[dict], overrides: dict) -> list[dict]:
    """Merge Grace's manual steering over the computed stats. Pure.

    `overrides` maps (kind, value_norm) -> score, where None means "suppress".
    Three effects, matching the three things the Trends screen offers:

      adjust  — a manual score REPLACES the computed one for an existing tag
      add     — an override with no computed tag behind it enters with n=0
      delete  — a None score removes the tag from the profile entirely

    A manual score is used verbatim, NOT shrunk: shrinkage exists to discount
    thin evidence, and a stated preference is not evidence to be discounted —
    if Grace says 5, the profile says 5. Manual rows also bypass the
    discriminating-kind rule, since an explicit instruction about a tag is a
    preference about it by definition.
    """
    out, seen = [], set()
    for r in stats:
        key = (r["kind"], r["value"])
        if key not in overrides:
            out.append(r)
            continue
        seen.add(key)
        score = overrides[key]
        if score is None:
            continue  # suppressed
        out.append({**r, "avg": round(float(score), 2),
                    "shrunk": float(score), "manual": True})
    for (kind, value), score in overrides.items():
        if (kind, value) in seen or score is None:
            continue
        out.append({"kind": kind, "value": value, "n": 0,
                    "avg": round(float(score), 2), "shrunk": float(score),
                    "manual": True})
    out.sort(key=lambda r: (-r["shrunk"], -r["n"], r["kind"], r["value"]))
    return out


def split_preferences(stats: list[dict], limit: int = 8
                      ) -> tuple[list[dict], list[dict]]:
    """(liked, disliked), each capped at `limit`, strongest-first within a kind
    and spread across kinds. Rows whose shrunk mean sits exactly at
    NEUTRAL_SCORE are in neither list: they carry no direction, and padding the
    profile with them would dilute the ones that do.
    """
    liked = _take_across_kinds(
        [r for r in stats if r["shrunk"] > NEUTRAL_SCORE], limit)
    disliked = _take_across_kinds(
        sorted((r for r in stats if r["shrunk"] < NEUTRAL_SCORE),
               key=lambda r: (r["shrunk"], -r["n"])), limit)
    return liked, disliked


def render_profile(stats: list[dict], rated_story_count: int = 0,
                   limit: int = 8) -> str:
    """The text block injected into the curation prompt (DESIGN §8 format).

    Returns "" when there is nothing to say — an empty profile must produce NO
    prompt section at all, not a section announcing it is empty, so that an
    unrated library curates exactly as it did before Phase 6.
    """
    liked, disliked = split_preferences(stats, limit=limit)
    if not liked and not disliked:
        return ""

    def fmt(rows):
        # A manual entry is labelled as such: it is the listener speaking
        # directly, and the model should not read "n=0" as weak evidence.
        return ", ".join(
            f"{r['value']} [{r['kind']}] "
            + ("(set by the listener: "
               f"{r['avg']:.1f}/5)" if r.get("manual")
               else f"({r['avg']:.1f}/5, n={r['n']})")
            for r in rows)

    lines = []
    if liked:
        lines.append(f"liked: {fmt(liked)}")
    if disliked:
        lines.append(f"disliked: {fmt(disliked)}")
    # n is stated so the model can discount thin evidence instead of treating a
    # single 5 as settled taste.
    lines.append(f"(from {rated_story_count} rated "
                 f"{'story' if rated_story_count == 1 else 'stories'}; "
                 f"n = stories behind each figure. Weight these preferences "
                 f"against the channel criteria — they refine the channel, "
                 f"they never override it.)")
    return "\n".join(lines)


# ---- persistence boundary (everything above is pure) ----

def rated_tags(conn, channel_id: int | None = None
               ) -> list[tuple[str, str, str, int]]:
    """(story_id, kind, value_norm, score) for every rated story's tags.

    A LEFT JOIN, not an inner one: a rated story with no tags still has to reach
    `aggregate`, because it belongs in the global mean that centres the prior
    even though it contributes no tag of its own.

    channel_id restricts to stories acquired for that channel, matching how
    replenishment is already channel-scoped (pool.pool_candidates): taste from a
    Chinese sci-fi channel should not steer an English horror one.
    """
    sql = ("SELECT r.story_id, t.kind, t.value_norm, r.score FROM ratings r "
           "JOIN stories s ON s.id = r.story_id "
           "LEFT JOIN tags t ON t.story_id = r.story_id")
    args: tuple = ()
    if channel_id is not None:
        sql += " WHERE s.channel_id = ?"
        args = (channel_id,)
    return [(r["story_id"], r["kind"], r["value_norm"], r["score"])
            for r in conn.execute(sql, args)]


def rated_story_count(conn, channel_id: int | None = None) -> int:
    sql = ("SELECT COUNT(*) AS n FROM ratings r "
           "JOIN stories s ON s.id = r.story_id")
    args: tuple = ()
    if channel_id is not None:
        sql += " WHERE s.channel_id = ?"
        args = (channel_id,)
    return conn.execute(sql, args).fetchone()["n"]


def overrides(conn) -> dict:
    """{(kind, value_norm): score|None} — Grace's manual steering."""
    return {(r["kind"], r["value_norm"]): r["score"]
            for r in conn.execute(
                "SELECT kind, value_norm, score FROM taste_overrides")}


def set_override(conn, kind: str, value: str, score: float | None):
    """Upsert one manual entry. score=None suppresses the tag."""
    conn.execute(
        "INSERT INTO taste_overrides(kind, value_norm, score, updated_at) "
        "VALUES(?,?,?,datetime('now')) ON CONFLICT(kind, value_norm) DO UPDATE "
        "SET score=excluded.score, updated_at=excluded.updated_at",
        (kind, value, score))
    conn.commit()


def clear_override(conn, kind: str, value: str) -> bool:
    """Revert a tag to automatic. True if an override was actually removed."""
    cur = conn.execute(
        "DELETE FROM taste_overrides WHERE kind=? AND value_norm=?",
        (kind, value))
    conn.commit()
    return cur.rowcount > 0


def _stats_with_overrides(conn, channel_id) -> list[dict]:
    return apply_overrides(aggregate(rated_tags(conn, channel_id)),
                           overrides(conn))


def profile_for(conn, channel_id: int | None = None) -> str:
    """The single copy of 'what taste profile goes in the prompt' — both
    curation paths and the Trends screen read this, so what the UI shows is by
    construction what the model was sent.

    Below `TASTE_MIN_RATED_STORIES` this returns "" and curation behaves exactly
    as it did before Phase 6. That floor is not caution for its own sake: the
    prior is centred on the listener's own mean, so with a single rated story
    every tag's shrunk mean EQUALS that mean, and one 5-star story would mark
    every tag it carries as "liked" with no evidence separating them.

    Manual overrides bypass the floor: they are a stated preference, not an
    inference from thin evidence, so they carry no degenerate-prior problem.
    """
    n = rated_story_count(conn, channel_id)
    manual = overrides(conn)
    if n < config.TASTE_MIN_RATED_STORIES and not any(
            s is not None for s in manual.values()):
        return ""
    return render_profile(_stats_with_overrides(conn, channel_id), n)


def summary(conn, channel_id: int | None = None) -> dict:
    """Trends screen payload (DESIGN §8: 'reads the same aggregation')."""
    stats = _stats_with_overrides(conn, channel_id)
    liked, disliked = split_preferences(stats)
    return {
        "rated_story_count": rated_story_count(conn, channel_id),
        "liked": liked,
        "disliked": disliked,
        "all": stats,
        "profile_text": profile_for(conn, channel_id),
        "min_ratings_for_signal": config.TASTE_MIN_RATED_STORIES,
        "kinds": sorted({r["kind"] for r in stats}
                        | set(config.CONTROLLED_VOCAB) | {"theme", "author"}),
    }
