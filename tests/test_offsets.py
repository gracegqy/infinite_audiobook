import math
import pathlib
import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from pipeline import textproc
from pipeline.models import OffsetsManifest


def test_build_offsets_cumulative_and_char_spans():
    paras = ["alpha beta", "gamma", "delta epsilon zeta"]
    offs = textproc.build_offsets(paras, [1.5, 2.25, 0.75])
    assert [o["t_start_s"] for o in offs] == [0.0, 1.5, 3.75]
    assert [o["t_end_s"] for o in offs] == [1.5, 3.75, 4.5]
    # char spans index into "\n\n".join(paras)
    joined = "\n\n".join(paras)
    for p, o in zip(paras, offs):
        assert joined[o["char_start"]:o["char_end"]] == p


def test_build_offsets_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        textproc.build_offsets(["a", "b"], [1.0])


def test_build_offsets_rejects_negative_duration():
    with pytest.raises(ValueError):
        textproc.build_offsets(["a"], [-0.1])


def test_paragraph_at_binary_search():
    offs = textproc.build_offsets(["a", "b", "c"], [10.0, 5.0, 20.0])
    m = OffsetsManifest(engine="kokoro", voice="af_heart", sample_rate=24000,
                        paragraphs=offs)
    assert m.paragraph_at(0.0) == 0
    assert m.paragraph_at(9.99) == 0
    assert m.paragraph_at(10.0) == 1
    assert m.paragraph_at(14.9) == 1
    assert m.paragraph_at(15.0) == 2
    assert m.paragraph_at(999.0) == 2


@pytest.mark.skipif(shutil.which("afconvert") is None, reason="needs macOS afconvert")
def test_compressed_duration_math_survives_decode(tmp_path, monkeypatch):
    """DESIGN §5: edge-tts returns compressed audio; durations come from decoded
    sample counts. Round-trip a known-length tone through the same
    afconvert-decode path and check the duration is preserved."""
    from pipeline import config, synthesize
    monkeypatch.setattr(config, "INTERIM_DIR", tmp_path)

    sr, dur_s = 24000, 2.5
    t = np.linspace(0, dur_s, int(sr * dur_s), endpoint=False)
    tone = (0.3 * np.sin(2 * math.pi * 220 * t)).astype(np.float32)
    wav = tmp_path / "tone.wav"
    sf.write(wav, tone, sr)
    m4a = tmp_path / "tone.m4a"
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(wav), str(m4a)],
                   check=True, capture_output=True)

    samples, out_sr = synthesize.decode_audio_bytes(m4a.read_bytes(), ".m4a")
    assert out_sr == sr
    # AAC pads with encoder priming/remainder frames — accept < 100 ms drift
    assert abs(len(samples) / out_sr - dur_s) < 0.1
