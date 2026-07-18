from pipeline.models import OffsetsManifest, StoryMeta
from pipeline import textproc


def test_story_meta_roundtrip_full():
    m = StoryMeta(
        id="abc123def456-the-willows", dedup_key="f" * 40, title="The Willows",
        source_class="gutenberg", source_url="https://www.gutenberg.org/ebooks/11438",
        license_class="pd", language="en", author="Algernon Blackwood", year=1907,
        curation_evidence=["Lovecraft's 'Supernatural Horror in Literature' essay"],
        tts_engine="kokoro", voice="af_heart", duration_s=4212.5,
        paragraph_count=180, created_at="2026-07-18T12:00:00+00:00")
    assert StoryMeta.decode(m.encode()) == m


def test_story_meta_roundtrip_nullables():
    m = StoryMeta(id="x", dedup_key="k", title="無名", source_class="local_import",
                  source_url="file:///import/wu-ming.txt",
                  license_class="modern_private", language="zh")
    assert StoryMeta.decode(m.encode()) == m
    assert m.author is None and m.year is None and m.curation_evidence == []


def test_offsets_manifest_roundtrip():
    offs = textproc.build_offsets(["one two", "three"], [3.25, 1.5])
    m = OffsetsManifest(engine="edge_tts", voice="zh-CN-YunxiNeural",
                        sample_rate=24000, paragraphs=offs)
    assert OffsetsManifest.decode(m.encode()) == m
