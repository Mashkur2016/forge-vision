/**
 * Render intro + outro slides as narrated 1080p video segments.
 * For each slide: screenshot full-screen, hold for its MP3 duration, mux the MP3.
 * Output: segments/seg_00..06 (intro), seg_90..92 (outro).
 *
 * Run: cd presentation && node render_slides.mjs
 */
import { chromium } from 'playwright';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { FF, DIR, VO, SEG, W, H, durationOf, INTRO, OUTRO } from './pres_config.mjs';

if (!existsSync(SEG)) mkdirSync(SEG, { recursive: true });
const log = (...a) => console.log('·', ...a);

const browser = await chromium.launch({ headless: true });
const page = await (await browser.newContext({ viewport: { width: W, height: H } })).newPage();

async function shot(deckFile, slideIdx, outPng) {
  await page.goto(pathToFileURL(resolve(DIR, deckFile)).href);
  await page.waitForTimeout(900);
  await page.evaluate(i => window.Reveal.slide(i), slideIdx);
  await page.waitForTimeout(700);
  await page.screenshot({ path: outPng });
}

function slideClip(png, mp3, out) {
  const dur = durationOf(mp3);
  const fo = Math.max(0.1, dur - 0.4).toFixed(2);
  const vf = `scale=${W}:${H},format=yuv420p,fade=t=in:st=0:d=0.4,fade=t=out:st=${fo}:d=0.4`;
  const r = spawnSync(FF, ['-y', '-loop', '1', '-i', png, '-i', mp3,
    '-filter_complex', `[0:v]${vf}[v]`, '-map', '[v]', '-map', '1:a',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-r', '30',
    '-c:a', 'aac', '-b:a', '192k', '-t', dur.toFixed(2), '-shortest', out],
    { stdio: 'ignore' });
  return r.status === 0;
}

for (const [deck, list, tag] of [['intro_slides.html', INTRO, 'intro'], ['outro_slides.html', OUTRO, 'outro']]) {
  for (const s of list) {
    const png = join(SEG, `_slide_${s.id}.png`);
    const mp3 = join(VO, s.mp3);
    const out = join(SEG, `seg_${s.id}.mp4`);
    if (!existsSync(mp3)) { log('MISSING mp3:', s.mp3); continue; }
    await shot(deck, s.slide, png);
    const ok = slideClip(png, mp3, out);
    log(`${tag} seg_${s.id} (${durationOf(mp3).toFixed(1)}s) → ${ok ? 'OK' : 'FAIL'}`);
  }
}
await browser.close();
log('slides done');
