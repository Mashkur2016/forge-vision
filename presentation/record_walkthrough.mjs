/**
 * Record each app page as a narrated 1080p segment, timed to its voiceover MP3,
 * with a gold pointer (no captions). Each page is recorded independently and
 * muxed with its MP3 → segments/seg_NN.mp4. Resumable: skips segments that exist.
 *
 * Run: cd presentation && node record_walkthrough.mjs            (all pages)
 *      cd presentation && node record_walkthrough.mjs 20 29      (only those ids)
 */
import { chromium } from 'playwright';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, rmSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { FF, VO, SEG, W, H, SPACE, EMAIL, PASS, durationOf, PAGES } from './pres_config.mjs';

if (!existsSync(SEG)) mkdirSync(SEG, { recursive: true });
const VID = resolve(SEG, '_rec');
const only = process.argv.slice(2);
const log = (...a) => console.log('·', ...a);
const sleep = ms => new Promise(r => setTimeout(r, ms));

const browser = await chromium.launch({ headless: true });

// ── FX: gold pointer + highlight ring (no caption) ─────────────────────────
const FX = `
if(!window.__fx){
  const css=document.createElement('style');css.textContent=\`
   #fc-ring{position:fixed;z-index:2147483645;pointer-events:none;border:3px solid #FFCC00;border-radius:14px;box-shadow:0 0 0 5px rgba(255,204,0,.16),0 0 30px rgba(255,204,0,.4);opacity:0;transition:left .6s cubic-bezier(.22,1,.36,1),top .6s cubic-bezier(.22,1,.36,1),width .6s,height .6s,opacity .3s}
   #fc-ring.on{opacity:1;animation:fcp 1.6s ease-in-out infinite}
   @keyframes fcp{0%,100%{box-shadow:0 0 0 5px rgba(255,204,0,.16),0 0 24px rgba(255,204,0,.32)}50%{box-shadow:0 0 0 9px rgba(255,204,0,.09),0 0 40px rgba(255,204,0,.6)}}
   #fc-ptr{position:fixed;z-index:2147483647;pointer-events:none;width:20px;height:20px;border-radius:50%;background:#FFCC00;box-shadow:0 0 0 5px rgba(255,204,0,.4);opacity:0;transition:left .6s cubic-bezier(.22,1,.36,1),top .6s cubic-bezier(.22,1,.36,1),opacity .3s}
   #fc-ptr.on{opacity:1}\`;document.head.appendChild(css);
  const r=document.createElement('div');r.id='forge-fx';r.innerHTML='<div id="fc-ring"></div><div id="fc-ptr"></div>';document.body.appendChild(r);
  window.__fx={point(b){const ring=document.getElementById('fc-ring'),p=document.getElementById('fc-ptr');ring.style.left=(b.x-10)+'px';ring.style.top=(b.y-10)+'px';ring.style.width=(b.width+20)+'px';ring.style.height=(b.height+20)+'px';ring.classList.add('on');p.style.left=(b.x+Math.min(b.width-8,36))+'px';p.style.top=(b.y+Math.min(b.height-8,30))+'px';p.classList.add('on');},hide(){document.getElementById('fc-ring')?.classList.remove('on');document.getElementById('fc-ptr')?.classList.remove('on');}};
}`;

function muxSplit(webm, t0, dur, mp3, out) {
  // take [t0, dur] of the recording, scale to 1080p, attach the MP3
  const r = spawnSync(FF, ['-y', '-ss', t0.toFixed(2), '-i', webm, '-i', mp3,
    '-map', '0:v', '-map', '1:a', '-t', dur.toFixed(2),
    '-vf', `scale=${W}:${H},fps=30,format=yuv420p`,
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
    '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-ac', '2', out],
    { stdio: 'ignore' });
  return r.status === 0;
}

async function recordPage(pg) {
  const out = join(SEG, `seg_${pg.id}.mp4`);
  if (existsSync(out)) { log(`seg_${pg.id} exists — skip`); return; }
  const mp3 = join(VO, pg.mp3);
  if (!existsSync(mp3)) { log(`seg_${pg.id} MISSING mp3 ${pg.mp3}`); return; }
  const dur = durationOf(mp3);

  if (existsSync(VID)) rmSync(VID, { recursive: true, force: true });
  mkdirSync(VID, { recursive: true });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir: VID, size: { width: W, height: H } } });
  ctx.setDefaultTimeout(25000);
  const page = await ctx.newPage();
  const base = Date.now();
  const elapsed = () => (Date.now() - base) / 1000;
  const ensureFx = () => page.evaluate(FX).catch(() => {});
  const point = async (loc) => { try { await ensureFx(); const el = (typeof loc === 'string' ? page.locator(loc) : loc).first(); await el.scrollIntoViewIfNeeded({ timeout: 4000 }).catch(() => {}); const b = await el.boundingBox(); if (b) await page.evaluate(x => window.__fx.point(x), b); } catch {} };
  const M = () => page.locator('[data-testid="stMain"]');
  const sb = () => page.locator('[data-testid="stSidebar"]');
  const byText = re => M().getByText(new RegExp(re, 'i'));
  const glide = async (px, steps = 24) => { await page.mouse.move(960, 540); for (let i = 0; i < steps; i++) { await page.mouse.wheel(0, px / steps); await sleep(45); } };
  const expand = () => page.evaluate(() => document.querySelectorAll('[data-testid="sidebar"] details,[data-testid="stSidebar"] details').forEach(d => d.open = true)).catch(() => {});
  const tab = async (name) => { await page.getByRole('tab', { name: new RegExp(name, 'i') }).first().click({ timeout: 6000 }).catch(() => {}); };

  let t0 = 0;
  try {
    await page.goto(SPACE, { waitUntil: 'domcontentloaded' });
    await page.locator('input[type="text"]').first().waitFor({ timeout: 20000 });
    await sleep(1500);

    if (pg.kind === 'login') {
      // Show the login page; type credentials slowly; DO NOT submit (submit happens after the window).
      await ensureFx();
      t0 = elapsed();
      const end = Date.now() + dur * 1000;
      await point(page.locator('input[type="text"]').first());
      await page.locator('input[type="text"]').first().pressSequentially(EMAIL, { delay: 90 });
      await sleep(800);
      await point(page.locator('input[type="password"]').first());
      await page.locator('input[type="password"]').first().pressSequentially(PASS, { delay: 90 });
      await point(page.getByRole('button', { name: /sign in/i }).first());
      while (Date.now() < end + 1000) await sleep(200);
    } else {
      // Log in first (untimed), then navigate, then the timed dwell begins.
      await page.locator('input[type="text"]').first().fill(EMAIL);
      await page.locator('input[type="password"]').first().fill(PASS);
      await page.getByRole('button', { name: /sign in/i }).first().click();
      await M().getByText(/System Status/i).first().waitFor({ timeout: 25000 }).catch(() => {});
      await sleep(1500);
      if (pg.topbarBtn) {
        // some pages (e.g. Help) open from the TOP BAR, not the sidebar
        await page.getByRole('button', { name: new RegExp('^' + pg.topbarBtn + '$', 'i') }).first().click({ timeout: 10000 }).catch(() => {});
        if (pg.wait) await M().getByText(new RegExp(pg.wait, 'i')).first().waitFor({ timeout: 14000 }).catch(() => {});
        await sleep(1800);
      } else if (pg.nav) {
        await expand();
        await sb().getByRole('button', { name: new RegExp(pg.nav, 'i') }).first().click({ timeout: 10000 }).catch(() => {});
        if (pg.wait) await M().getByText(new RegExp(pg.wait, 'i')).first().waitFor({ timeout: 14000 }).catch(() => {});
        await sleep(1800);
      }
      await ensureFx();
      t0 = elapsed();
      await focus(pg, dur, { page, point, glide, byText, M, sb, tab, expand, ensureFx, sleep });
    }
  } catch (e) { log(`seg_${pg.id} error:`, e.message.split('\n')[0]); }

  const path = await page.video().path();
  await ctx.close();        // finalises the webm
  await sleep(300);
  const ok = muxSplit(path, t0, dur, mp3, out);
  rmSync(VID, { recursive: true, force: true });
  log(`seg_${pg.id} (${dur.toFixed(1)}s, t0=${t0.toFixed(1)}) → ${ok ? 'OK' : 'FAIL'}`);
}

// ── per-page pointer choreography, time-filled to `dur` ────────────────────
async function focus(pg, dur, h) {
  const end = Date.now() + dur * 1000;
  const left = () => Math.max(0, (end - Date.now()) / 1000);
  const hold = async (s) => { const t = Date.now() + s * 1000; while (Date.now() < Math.min(t, end)) await h.sleep(150); };

  const kind = pg.focus || 'scroll';
  if (kind === 'topbar') {
    for (const t of ['View as', 'Help', 'Sign Out']) { await h.point(h.page.getByText(new RegExp(t, 'i')).first()); await hold(left() / 2); }
  } else if (kind === 'sidebar') {
    await h.expand();
    const items = ['Live Training', 'Analytics', 'Settings', 'My Account'];
    for (const it of items) { await h.point(h.sb().getByRole('button', { name: new RegExp(it, 'i') }).first()); await hold(dur / items.length); }
  } else if (kind === 'dashboard') {
    await h.point(h.byText('System Status')); await hold(dur * 0.3);
    await h.point(h.M().locator('[data-testid="stMetric"]').nth(1)); await hold(dur * 0.2);
    await h.point(h.byText('Live Activity Feed')); await hold(dur * 0.25);
    await h.glide(420); await h.point(h.byText('Recent Sessions')).catch(() => {});
  } else if (kind === 'analytics_tabs') {
    await h.point(h.M().locator('[data-testid="stMetric"]').first()); await hold(Math.min(8, dur * 0.1));
    const tabs = ['Session History', 'Worker Performance', 'SOP Analytics', 'Deviation Heatmap', 'Study Groups', 'Emotion Breakdown', 'Bias Audit'];
    for (const t of tabs) { if (left() < 2) break; await h.tab(t); await hold(left() / (tabs.length - tabs.indexOf(t))); }
  } else if (kind === 'help_tabs') {
    const tabs = ['Getting Started', 'API Reference', 'SOP Guide', 'Troubleshooting', 'About', 'Data'];
    for (const t of tabs) { if (left() < 2) break; await h.tab(t); await hold(left() / (tabs.length - tabs.indexOf(t))); }
  } else if (kind === 'simulation') {
    await h.point(h.byText('Experiment Configuration')); await hold(dur * 0.2);
    await h.page.getByRole('button', { name: /run hypothesis tests/i }).first().click({ timeout: 6000 }).catch(() => {});
    await h.hold ? null : null; await hold(dur * 0.15);
    for (const t of ['Errors per Task', 'Completion Time', 'Sessions to Competency']) { if (left() < 3) break; await h.tab(t); await hold(left() / 3); }
    await h.glide(500); await h.point(h.byText('Continual Learning')).catch(() => {});
  } else if (kind === 'logout') {
    const so = () => h.page.getByRole('button', { name: /^Sign Out$/i }).first();
    await h.point(so()).catch(() => {}); await hold(4);          // highlight Sign Out
    await so().click({ timeout: 8000 }).catch(() => {});         // sign out
    await h.sleep(3500);                                          // signed-out confirmation
    await h.ensureFx();
    const si = h.page.getByRole('button', { name: /sign in/i }).first();
    if (await si.count().catch(() => 0)) { await si.click({ timeout: 6000 }).catch(() => {}); await h.sleep(3000); }  // → login page
    await hold(left());
  } else if (kind === 'settings') {
    await h.point(h.byText('LLM Configuration')).catch(() => {}); await hold(7);
    await h.glide(220); await h.point(h.page.getByRole('button', { name: /Test Connection/i })).catch(() => {}); await hold(7);
    // scroll to the Feedback Demo and RUN it so the AI feedback is shown
    await h.byText('Feedback Demo').first().scrollIntoViewIfNeeded().catch(() => {});
    await h.sleep(700); await h.point(h.byText('Feedback Demo')).catch(() => {}); await hold(4);
    await h.page.getByRole('button', { name: /Generate comparison/i }).first().click({ timeout: 8000 }).catch(() => {});
    await h.sleep(7000);   // LLM generates the comparison
    await h.byText(/Rule-based template/i).first().scrollIntoViewIfNeeded().catch(() => {});
    await h.point(h.byText(/Rule-based template/i)).catch(() => {}); await hold(Math.min(6, left()));
    await h.point(h.byText(/LLM —/i)).catch(() => {}); await hold(left());   // hold on the AI feedback
  } else if (kind === 'createsop') {
    await h.point(h.byText('SOP Metadata')); await hold(dur * 0.3);
    await h.point(h.byText('Steps')).catch(() => {}); await hold(dur * 0.3);
    await h.glide(360); await hold(left());
  } else { // 'scroll' default
    await h.point(h.M().locator('h1,h2,h3').first()).catch(() => {});
    await hold(Math.min(6, dur * 0.25));
    await h.glide(420); await hold(dur * 0.3);
    await h.glide(380); await hold(left());
  }
  while (Date.now() < end + 800) await h.sleep(150);  // pad past the window for a clean split
}

const list = only.length ? PAGES.filter(p => only.includes(p.id)) : PAGES;
for (const pg of list) await recordPage(pg);
await browser.close();
log('walkthrough done. segments:', readdirSync(SEG).filter(f => /^seg_\d+\.mp4$/.test(f)).sort().join(' '));
