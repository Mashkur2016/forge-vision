# FORGE-Vision — Presentation Kit

Everything needed to produce the DBA system-walkthrough video.

| File | What it is |
|------|------------|
| **`VideoScript.md`** | The shot-by-shot **storyboard + narration script** (~14 min, viva depth). What to show, what to click, and the exact voiceover to read. |
| **`slides.html`** | The **slide deck** (reveal.js, on-brand gold/dark). Opens in any browser — used for the intro/architecture/results/closing scenes. Press **F** for full screen, arrow keys to advance, **E** then print → PDF to export. |
| **`forge-vision-walkthrough.mp4`** | The **auto-rendered video** — a continuous track (intro slides → **every page** of the live app → closing slides) with **animated captions**, a **moving gold pointer + highlight ring** on the element being described, and a **background-music** bed. Produced by `capture.mjs`. |
| `capture.mjs` | The Playwright automation that records the video above. |
| `probe_pages.mjs` | One-off helper used to map each page's real content. Safe to delete. |

---

## The two ways to make the final video

**Option 1 — Narrate the auto-rendered reel (fastest).**
`forge-vision-walkthrough.mp4` is already a watchable, captioned walkthrough of the
live system (~3–5 min). Open it in any video editor (or PowerPoint), record your
voiceover over it using `VideoScript.md`, and export. Good for a concise demo.

**Option 2 — Record the full viva version yourself (recommended for examiners).**
For the full ~14-minute doctoral version, screen-record yourself following
`VideoScript.md`:
1. Open `slides.html` full-screen for the slide scenes (1–4, results, closing).
2. Open the live system `https://mashkura-forge-vision.hf.space` for the app scenes.
3. Use OBS Studio (free) or PowerPoint → *Insert → Screen Recording*; narrate live.
4. Stitch in the slide and app segments per the script's scene order.

> **Re-record the Live Training scene (Scene 6) with a real person at a workstation.**
> The auto-capture uses a synthetic webcam feed to prove the pipeline runs; a real
> subject is needed to show the pose skeleton and tool detection at their best.

---

## Regenerating the auto video

```bash
cd presentation
node capture.mjs
```
- Needs Node (already used here) + the packages in `package.json`
  (`playwright`, `@ffmpeg-installer/ffmpeg`) and the Chromium browser
  (`npx playwright install chromium`). All installed during setup.
- Output: `presentation/forge-vision-walkthrough.mp4` (raw `.webm` kept in `videos/`).
- Env knobs: `SPEED=1.3` slows every dwell (more reading time) · `HEADED=1`
  watch it run in a visible browser · `MUSIC_VOL=0.16` background-music level ·
  the live Space must be awake (open it once in a browser if it has been idle —
  free Spaces sleep after ~48 h).

It logs into the live Space, so it depends on the deployment being up and the
demo credentials being valid.

### Background music

By default the video ships with a soft, **royalty-free ambient bed synthesised by
ffmpeg** (a 4-chord loop) at low volume — safe to publish, no licensing.
To use your **own track**, drop a file named `music.mp3` (or `.wav`/`.m4a`/`.ogg`)
in `presentation/` and re-run `capture.mjs` — it's auto-detected, looped to length,
volume-balanced, and faded in/out. Tune the level with `MUSIC_VOL` (e.g. `0.10`
if you'll speak over it).

### Animations &amp; pointer

Each app scene fades its caption in, moves a gold pointer to the element being
described, and pulses a highlight ring around it — so the silent reel reads clearly
on its own. The closing slide credits **Mashkur Alam**.

---

## Adding your real Live SOP Test (final submission)

The walkthrough ships with a *synthetic* camera scene. For the final cut, record
yourself doing a real live SOP test and splice it in with `splice_live.mjs`.

**Live test sessions are now saved to the database** (deployed to the Space), so a
real test shows up in Session History, the Dashboard activity feed, and Analytics —
which is the second thing to record.

**1. Record on the live Space** (`https://huggingface.co/spaces/MashkurA/forge-vision`):
   - **Clip A — the test:** Training → Live Training → consent → pick an SOP → Start
     → allow camera → perform the procedure (do a step or two correctly, then a
     deliberate deviation to trigger AI feedback) → finish to the **Session Summary**
     (it shows "✅ Saved to the research database"). Screen-record the whole thing.
   - **Clip B — the data it captured:** *immediately after*, screen-record the
     **Dashboard** (your session at the top of the activity feed) and **Session
     History** (open your session in the drill-down to show its deviations).
   - Save them in `presentation/` as `live_test.mp4` and `session_report.mp4`
     (any common format works — they're auto-normalised to 720p).

**2. Splice them in:**
```bash
cd presentation
node splice_live.mjs live_test.mp4 session_report.mp4
# → forge-vision-walkthrough-FINAL.mp4   (base file is left untouched)
```
- The clips replace the synthetic Live Training scene (the slot at `START=82`…`END=108` s).
- The first clip gets a gold **"LIVE SOP TEST · Mashkur Alam"** lower-third for 6 s.
- Each clip is scaled/padded to 1280×720, fades in/out, audio kept (or silent).
- Env overrides: `START` / `END` (seconds), `NAME`, `NO_TITLE=1`.

You can pass one clip or several; order is preserved. That `-FINAL.mp4` is your
submission master.

---

## Keep these figures accurate

Model 85.8% test accuracy · macro-F1 0.875 · p95 latency 62 ms · 2.3 M params.
H1 control 8.30 vs hybrid 2.80 deviations/worker (p≈0, d≈−3.4) ·
H2 ANOVA p≈0, η²≈0.27 · weighted accuracy hybrid 70.4% > real-time 60.4% >
simulation 49.4% > control 21.6%.
