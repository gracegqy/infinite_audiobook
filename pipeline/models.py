"""Serialized shapes: StoryMeta (meta.json) and OffsetsManifest (offsets.json).
Every shape gets a decode(encode(x)) == x round-trip test (CLAUDE.md rule;
tests/test_models_roundtrip.py)."""
import dataclasses
import json


@dataclasses.dataclass
class StoryMeta:
    id: str
    dedup_key: str
    title: str
    source_class: str        # gutenberg|creepypasta|nosleep|scp_cn|local_import|other
    source_url: str          # provenance, always (DESIGN §3)
    license_class: str       # pd|modern_private|cc_by_sa
    language: str            # en|zh|fr
    author: str | None = None
    year: int | None = None  # LLM-extracted → nullable
    curation_evidence: list[str] = dataclasses.field(default_factory=list)
    tts_engine: str | None = None
    voice: str | None = None
    duration_s: float | None = None
    paragraph_count: int | None = None
    created_at: str | None = None

    def encode(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def decode(cls, s: str) -> "StoryMeta":
        return cls(**json.loads(s))


@dataclasses.dataclass
class OffsetsManifest:
    engine: str
    voice: str
    sample_rate: int
    paragraphs: list[dict]   # entries from textproc.build_offsets
    version: int = 1

    def encode(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def decode(cls, s: str) -> "OffsetsManifest":
        return cls(**json.loads(s))

    def paragraph_at(self, t_s: float) -> int:
        """Index of the paragraph playing at time t_s (player highlight, R8).
        Binary search on t_start_s."""
        lo, hi = 0, len(self.paragraphs) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.paragraphs[mid]["t_start_s"] <= t_s:
                lo = mid
            else:
                hi = mid - 1
        return lo
