# FORGE-Vision — Presentation Kit (record-it-yourself edition)

Everything for the narrated walkthrough you'll record yourself, with your own
background music.

| File | What it is |
|------|------------|
| **`Forge-Vision_Presentation_Script.docx`** | The **master voiceover script**. Read the normal text aloud; the grey **"▶ On screen"** lines tell you what to click/show (not read). Covers Part 1 (intro slides), Part 2 (the full live-app walkthrough — every page, tab, sub-tab, button), Part 3 (conclusion). |
| **`intro_slides.html`** | The **intro slide deck** (7 slides) for Part 1 — what FORGE-Vision is, how it works, architecture, components. |
| **`outro_slides.html`** | The **conclusion deck** (3 slides) for Part 3. |
| `build_script_docx.py` | Regenerates the .docx (`python build_script_docx.py`). Edit this to change wording. |

> No audio is baked into the decks — you add your background music while recording.

---

## How to record

**1. Part 1 — Intro (slides + voiceover)**
- Open `intro_slides.html` in a browser, press **F** for full screen.
- Start your screen recorder (with your music) and read the **Part 1** narration from the
  `.docx`, advancing slides on each new heading (→ arrow / Space).

**2. Part 2 — Live app walkthrough (the main part)**
- Log in to the live system **as Admin** so every menu is visible:
  `https://huggingface.co/spaces/MashkurA/forge-vision` — `mashkur.alam@hotmail.co.uk`.
  *(Admin is required — the "View as" switcher and the Administration group only appear for admins.)*
- Follow **Part 2** of the `.docx` top to bottom: Login → Dashboard → Training → Data &
  Analytics → Administration → Account → Help → Logout. Read the narration; do what each
  **▶ On screen** cue says.
- Tips: 1920×1080, browser zoom 100%. Pause the recording between pages if you need to read ahead.
- For the **Live Training** scene, perform a real run (do a step, then **Skip a step or two**
  so deviations show) and let it reach the **Session Summary** — that's the strongest moment.

**3. Part 3 — Conclusion (slides + voiceover)**
- Open `outro_slides.html` full screen and read the **Part 3** narration.

---

## How to present the slide decks
- Full screen: **F**. Next/prev: **arrow keys** / **Space**. Overview: **Esc** / **O**.
- Export a deck to PDF (optional): open it with `?print-pdf` appended to the URL, then
  the browser's Print → Save as PDF.

---

## After you record — assembly
Once you've recorded the three parts (or just Part 2, if you film the slides separately),
hand me the clips and I'll stitch them into one file:

```
intro (slides)  →  your Part-2 walkthrough  →  conclusion (slides)
```

The existing `splice_live.mjs` / ffmpeg tooling in this folder handles the concatenation and
720p/1080p normalisation. If you'd rather, I can also screen-capture the two slide decks into
video automatically (silent), so you only narrate the app walkthrough.

---

## What the script covers (nothing skipped)
Login · Top bar (View-as role switcher, profile, Help, Sign Out) · Sidebar groups · Dashboard
(quick actions, System Status, metrics, activity feed, recent sessions) · **Live Training**
(consent, setup, live metrics, timers, step controls, camera, summary) · **Simulation**
(experiment config, power analysis, 3 distribution sub-tabs, H1/H2/H3, continual learning) ·
**Create SOP** (Create New + Upload Document) · Session History · Staff Profiles · SOP Library ·
**Analytics** (all 7 tabs) · Reports · Leaderboard · **Settings** (provider cards, test, feedback
demo) · User Management · System Health · Audit Log · Notifications · My Account · **Help** (6
tabs) · Logout.
