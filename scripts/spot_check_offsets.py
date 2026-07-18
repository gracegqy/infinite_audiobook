#!/usr/bin/env python3
"""Phase 3 gate helper: spot-check a library story's offsets at 3 paragraphs.

Mechanical checks: char spans slice story.txt exactly; times monotonic and
gap-free (butt-join); decoded audio length matches the manifest's total within
AAC-padding tolerance. Then cuts an 8 s clip at the start of the first, middle,
and last paragraph into data/interim/spotcheck/<story_id>/ next to each
paragraph's opening text — the ear check is "does the clip say these words".

Run: .venv/bin/python scripts/spot_check_offsets.py <story_id>
"""
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import soundfile as sf  # noqa: E402

from pipeline import config, synthesize  # noqa: E402
from pipeline.models import OffsetsManifest  # noqa: E402

CLIP_S = 8.0


def main(sid: str) -> int:
    story_dir = config.LIBRARY_DIR / sid
    text = (story_dir / "story.txt").read_text()
    manifest = OffsetsManifest.decode((story_dir / "offsets.json").read_text())
    paras = manifest.paragraphs

    ok = True
    true_paras = text.split("\n\n")
    if len(true_paras) != len(paras):
        print(f"FAIL: {len(true_paras)} paragraphs in story.txt vs "
              f"{len(paras)} in manifest")
        ok = False
    for o, expected in zip(paras, true_paras):
        # slice must equal the actual i-th paragraph — a strip()-style check
        # would pass systematically shifted spans
        if text[o["char_start"]:o["char_end"]] != expected or \
                o["t_end_s"] < o["t_start_s"]:
            print(f"FAIL para {o['i']}: span does not match paragraph text")
            ok = False
    for a, b in zip(paras, paras[1:]):
        if abs(b["t_start_s"] - a["t_end_s"]) > 1e-6 or \
                b["char_start"] != a["char_end"] + 2:
            print(f"FAIL contiguity between paras {a['i']} and {b['i']}")
            ok = False
    print(f"[check] {len(paras)} paragraphs contiguous (time + char): "
          f"{'OK' if ok else 'FAIL'}")

    samples, sr = synthesize.decode_audio_bytes(
        (story_dir / "audio.m4a").read_bytes(), ".m4a")
    audio_s, manifest_s = len(samples) / sr, paras[-1]["t_end_s"]
    drift = abs(audio_s - manifest_s)
    print(f"[check] audio {audio_s:.2f}s vs manifest {manifest_s:.2f}s "
          f"(drift {drift * 1000:.0f} ms): {'OK' if drift < 0.15 else 'FAIL'}")
    ok &= drift < 0.15

    out = config.INTERIM_DIR / "spotcheck" / sid
    out.mkdir(parents=True, exist_ok=True)
    picks = sorted({0, len(paras) // 2, len(paras) - 1})
    for i in picks:
        o = paras[i]
        s0 = int(o["t_start_s"] * sr)
        clip = samples[s0:s0 + int(CLIP_S * sr)]
        wav = out / f"para_{i:03d}.wav"
        sf.write(wav, clip, sr)
        m4a = wav.with_suffix(".m4a")
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(wav), str(m4a)],
                       check=True, capture_output=True)
        wav.unlink()
        opening = text[o["char_start"]:o["char_end"]][:160]
        (out / f"para_{i:03d}.txt").write_text(opening + "\n")
        print(f"[clip] para {i} @ {o['t_start_s']:8.2f}s -> {m4a.name}")
        print(f"       should say: {opening[:100]}...")
    print(f"\nclips in {out} — ear check: each clip must speak its .txt opening")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
