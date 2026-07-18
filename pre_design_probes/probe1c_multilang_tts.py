#!/usr/bin/env python3
"""Probe 1c: Kokoro zh + fr quality (AMENDMENT_03 gate for zh/fr channels).

Renders one modern-vernacular Chinese horror paragraph (original text written for this
probe — no copyright) in a female + male voice, and the PD opening of Maupassant's
Le Horla in French. Grace's ear is the gate. Throwaway code.

Texts are single-line on purpose — probe 1b: newlines cause chunk-break pauses.
"""
import pathlib
import subprocess
import time

import soundfile as sf
from kokoro import KPipeline

OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "interim" / "probe1c"
OUT.mkdir(parents=True, exist_ok=True)

ZH = (
    "楼道里的声控灯又亮了。我数着脚步声，一层，两层，在我门口停住。猫眼里没有人，"
    "只有对面那扇门，开着一条缝。我记得很清楚，三年前搬来的时候，物业说过，对面那户，"
    "从来没有住过人。我退回客厅，把电视的音量调大，可是没有用——脚步声再次响起的时候，"
    "是从我身后的卧室里传来的。"
)
FR = (
    "Quel jour admirable ! J'ai passé toute la matinée étendu sur l'herbe, devant ma "
    "maison, sous l'énorme platane qui la couvre, l'abrite et l'ombrage tout entière. "
    "J'aime ce pays, et j'aime y vivre parce que j'y ai mes racines, ces profondes et "
    "délicates racines, qui attachent un homme à la terre où sont nés et morts ses "
    "aïeux, qui l'attachent à ce qu'on pense et à ce qu'on mange, aux usages comme aux "
    "nourritures, aux locutions locales, aux intonations des paysans, aux odeurs du "
    "sol, des villages et de l'air lui-même."
)

JOBS = [
    ("z", "zf_xiaobei", ZH, "zh_original_zf_xiaobei"),
    ("z", "zm_yunxia", ZH, "zh_original_zm_yunxia"),
    ("f", "ff_siwis", FR, "fr_lehorla_ff_siwis"),
]

pipes = {}
for lang, voice, text, name in JOBS:
    if lang not in pipes:
        t0 = time.time()
        pipes[lang] = KPipeline(lang_code=lang)
        print(f"pipeline '{lang}' ready in {time.time()-t0:.1f}s")
    t0 = time.time()
    chunks = [audio for _, _, audio in pipes[lang](text, voice=voice)]
    import numpy as np
    wav = np.concatenate(chunks)
    dur, wall = len(wav) / 24000, time.time() - t0
    path = OUT / f"{name}.wav"
    sf.write(path, wav, 24000)
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac",
                    str(path), str(path.with_suffix(".m4a"))], check=True)
    print(f"{name}: {len(chunks)} chunk(s), {dur:.1f}s audio in {wall:.1f}s "
          f"({dur/wall:.1f}x realtime) -> {path.name} + .m4a")
print("done; files in data/interim/probe1c/ (served at /audio/probe1c/ on the probe5 server)")
