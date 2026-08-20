# AMENDMENT 07 — Hosting moves off the Mac to an always-on tailnet host (2026-08-19)

> **Authority: HIGHEST**, applied on top of BRIEF_VERBATIM.md + AMENDMENTS 01–06
> + DESIGN v1.0. Status: **BINDING** on arrival — this is Grace's direct
> instruction, not a proposal of mine. Never edited from here; further changes
> are new amendment docs.

## Verbatim (Grace, 2026-08-19)

> "looking at active/ french_passerelle, ebook_readaloud, and infinite_audiobook, is
> there a way to change the hosting now, so that I can access the apps on mobile alone
> anytime without needing to boot the local server on my laptop?"

and, on the rights question after the options were laid out:

> "the 'not public' line was mostly a note-to-self about not violating ebook licencing
> by making things public, i think. if i cloud host, wouldn't i be able to access the
> apps even when my laptop is off (which is a lot of the use cases)? as long as i don't
> share the ebooks with others, i don't see the issue"

## What this contradicts

`BRIEF_VERBATIM.md` → Interview answers (2026-07-18), item 3:

> **Hosting:** Grace's Mac + Tailscale; app and audio never leave her machines. $0/mo.

Two clauses of that line are superseded: **"never leave her machines"** and **"$0/mo"**.
The rest of the brief is untouched.

## Ruling

1. **The app moves to one always-on host joined to Grace's tailnet.** Rented VM or owned
   mini/Pi is open; always-on and tailnet-joined is the binding part.
2. **It stays tailnet-only.** No public URL, no port forwarding, no Tailscale Funnel. A
   tailnet-joined host *is* remote hosting — it is reachable from the phone anywhere, with
   the laptop off — and it has no public surface. Any future session reading "cloud
   hosting" here and reaching for a public deploy is misreading this amendment.
3. **The Tailscale-only bind stays, including its refusal to start.** `scripts/serve.sh`
   resolves the live Tailscale IP and refuses to start without one; on the host it resolves
   the host's own address. That behavior is kept verbatim in spirit, not weakened. DESIGN §1
   / negative spec §10 survive this amendment intact.
4. **Rendering moves with the app.** Pool builds and renders are triggered from the UI
   (`POST /api/channels/{cid}/build`, the render routes), so the server is the renderer.
   Kokoro runs on the host.
5. **`$0/mo` is retired as a constraint** if the host is rented. The figure is not estimated
   anywhere in this repo — it is recorded at purchase, per `NUMBERS_PROTOCOL.md`.

## What does not change

- **One listener. Not public, no accounts, no sharing, no redistribution.** The content
  posture in CLAUDE.md — classics public-domain, modern web fiction author-owned and stored
  for private listening only — is unchanged and unweakened.
- `data/` is still never committed. Story text and audio still never appear in git.
- The spend cap, the Grace-initiated-only rule for paid pool builds (AMENDMENT_04 A), and
  every gate in TASKS.md.
- Ports: this repo keeps 8123; `ebook_readaloud` keeps 8124. Both land on the same host and
  the separation still matters.

## Grace's rights ruling, recorded

The brief's private-use language was about **not redistributing** the content, not about
which machine holds the files. Private hosting is not publishing, and this amendment keeps
the no-redistribution invariant. The honest delta: the audio and story text now sit on a
machine Grace does not physically hold, under a provider's terms and abuse process. That is
what "never leave her machines" bought, and it is what is being given up — knowingly, by her
call, after it was named.

## Two honest limits (accepted, not worked around)

- **Kokoro on the host is slower than on the M3, by an unmeasured amount.** No figure is
  offered here. Gate M2 in `_META_working_knowledge/reference/tailnet_host_migration.md`
  benchmarks it against this repo's measured baselines before any library moves. The trade
  is likely fine — rendering is batch and unattended, listening is constant — but "likely
  fine" is not a measurement, and the gate exists so it does not become one by repetition.
- **Nothing here is executed.** This amendment records a decision, not a state. The app runs
  on the Mac until gate M4 says otherwise, and `README.md` still describes the Mac
  deployment — deliberately, because editing it now would document a deployment that does
  not exist. See the README debt in the shared spec.

## Traceability

Supersedes two clauses of the brief's interview answer 3; no schema change; no change to the
offsets math, the iOS rules, the curation cost modes, or any phase gate. Migration procedure
and gates live in `_META_working_knowledge/reference/tailnet_host_migration.md` (shared with
`ebook_readaloud` and `french_passerelle`, which move to the same host).
