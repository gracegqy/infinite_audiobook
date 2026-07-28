"""Free source registry (Entry 32).

The thing under test is not "does it find stories" — it is CHANNEL GENERALITY.
AMENDMENT_01 says nothing outside the channel row may assume horror, and the
creepypasta wiki is horror by nature. So the tests that earn their keep are the
ones proving a non-horror channel never sees it, and that a channel no source
covers gets a loud explanation rather than an empty pool or a silent paid run.

No network: coverage is pure over a channel row, and selection is tested against
a hand-built index.
"""
import json

import pytest

from pipeline import config, curate, db, freepool, sources


def channel(**over):
    base = {"id": 1, "name": "horror", "genre": "horror", "language": "en",
            "topics_json": None, "era": None, "exclusions_json": None,
            "extra_criteria": "Highly-reputed short horror fiction."}
    base.update(over)
    return base


# ---- coverage: the AMENDMENT_01 guard ----

def test_creepypasta_covers_a_horror_english_channel():
    ok, why = sources.CreepypastaWikiSource().covers(channel())
    assert ok and "wiki" in why.lower()


@pytest.mark.parametrize("over", [
    {"genre": "science fiction", "extra_criteria": "Golden-age SF."},
    {"genre": "mystery", "extra_criteria": "Detective stories."},
    {"genre": None, "extra_criteria": None},
])
def test_creepypasta_excludes_itself_from_non_horror_channels(over):
    """The whole reason the registry exists. A sci-fi channel that received
    creepypasta would be the AMENDMENT_01 violation."""
    ok, why = sources.CreepypastaWikiSource().covers(channel(**over))
    assert not ok
    assert "horror" in why.lower()


def test_creepypasta_excludes_itself_from_non_english_channels():
    ok, why = sources.CreepypastaWikiSource().covers(
        channel(language="zh", genre="horror"))
    assert not ok and "zh" in why


def test_creepypasta_honours_horror_stated_only_in_topics_or_extra():
    """Genre is not the only field a channel can express horror in — the editor
    exposes topics and extra_criteria too, and they reach the prompt (R12)."""
    assert sources.CreepypastaWikiSource().covers(
        channel(genre=None, topics_json=json.dumps(["ghost stories"]),
                extra_criteria=None))[0]
    assert sources.CreepypastaWikiSource().covers(
        channel(genre="fiction", topics_json=None,
                extra_criteria="modern creepypasta"))[0]


def test_gutenberg_covers_non_horror_channels_but_not_criteria_free_ones():
    src = sources.GutenbergCatalogSource()
    assert src.covers(channel(genre="science fiction"))[0]
    ok, why = src.covers(channel(genre=None, topics_json=None))
    assert not ok and "genre" in why


def sf_channel():
    """A genuinely non-horror channel: `extra_criteria` must be cleared too,
    since a source reads every criteria field, not just `genre`."""
    return channel(genre="science fiction", extra_criteria="Golden-age SF.")


def test_for_channel_splits_covering_from_skipped_with_reasons():
    covering, skipped = sources.for_channel(sf_channel())
    assert [s.name for s in covering] == ["gutenberg-catalog"]
    assert [s.name for s, _ in skipped] == ["creepypasta-wiki"]
    assert all(why for _, why in skipped)


def test_gather_raises_rather_than_returning_an_empty_pool(monkeypatch):
    """A channel nothing covers must STOP with an explanation. Returning [] would
    look like 'no stories exist', and falling back to the paid path would be a
    silent spend (AMENDMENT_04 A)."""
    monkeypatch.setattr(sources.GutenbergCatalogSource, "covers",
                        lambda self, ch: (False, "no catalog terms"))
    with pytest.raises(sources.NoFreeSource) as e:
        sources.gather(None, sf_channel(), [], 10, log=lambda *a: None)
    msg = str(e.value)
    assert "no catalog terms" in msg and "horror" in msg  # both reasons named
    assert "curation_mode=llm" in msg                      # and the way forward


# ---- the creepypasta index → candidates ----

def index(**pages):
    return {t: {"length": ln, "categories": ["Pasta of the Month"]}
            for t, ln in pages.items()}


def test_candidate_ref_is_the_page_title_so_it_cannot_be_wrong():
    """The paid path's dominant failure was a guessed source_ref (6 of 15 dead
    in Entry 27). Here the ref IS the key the fetcher takes."""
    c = sources.to_candidate("The Rake", {"categories": ["Spotlighted Pasta"]})
    assert c["source_ref"] == "The Rake" == c["title"]
    assert c["source_class"] == "creepypasta"
    assert c["license_class"] == "modern_private"
    assert c["evidence"] == ["Creepypasta Wiki editorial category: Spotlighted Pasta"]
    assert c["unverified"], "the weaker reputation claim must be stated"


def test_markup_length_prefilter_rejects_stubs_and_keeps_unknowns():
    assert not sources.plausible_length(config.MIN_STORY_CHARS - 1)
    assert sources.plausible_length(config.MIN_STORY_CHARS)
    assert sources.plausible_length(None)  # unknown is never a rejection


def test_upper_bound_is_padded_because_markup_is_not_prose():
    """Markup >= prose, so a markup length just over MAX_STORY_CHARS does NOT
    prove the story is too long — the real gate is verify/ingest on clean text.
    Rejecting here at exactly MAX would throw away usable stories."""
    assert sources.plausible_length(config.MAX_STORY_CHARS + 1)
    assert not sources.plausible_length(
        int(config.MAX_STORY_CHARS * sources.MARKUP_MAX_MULTIPLIER) + 1)


def test_candidates_drop_known_titles_and_out_of_range_pages(monkeypatch):
    monkeypatch.setattr(sources, "fetch_reputation_index",
                        lambda log=print, force=False: index(
                            **{"Good Story": 20000, "Stub": 10,
                               "Already Read": 20000}))
    out = sources.CreepypastaWikiSource().candidates(
        None, channel(), ["already read"], 10, log=lambda *a: None)
    assert [c["title"] for c in out] == ["Good Story"]


def test_gather_interleaves_sources_so_a_batch_is_never_all_one_kind(monkeypatch):
    """Balance is the thing the paid prompt kept failing at (Entries 27-28).
    Here it is structural, so it is worth pinning."""
    monkeypatch.setattr(sources.GutenbergCatalogSource, "candidates",
                        lambda self, c, ch, k, n, log=print: [
                            {"title": f"classic {i}", "source_class": "gutenberg"}
                            for i in range(n)])
    monkeypatch.setattr(sources.CreepypastaWikiSource, "candidates",
                        lambda self, c, ch, k, n, log=print: [
                            {"title": f"modern {i}", "source_class": "creepypasta"}
                            for i in range(n)])
    out = sources.gather(None, channel(), [], 6, log=lambda *a: None)
    classes = [c["source_class"] for c in out]
    assert classes == ["gutenberg", "creepypasta"] * 3


def test_gather_dedupes_a_title_two_sources_both_claim(monkeypatch):
    monkeypatch.setattr(sources.GutenbergCatalogSource, "candidates",
                        lambda self, c, ch, k, n, log=print: [
                            {"title": "The Rake", "source_class": "gutenberg"}])
    monkeypatch.setattr(sources.CreepypastaWikiSource, "candidates",
                        lambda self, c, ch, k, n, log=print: [
                            {"title": "the rake", "source_class": "creepypasta"}])
    out = sources.gather(None, channel(), [], 6, log=lambda *a: None)
    assert len(out) == 1


# ---- resilience: findings from the Phase 5 close review (Entry 33) ----

def test_one_failing_source_does_not_lose_the_others(monkeypatch):
    """Gutenberg and the wiki are independent networks. Losing the wiki should
    cost the modern half, not the whole build."""
    monkeypatch.setattr(sources.GutenbergCatalogSource, "candidates",
                        lambda self, c, ch, k, n, log=print: [
                            {"title": "classic", "source_class": "gutenberg"}])
    monkeypatch.setattr(sources.CreepypastaWikiSource, "candidates",
                        lambda self, c, ch, k, n, log=print: (_ for _ in ()).throw(
                            TimeoutError("wiki down")))
    out = sources.gather(None, channel(), [], 6, log=lambda *a: None)
    assert [c["title"] for c in out] == ["classic"]


def test_all_sources_failing_is_a_real_error(monkeypatch):
    for cls in (sources.GutenbergCatalogSource, sources.CreepypastaWikiSource):
        monkeypatch.setattr(cls, "candidates",
                            lambda self, c, ch, k, n, log=print: (
                                _ for _ in ()).throw(TimeoutError("down")))
    with pytest.raises(sources.NoFreeSource, match="transient"):
        sources.gather(None, channel(), [], 6, log=lambda *a: None)


def test_page_lengths_key_on_the_title_we_asked_for(monkeypatch):
    """MediaWiki normalizes titles ('the rake' → 'The rake'). Keying on the
    REPLY would drop those pages' lengths, or KeyError the caller's index."""
    monkeypatch.setattr(sources, "_api", lambda **p: {"query": {
        "normalized": [{"from": "the rake", "to": "The rake"}],
        "pages": {"1": {"title": "The rake", "length": 5000},
                  "2": {"title": "NoEnd House", "length": 27291}}}})
    assert sources._page_lengths(["the rake", "NoEnd House"]) == {
        "the rake": 5000, "NoEnd House": 27291}


def test_stale_index_is_used_when_the_refresh_fails(monkeypatch, tmp_path):
    """A month-old editorial list beats failing the pool build outright."""
    import json as _json
    cache = tmp_path / "creepypasta_reputation.json"
    cache.write_text(_json.dumps({"Old Story": {"length": 9000,
                                                "categories": ["PotM"]}}))
    import os
    old = cache.stat()
    os.utime(cache, (old.st_atime - 86400 * 90, old.st_mtime - 86400 * 90))
    monkeypatch.setattr(sources, "creepypasta_cache_path", lambda: cache)
    monkeypatch.setattr(sources, "_category_members",
                        lambda cat: (_ for _ in ()).throw(TimeoutError("down")))
    index = sources.fetch_reputation_index(log=lambda *a: None)
    assert index == {"Old Story": {"length": 9000, "categories": ["PotM"]}}


def test_no_cache_and_a_failed_refresh_still_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(sources, "creepypasta_cache_path",
                        lambda: tmp_path / "missing.json")
    monkeypatch.setattr(sources, "_category_members",
                        lambda cat: (_ for _ in ()).throw(TimeoutError("down")))
    with pytest.raises(TimeoutError):
        sources.fetch_reputation_index(log=lambda *a: None)
