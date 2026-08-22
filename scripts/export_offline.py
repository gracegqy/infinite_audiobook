#!/usr/bin/env python3
"""Export one story as a SINGLE self-contained .html for offline listening.

Why this exists: the apps are reachable only while the Mac is awake and on the
tailnet. On a plane, in a dead-zone, or with the laptop shut, there is no
server to talk to. This bakes one already-rendered story -- audio, text and the
paragraph offsets that drive highlight sync -- into one file that needs no
network, no server and no service worker.

Deliberately NOT a PWA cache. iOS evicts PWA storage without warning, which is
exactly the failure you cannot debug on a train. A file in the Files app is not
evictable, and copying it to the phone is a one-time act Grace controls.

  python3 scripts/export_offline.py damned            # substring match on id/title
  python3 scripts/export_offline.py --list            # what can be exported
  python3 scripts/export_offline.py damned -o ~/x.html

Output defaults to data/interim/ (gitignored). CONTENT IS NEVER COMMITTED
(CLAUDE.md): the exported file contains the full text and audio, so it is
treated exactly like data/library -- private listening only, never a public
deploy, never a git add.
"""
import argparse
import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import config  # noqa: E402  -- after sys.path

# Paths come from pipeline.config, never from ROOT/"data" directly, so that
# HR_DATA_DIR redirects this exporter along with everything else. A script that
# resolves the library itself silently escapes the sandbox (CLAUDE.md standing
# rule: never point a script at the live data/).
LIB = config.LIBRARY_DIR

# Kept in one place: the audio container the pipeline writes (64k AAC in m4a).
# If synthesize.py's container ever changes, change it here too -- a wrong MIME
# makes Safari refuse to play with no error message at all.
AUDIO_MIME = "audio/mp4"


def stories():
    if not LIB.is_dir():
        return []
    out = []
    for d in sorted(LIB.iterdir()):
        if (d / "audio.m4a").is_file() and (d / "offsets.json").is_file():
            out.append(d)
    return out


def pick(term):
    found = stories()
    if not found:
        sys.exit(f"no rendered stories in {LIB}")
    hits = [d for d in found if term.lower() in d.name.lower()]
    if not hits:
        sys.exit(f"no story matching {term!r}. Try --list.")
    if len(hits) > 1:
        names = "\n  ".join(d.name for d in hits)
        sys.exit(f"{term!r} matches {len(hits)} stories, be more specific:\n  {names}")
    return hits[0]


def build(story: pathlib.Path) -> str:
    meta = json.loads((story / "meta.json").read_text(encoding="utf-8"))
    offsets = json.loads((story / "offsets.json").read_text(encoding="utf-8"))
    text = (story / "story.txt").read_text(encoding="utf-8")
    audio_b64 = base64.b64encode((story / "audio.m4a").read_bytes()).decode("ascii")

    # Slice the text by the SAME char offsets the player uses, rather than
    # re-splitting on blank lines. Re-splitting is how the highlight drifts out
    # of sync with the audio: offsets.json is the authority, story.txt is just
    # the character array it indexes into.
    paras = []
    for p in offsets["paragraphs"]:
        paras.append({
            "t0": p["t_start_s"],
            "t1": p["t_end_s"],
            "text": text[p["char_start"]:p["char_end"]],
        })

    payload = json.dumps({
        "title": meta.get("title", story.name),
        "author": meta.get("author") or "",
        "year": meta.get("year") or "",
        "license_class": meta.get("license_class", "unknown"),
        "duration_s": meta.get("duration_s", 0),
        "id": meta.get("id", story.name),
        "paras": paras,
    }, ensure_ascii=False)

    return (TEMPLATE
            .replace("__PAYLOAD__", payload)
            .replace("__AUDIO__", f"data:{AUDIO_MIME};base64,{audio_b64}"))


TEMPLATE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>offline story</title>
<style>
:root{--bg:#faf8f5;--fg:#1a1a1a;--dim:#6b6b6b;--hi:#fff2c2;--line:#e4ded4;--accent:#7a5c2e}
@media(prefers-color-scheme:dark){:root{--bg:#14140f;--fg:#e8e4db;--dim:#8f8a80;--hi:#3a3218;--line:#2c2a24;--accent:#d8b463}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:1.15rem/1.75 Iowan Old Style,Palatino,Georgia,serif;
 padding:1rem 1rem calc(7.5rem + env(safe-area-inset-bottom))}
header{border-bottom:1px solid var(--line);padding-bottom:.75rem;margin-bottom:1.25rem}
h1{font-size:1.4rem;margin:0 0 .2rem}
.by{color:var(--dim);font-size:.95rem}
.warn{margin-top:.6rem;padding:.5rem .65rem;border-left:3px solid var(--accent);
 background:color-mix(in srgb,var(--accent) 12%,transparent);font-size:.85rem;line-height:1.5}
p.para{margin:0 0 1.1rem;padding:.2rem .4rem;border-radius:.3rem;cursor:pointer;
 transition:background .15s;white-space:pre-wrap}
p.para.on{background:var(--hi)}
#bar{position:fixed;left:0;right:0;bottom:0;background:var(--bg);
 border-top:1px solid var(--line);padding:.6rem .8rem calc(.6rem + env(safe-area-inset-bottom));
 display:flex;gap:.7rem;align-items:center}
button{font:inherit;font-size:1.5rem;line-height:1;border:1px solid var(--line);
 background:transparent;color:var(--fg);border-radius:.5rem;padding:.35rem .7rem;cursor:pointer}
#seek{flex:1;accent-color:var(--accent)}
#t{color:var(--dim);font-size:.85rem;font-variant-numeric:tabular-nums;min-width:5.5rem;text-align:right}
</style></head><body>
<header>
  <h1 id="ti"></h1><div class="by" id="au"></div>
  <div class="warn" id="lic"></div>
</header>
<main id="body"></main>
<div id="bar">
  <button id="back" aria-label="back 15 seconds">↺</button>
  <button id="pp" aria-label="play or pause">▶</button>
  <input id="seek" type="range" min="0" max="1000" value="0">
  <span id="t">0:00</span>
</div>
<audio id="a" preload="metadata" src="__AUDIO__"></audio>
<script>
const D=__PAYLOAD__, a=document.getElementById('a'), body=document.getElementById('body');
document.title=D.title;
document.getElementById('ti').textContent=D.title;
document.getElementById('au').textContent=[D.author,D.year].filter(Boolean).join(' · ');
document.getElementById('lic').textContent = D.license_class==='pd'
  ? 'Public domain. This file is yours to keep; it works with no network.'
  : 'Author-owned text, stored for private listening only. Do not share this file.';

const nodes=D.paras.map((p,i)=>{
  const el=document.createElement('p');
  el.className='para'; el.textContent=p.text;
  el.onclick=()=>{a.currentTime=p.t0; a.play();};
  body.appendChild(el); return el;
});

// Resume position survives closing the tab. localStorage, not a server call --
// the whole point is that there is no server.
const KEY='off:'+D.id;
const saved=parseFloat(localStorage.getItem(KEY)||'0');
if(saved>0) a.addEventListener('loadedmetadata',()=>{a.currentTime=saved;},{once:true});

const fmt=s=>{s=Math.max(0,Math.floor(s||0));const m=Math.floor(s/60);
  return m+':'+String(s%60).padStart(2,'0');};

let cur=-1;
// Linear scan from the last known index: the list is time-ordered and playback
// is monotonic, so this is O(1) per tick in the normal case and correct after a
// seek. A binary search would be faster in theory and harder to read for no
// gain at 78 paragraphs.
function sync(){
  const t=a.currentTime; let i=cur>=0&&D.paras[cur]&&t>=D.paras[cur].t0?cur:0;
  while(i<D.paras.length-1&&t>=D.paras[i].t1) i++;
  while(i>0&&t<D.paras[i].t0) i--;
  if(i!==cur){
    if(nodes[cur])nodes[cur].classList.remove('on');
    cur=i; nodes[i].classList.add('on');
    const r=nodes[i].getBoundingClientRect();
    if(r.top<80||r.bottom>innerHeight-140)
      nodes[i].scrollIntoView({block:'center',behavior:'smooth'});
  }
}
a.ontimeupdate=()=>{
  sync();
  document.getElementById('t').textContent=fmt(a.currentTime)+' / '+fmt(a.duration||D.duration_s);
  if(a.duration) document.getElementById('seek').value=Math.round(a.currentTime/a.duration*1000);
  localStorage.setItem(KEY,a.currentTime);
};
document.getElementById('seek').oninput=e=>{
  if(a.duration) a.currentTime=e.target.value/1000*a.duration;
};
const pp=document.getElementById('pp');
pp.onclick=()=>a.paused?a.play():a.pause();
a.onplay=()=>pp.textContent='⏸'; a.onpause=()=>pp.textContent='▶';
document.getElementById('back').onclick=()=>{a.currentTime=Math.max(0,a.currentTime-15);};
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story", nargs="?", help="substring of the story id or slug")
    ap.add_argument("-o", "--out", help="output path (default: data/interim/<id>.html)")
    ap.add_argument("--list", action="store_true", help="list exportable stories")
    args = ap.parse_args()

    if args.list or not args.story:
        found = stories()
        if not found:
            sys.exit(f"no rendered stories in {LIB}")
        print(f"{len(found)} exportable:")
        for d in found:
            mb = (d / "audio.m4a").stat().st_size / 1e6
            print(f"  {d.name}  ({mb:.1f} MB audio -> ~{mb*4/3:.0f} MB html)")
        return

    story = pick(args.story)
    html = build(story)
    out = pathlib.Path(args.out).expanduser() if args.out else \
        config.INTERIM_DIR / f"{story.name}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    mb = out.stat().st_size / 1e6
    print(f"wrote {out}  ({mb:.1f} MB)")
    if mb > 60:
        print("  WARNING: over 60 MB. Mobile Safari may stall loading a single file "
              "this large -- export a shorter story, or split it.", file=sys.stderr)
    print("  AirDrop it to the phone, then Save to Files. It needs no network.")


if __name__ == "__main__":
    main()
