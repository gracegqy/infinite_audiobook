#!/usr/bin/env python3
"""Export a rendered story as .m4b -- the format an iPhone opens natively.

Why this and not the .html exporter: iOS will not reliably open a local .html
with a 12 MB data: URI in it. Files' preview is a Quick Look webview, not
Safari, and it is not a browser you can count on. A .m4b is what the phone is
actually built for: AirDrop it and Apple Books takes it, with lock-screen
controls, playback speed, a sleep timer and remembered position, all offline.

The trade is real and worth stating: .m4b carries audio + chapters, NOT the
synced text highlight. Use scripts/export_offline.py when the highlight is the
point (it works on a laptop or iPad); use this when listening is the point.

No re-encoding happens. The pipeline already writes 64k AAC in an MP4 container,
and .m4b IS that container under a different extension, so ffmpeg copies the
stream through untouched -- instant, and bit-identical audio.

  python3 scripts/export_m4b.py damned          # substring match
  python3 scripts/export_m4b.py --all           # every rendered story
  python3 scripts/export_m4b.py --list

Output defaults to data/interim/ (gitignored). CONTENT IS NEVER COMMITTED
(CLAUDE.md): private listening only, never a public deploy, never a git add.
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import config  # noqa: E402  -- after sys.path

# Paths come from pipeline.config, never from ROOT/"data" directly, so that
# HR_DATA_DIR redirects this exporter along with everything else (CLAUDE.md
# standing rule: never point a script at the live data/).
LIB = config.LIBRARY_DIR

# Group paragraphs into chapter marks of about this length. Short stories do not
# have real chapters, but skip targets make a 20-minute file navigable, and
# Apple Books shows them in a list.
CHAPTER_TARGET_S = 240


def _esc(s: str) -> str:
    """ffmetadata escaping: =, ;, #, \\ and newlines are special."""
    for ch in ("\\", "=", ";", "#"):
        s = s.replace(ch, "\\" + ch)
    return s.replace("\n", " ").strip()


def stories():
    if not LIB.is_dir():
        return []
    return [d for d in sorted(LIB.iterdir())
            if (d / "audio.m4a").is_file() and (d / "offsets.json").is_file()]


def chapters(offsets, duration_s):
    """Fold paragraphs into ~CHAPTER_TARGET_S blocks, titled by their opening words."""
    paras = offsets["paragraphs"]
    out, start, title = [], 0.0, None
    for p in paras:
        if title is None:
            title = None  # filled by caller from text; placeholder
        if p["t_end_s"] - start >= CHAPTER_TARGET_S:
            out.append((start, p["t_end_s"]))
            start = p["t_end_s"]
    if not out or start < duration_s - 1:
        out.append((start, duration_s))
    return out


def build_metadata(meta, offsets, text, duration_s):
    lines = [";FFMETADATA1"]
    lines.append(f"title={_esc(meta.get('title', ''))}")
    if meta.get("author"):
        lines.append(f"artist={_esc(meta['author'])}")
        lines.append(f"album_artist={_esc(meta['author'])}")
    lines.append(f"album={_esc(meta.get('title', ''))}")
    lines.append("genre=Audiobook")
    if meta.get("year"):
        lines.append(f"date={meta['year']}")
    lines.append(f"comment={_esc('Rendered locally with ' + str(meta.get('tts_engine','')) + ' / ' + str(meta.get('voice','')))}")

    # Chapter titles come from the first paragraph that starts inside the block,
    # so a skip target reads as a line of the story rather than "Chapter 3".
    paras = offsets["paragraphs"]
    for (t0, t1) in chapters(offsets, duration_s):
        opening = next((text[p["char_start"]:p["char_end"]].strip()
                        for p in paras if p["t_start_s"] >= t0 and
                        text[p["char_start"]:p["char_end"]].strip()), "")
        words = " ".join(opening.split())[:48]
        lines += ["[CHAPTER]", "TIMEBASE=1/1000",
                  f"START={int(t0*1000)}", f"END={int(t1*1000)}",
                  f"title={_esc(words or 'Part')}"]
    return "\n".join(lines) + "\n"


def export(story: pathlib.Path, outdir: pathlib.Path) -> pathlib.Path:
    meta = json.loads((story / "meta.json").read_text(encoding="utf-8"))
    offsets = json.loads((story / "offsets.json").read_text(encoding="utf-8"))
    text = (story / "story.txt").read_text(encoding="utf-8")
    src = story / "audio.m4a"
    duration_s = float(meta.get("duration_s") or offsets["paragraphs"][-1]["t_end_s"])

    outdir.mkdir(parents=True, exist_ok=True)
    ffmeta = outdir / (story.name + ".ffmeta")
    ffmeta.write_text(build_metadata(meta, offsets, text, duration_s), encoding="utf-8")
    out = outdir / (story.name + ".m4b")

    # -c copy: no re-encode. -map_metadata 1 pulls tags+chapters from the
    # metadata file. -map 0:a takes only the audio stream, so a stray cover or
    # data stream cannot break the copy.
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-i", str(src), "-i", str(ffmeta),
           "-map", "0:a", "-map_metadata", "1",
           "-c", "copy", "-f", "mp4", str(out)]
    subprocess.run(cmd, check=True)
    ffmeta.unlink()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("-o", "--outdir", default=str(config.INTERIM_DIR / "m4b"))
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. brew install ffmpeg")

    found = stories()
    if not found:
        sys.exit(f"no rendered stories in {LIB}")

    if args.list or (not args.story and not args.all):
        print(f"{len(found)} exportable:")
        for d in found:
            print(f"  {d.name}  ({(d/'audio.m4a').stat().st_size/1e6:.1f} MB)")
        return

    targets = found if args.all else \
        [d for d in found if args.story.lower() in d.name.lower()]
    if not targets:
        sys.exit(f"no story matching {args.story!r}. Try --list.")

    outdir = pathlib.Path(args.outdir).expanduser()
    for d in targets:
        out = export(d, outdir)
        print(f"wrote {out}  ({out.stat().st_size/1e6:.1f} MB)")
    print("\nAirDrop to the phone and choose Books. Works with no network.")


if __name__ == "__main__":
    main()
