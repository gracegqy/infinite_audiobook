"""Preference adaptation (DESIGN §8, Phase 6).

The behaviours under test are the ones where the obvious implementation is
wrong: a single 5-star rating must not outrank a well-evidenced 4.5; a tag kind
that never varies must not be reported as a preference; and an unrated library
must curate exactly as it did before Phase 6 existed.
"""
import pytest

from pipeline import config, db, tag, taste


def rows(*triples):
    """(story_id, kind, value, score) rows, spelled compactly in the tests."""
    return [(s, k, v, sc) for s, k, v, sc in triples]


# ---- aggregation ----

def test_empty_input_yields_no_stats():
    assert taste.aggregate([]) == []


def test_averages_and_counts_per_tag():
    stats = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 5), ("s1", "era", "19th-century", 5),
        ("s2", "subgenre", "gothic", 3), ("s2", "era", "contemporary", 3),
        ("s3", "subgenre", "weird", 1),  # subgenre must vary to be reported
    ))
    gothic = next(r for r in stats if r["value"] == "gothic")
    assert gothic["n"] == 2 and gothic["avg"] == 4.0


def test_shrinkage_ranks_evidence_over_a_lone_five():
    """The core ranking rule: 4.5 over four stories beats a single 5."""
    stats = taste.aggregate(rows(
        ("s1", "subgenre", "solid", 5), ("s2", "subgenre", "solid", 4),
        ("s3", "subgenre", "solid", 5), ("s4", "subgenre", "solid", 4),
        ("s5", "subgenre", "lucky", 5),
        # a low-rated story to pull the global mean below both
        ("s6", "subgenre", "bad", 1),
    ))
    ranked = [r["value"] for r in stats]
    assert ranked.index("solid") < ranked.index("lucky")
    lucky = next(r for r in stats if r["value"] == "lucky")
    assert lucky["avg"] == 5.0, "raw average is still reported verbatim"
    assert lucky["shrunk"] < 5.0, "but ranking uses the shrunk mean"


def test_prior_is_centred_on_stories_not_tag_rows():
    """A heavily tagged story must not drag the prior toward its own score."""
    heavy = rows(*[("s1", "theme", f"t{i}", 5) for i in range(9)])
    light = rows(("s2", "theme", "lonely", 1))
    stats = taste.aggregate(heavy + light)
    lonely = next(r for r in stats if r["value"] == "lonely")
    # global mean is (5 + 1) / 2 = 3.0, not 9x5+1 / 10 = 4.6
    assert lonely["shrunk"] == pytest.approx((1 + 2.0 * 3.0) / 3.0, abs=1e-3)


def test_a_kind_with_one_distinct_value_is_dropped():
    """Every story being `en` expresses no preference about language."""
    stats = taste.aggregate(rows(
        ("s1", "language", "en", 5), ("s1", "subgenre", "gothic", 5),
        ("s2", "language", "en", 1), ("s2", "subgenre", "weird", 1),
    ))
    assert {r["kind"] for r in stats} == {"subgenre"}


def test_a_kind_that_varies_is_kept():
    stats = taste.aggregate(rows(
        ("s1", "language", "en", 5), ("s2", "language", "zh", 1)))
    assert {r["kind"] for r in stats} == {"language"}


def test_placeholder_authors_are_dropped_but_real_ones_kept():
    stats = taste.aggregate(rows(
        ("s1", "author", "unknown", 1), ("s2", "author", "shirley jackson", 5),
        ("s3", "author", "anonymous", 2),
    ))
    assert [r["value"] for r in stats] == ["shirley jackson"]


def test_unknown_is_kept_for_kinds_other_than_author():
    stats = taste.aggregate(rows(
        ("s1", "theme", "unknown", 5), ("s2", "theme", "known", 1)))
    assert {r["value"] for r in stats} == {"unknown", "known"}


def test_rated_story_with_no_tags_still_counts_toward_the_prior():
    """The LEFT JOIN case: tagless rated stories carry no tag but do move the
    centre, so dropping them would bias the prior toward tagged stories."""
    with_tagless = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 5), ("s2", "subgenre", "weird", 3),
        ("s3", None, None, 1)))
    without = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 5), ("s2", "subgenre", "weird", 3)))
    g1 = next(r for r in with_tagless if r["value"] == "gothic")["shrunk"]
    g2 = next(r for r in without if r["value"] == "gothic")["shrunk"]
    assert g1 != g2


def test_aggregate_is_deterministic_regardless_of_input_order():
    data = rows(("s1", "subgenre", "gothic", 5), ("s2", "era", "modern", 2),
                ("s3", "subgenre", "weird", 1), ("s4", "era", "old", 4))
    assert taste.aggregate(data) == taste.aggregate(list(reversed(data)))


# ---- profile rendering ----

def test_no_ratings_renders_no_profile_at_all():
    """An empty profile must be "", never a section announcing emptiness."""
    assert taste.render_profile([], 0) == ""


def test_profile_states_raw_average_and_n():
    # `weird` gets two stories: since Entry 38 a lone rating is not reportable,
    # and this test is about the FORMAT, not the floor.
    stats = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 5), ("s2", "subgenre", "gothic", 4),
        ("s3", "subgenre", "weird", 1), ("s4", "subgenre", "weird", 1)))
    text = taste.render_profile(stats, 4)
    assert "liked: gothic [subgenre] (4.5/5, n=2)" in text
    assert "disliked:" in text and "weird" in text


def test_neutral_tags_appear_in_neither_list():
    stats = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 3), ("s2", "subgenre", "weird", 3)))
    liked, disliked = taste.split_preferences(stats)
    assert liked == [] and disliked == []


def liked_pair(prefix: str, kind: str, value: str, score: int):
    """Two stories carrying the same tag — the minimum that clears the Entry-38
    evidence floor, so cap/spread tests exercise the cap and not the floor."""
    return rows((f"{prefix}a", kind, value, score),
                (f"{prefix}b", kind, value, score))


def test_cap_spreads_across_kinds_rather_than_taking_one_kind():
    """15 liked themes must not crowd out the single liked era/subgenre."""
    data = []
    for i in range(15):
        data += liked_pair("t%d" % i, "theme", "t%d" % i, 5)
    data += liked_pair("e", "era", "19th-century", 5)
    data += liked_pair("g", "subgenre", "gothic", 5)
    # every kind must vary, else the discriminating-kind rule drops it before
    # the cap is ever reached
    data += liked_pair("x", "theme", "bad", 1)
    data += liked_pair("y", "era", "contemporary", 1)
    data += liked_pair("z", "subgenre", "weird", 1)
    liked, _ = taste.split_preferences(taste.aggregate(data), limit=6)
    assert {r["kind"] for r in liked} == {"theme", "era", "subgenre"}


def test_cap_yields_places_when_a_kind_runs_out():
    data = []
    for i in range(6):
        data += liked_pair("t%d" % i, "theme", "t%d" % i, 5)
    data += liked_pair("e", "era", "19th-century", 5)
    data += liked_pair("x", "theme", "bad", 1)
    data += liked_pair("y", "era", "contemporary", 1)
    liked, _ = taste.split_preferences(taste.aggregate(data), limit=5)
    assert len(liked) == 5, "one era must not cap the whole profile at 2"


# ---- per-tag evidence floor (Entry 38) ----

def test_one_story_is_not_a_verdict_on_its_subgenre():
    """The `weird` defect: Grace rated ONE badly-made cosmic-horror story a 1,
    and the profile reported `weird (1.0/5)` — a verdict on a subgenre she
    likes. Shrinkage did not cover it, because the DISPLAYED figure is the raw
    average and that is what the model reads."""
    stats = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 5), ("s2", "subgenre", "gothic", 5),
        ("s3", "subgenre", "weird", 1)))
    weird = next(r for r in stats if r["value"] == "weird")
    assert weird["n"] == 1 and weird["shrunk"] < taste.NEUTRAL_SCORE, (
        "still computed, and still ranked below neutral")
    _, disliked = taste.split_preferences(stats)
    assert disliked == [], "but not stated as a preference"
    assert "weird" not in taste.render_profile(stats, 3)


def test_the_floor_is_per_tag_not_per_corpus():
    """A 20-story corpus does not license a claim about the one tag that
    appeared once — the two floors answer different questions."""
    data = rows(*[("s%d" % i, "subgenre", "gothic", 5) for i in range(20)])
    data += rows(("s99", "subgenre", "weird", 1))
    _, disliked = taste.split_preferences(taste.aggregate(data))
    assert [r["value"] for r in disliked] == []


def test_a_tag_clears_the_floor_at_exactly_two_stories():
    """Boundary: TASTE_MIN_N_PER_TAG is inclusive, so n=2 reports."""
    data = rows(("s1", "subgenre", "gothic", 5), ("s2", "subgenre", "gothic", 5),
                ("s3", "subgenre", "weird", 1), ("s4", "subgenre", "weird", 1))
    _, disliked = taste.split_preferences(taste.aggregate(data))
    assert [r["value"] for r in disliked] == ["weird"]


def test_has_evidence_reads_the_configured_floor(monkeypatch):
    """The floor is a config knob, not a literal 2 buried in the predicate."""
    monkeypatch.setattr(config, "TASTE_MIN_N_PER_TAG", 3)
    assert not taste.has_evidence({"n": 2})
    assert taste.has_evidence({"n": 3})


def test_a_manual_override_bypasses_the_evidence_floor():
    """Grace's correction path for exactly this defect: a stated preference is
    not an inference from thin evidence, so the floor does not apply to it."""
    stats = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 5), ("s2", "subgenre", "gothic", 5),
        ("s3", "subgenre", "weird", 1)))
    merged = taste.apply_overrides(stats, {("subgenre", "weird"): 4.0})
    liked, _ = taste.split_preferences(merged)
    assert "weird" in [r["value"] for r in liked]


def test_thin_tags_stay_visible_even_though_they_are_not_reported():
    """They must remain in `all` — a tag Grace cannot see is one she cannot
    override, and the override is the whole remedy."""
    stats = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 5), ("s2", "subgenre", "gothic", 5),
        ("s3", "subgenre", "weird", 1)))
    assert "weird" in [r["value"] for r in stats]


# ---- manual overrides (Entry 35) ----

def test_override_replaces_a_computed_score_verbatim():
    """A stated preference is not evidence to be discounted — no shrinkage."""
    stats = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 5), ("s2", "subgenre", "weird", 1)))
    out = taste.apply_overrides(stats, {("subgenre", "gothic"): 2.0})
    gothic = next(r for r in out if r["value"] == "gothic")
    assert gothic["avg"] == 2.0 and gothic["shrunk"] == 2.0
    assert gothic["manual"] is True
    assert gothic["n"] == 1, "the underlying evidence count is still reported"


def test_override_can_suppress_a_tag():
    stats = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 5), ("s2", "subgenre", "weird", 1)))
    out = taste.apply_overrides(stats, {("subgenre", "gothic"): None})
    assert [r["value"] for r in out] == ["weird"]


def test_override_can_add_a_tag_with_no_ratings_behind_it():
    stats = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 5), ("s2", "subgenre", "weird", 1)))
    out = taste.apply_overrides(stats, {("subgenre", "folk"): 5.0})
    folk = next(r for r in out if r["value"] == "folk")
    assert folk["n"] == 0 and folk["avg"] == 5.0 and folk["manual"] is True


def test_added_tag_bypasses_the_discriminating_kind_rule():
    """An explicit instruction about a tag is a preference about it, even if
    the kind never varies across rated stories."""
    stats = taste.aggregate(rows(("s1", "subgenre", "gothic", 5)))
    assert stats == [], "one distinct subgenre is dropped as uninformative"
    out = taste.apply_overrides(stats, {("language", "zh"): 5.0})
    assert [r["value"] for r in out] == ["zh"]


def test_overrides_do_not_mutate_the_input_stats():
    stats = taste.aggregate(rows(
        ("s1", "subgenre", "gothic", 5), ("s2", "subgenre", "weird", 1)))
    before = [dict(r) for r in stats]
    taste.apply_overrides(stats, {("subgenre", "gothic"): 1.0})
    assert stats == before


def test_manual_entries_are_labelled_in_the_prompt_text():
    """n=0 must not read to the model as weak evidence."""
    stats = taste.apply_overrides(
        taste.aggregate(rows(("s1", "subgenre", "gothic", 5),
                             ("s2", "subgenre", "weird", 1))),
        {("subgenre", "folk"): 5.0})
    text = taste.render_profile(stats, 2)
    assert "folk [subgenre] (set by the listener: 5.0/5)" in text
    assert "n=0" not in text


# ---- DB boundary ----

@pytest.fixture()
def conn(tmp_path):
    return db.connect(tmp_path / "app.db")


def seed(conn, story_id, score, tags, channel_id=1):
    conn.execute(
        "INSERT INTO stories(id, channel_id, dedup_key, title, source_class, "
        "source_url, license_class, status) VALUES(?,?,?,?,?,?,?,?)",
        (story_id, channel_id, story_id, story_id, "gutenberg", "u", "pd", "read"))
    conn.execute("INSERT INTO ratings(story_id, score) VALUES(?,?)",
                 (story_id, score))
    conn.executemany(
        "INSERT INTO tags(story_id, kind, value_verbatim, value_norm) "
        "VALUES(?,?,?,?)", [(story_id, k, v, v) for k, v in tags])
    conn.commit()


def test_profile_is_empty_below_the_rating_floor(conn):
    """One 5-star story would otherwise mark everything it touched as liked."""
    seed(conn, "s1", 5, [("subgenre", "gothic"), ("era", "19th-century")])
    assert taste.rated_story_count(conn) == 1
    assert taste.profile_for(conn) == ""


def test_profile_appears_once_the_floor_is_met(conn):
    for i, (score, sub) in enumerate([(5, "gothic"), (4, "gothic"),
                                      (1, "weird")]):
        seed(conn, f"s{i}", score, [("subgenre", sub), ("era", f"e{i%2}")])
    assert taste.rated_story_count(conn) == config.TASTE_MIN_RATED_STORIES
    profile = taste.profile_for(conn)
    assert "gothic" in profile and "liked:" in profile


def test_profile_is_scoped_to_one_channel(conn):
    conn.execute("INSERT INTO channels(id, name, genre, language) "
                 "VALUES(2,'other','sci-fi','en')")
    conn.commit()
    # each channel needs a varying subgenre of its own, or the
    # discriminating-kind rule drops the kind before scoping is exercised
    for i, (score, sub) in enumerate([(5, "gothic"), (5, "gothic"), (1, "weird")]):
        seed(conn, f"a{i}", score, [("subgenre", sub)], channel_id=1)
    for i, (score, sub) in enumerate([(5, "cyberpunk"), (5, "cyberpunk"),
                                      (1, "dystopian")]):
        seed(conn, f"b{i}", score, [("subgenre", sub)], channel_id=2)
    assert "gothic" in taste.profile_for(conn, 1)
    assert "gothic" not in taste.profile_for(conn, 2)
    assert "cyberpunk" in taste.profile_for(conn, 2)


def test_manual_override_survives_a_round_trip(conn):
    for i, score in enumerate([5, 4, 1]):
        seed(conn, f"s{i}", score,
             [("subgenre", "gothic" if score > 3 else "weird")])
    taste.set_override(conn, "subgenre", "gothic", 1.0)
    assert "gothic" in taste.profile_for(conn)
    liked, disliked = taste.split_preferences(
        taste._stats_with_overrides(conn, None))
    assert "gothic" in [r["value"] for r in disliked], "flipped by the override"
    assert taste.clear_override(conn, "subgenre", "gothic") is True
    liked, _ = taste.split_preferences(taste._stats_with_overrides(conn, None))
    assert "gothic" in [r["value"] for r in liked], "back to automatic"


def test_a_manual_entry_alone_builds_a_profile_below_the_floor(conn):
    """Overrides bypass the rating floor — they carry no degenerate prior."""
    seed(conn, "s1", 5, [("subgenre", "gothic")])
    assert taste.profile_for(conn) == ""
    taste.set_override(conn, "subgenre", "folk", 5.0)
    assert "folk" in taste.profile_for(conn)


def test_suppression_alone_does_not_conjure_a_profile(conn):
    """A suppress-only override says what to leave OUT, not what to seek."""
    seed(conn, "s1", 5, [("subgenre", "gothic")])
    taste.set_override(conn, "subgenre", "gothic", None)
    assert taste.profile_for(conn) == ""


def test_summary_matches_the_profile_the_model_is_sent(conn):
    """The Trends screen and the prompt must never disagree."""
    for i, score in enumerate([5, 4, 1]):
        seed(conn, f"s{i}", score,
             [("subgenre", "gothic" if score > 3 else "weird")])
    assert taste.summary(conn)["profile_text"] == taste.profile_for(conn)


# ---- the normalization migration this feature depends on ----

def test_free_value_norm_collapses_spacing_and_case():
    assert tag.free_value_norm("Unreliable Narrator") == "unreliable-narrator"
    assert tag.free_value_norm("descent  into_madness") == "descent-into-madness"


def test_migration_merges_the_two_spellings_of_one_theme(conn):
    """The live-DB defect: one theme stored under two keys, each with half its
    evidence (Phase 6 aggregates on value_norm)."""
    seed(conn, "s1", 5, [])
    seed(conn, "s2", 1, [])
    conn.executemany(
        "INSERT INTO tags(story_id, kind, value_verbatim, value_norm) "
        "VALUES(?,?,?,?)",
        [("s1", "theme", "unreliable narrator", "unreliable narrator"),
         ("s2", "theme", "unreliable narrator", "unreliable-narrator")])
    conn.commit()
    db._migrate_tag_value_norm(conn)
    norms = [r["value_norm"] for r in conn.execute(
        "SELECT value_norm FROM tags WHERE kind='theme'")]
    assert norms == ["unreliable-narrator"] * 2


def test_migration_leaves_author_spacing_alone(conn):
    """Author value_norm is a lowercased name; spaces belong in it."""
    seed(conn, "s1", 5, [("author", "w. w. jacobs")])
    db._migrate_tag_value_norm(conn)
    assert conn.execute("SELECT value_norm FROM tags WHERE kind='author'"
                        ).fetchone()["value_norm"] == "w. w. jacobs"


def test_migration_survives_a_story_holding_both_spellings(conn):
    """The PK (story_id, kind, value_norm) makes the merge a collision."""
    seed(conn, "s1", 5, [])
    conn.executemany(
        "INSERT INTO tags(story_id, kind, value_verbatim, value_norm) "
        "VALUES(?,?,?,?)",
        [("s1", "theme", "lost media", "lost media"),
         ("s1", "theme", "lost-media", "lost-media")])
    conn.commit()
    db._migrate_tag_value_norm(conn)
    rows_ = [r["value_norm"] for r in conn.execute(
        "SELECT value_norm FROM tags WHERE kind='theme'")]
    assert rows_ == ["lost-media"], "the duplicate is merged away, not doubled"


def test_migration_is_idempotent(conn):
    seed(conn, "s1", 5, [])
    conn.execute("INSERT INTO tags(story_id, kind, value_verbatim, value_norm) "
                 "VALUES('s1','theme','lost media','lost media')")
    conn.commit()
    db._migrate_tag_value_norm(conn)
    before = conn.execute("SELECT count(*) c FROM tags").fetchone()["c"]
    db._migrate_tag_value_norm(conn)
    assert conn.execute("SELECT count(*) c FROM tags").fetchone()["c"] == before
