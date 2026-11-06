/**
 * FORGE-Vision — automated walkthrough video capture (animated edition).
 *
 * Records a continuous track: intro slides → full live-app page tour → closing
 * slides, with an FX layer that (a) animates each caption in, (b) moves a gold
 * pointer to the element being described, and (c) draws a pulsing highlight ring
 * around it. Output: presentation/forge-vision-walkthrough.mp4
 *
 * The live-camera scene uses a SYNTHETIC webcam feed (Chromium fake device) to
 * prove the pipeline runs; re-record it with a real subject for the final cut.
 *
 * Run:  cd presentation && node capture.mjs
 * Env:  SPEED=1.0 (dwell multiplier) · HEADED=1 (watch it run)
 */
import { chromium } from 'playwright';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve, join } from 'node:path';
import ffmpeg from '@ffmpeg-installer/ffmpeg';

const __dir = dirname(fileURLToPath(import.meta.url));
const SPACE = 'https://mashkura-forge-vision.hf.space';
const EMAIL = 'mashkur.alam@hotmail.co.uk';
const PASS  = 'ForgeDemo123!';
const SLIDES = pathToFileURL(resolve(__dir, 'slides.html')).href;
const SPEED = parseFloat(process.env.SPEED || '1');
const VID_DIR = resolve(__dir, 'videos');
const OUT_MP4 = resolve(__dir, 'forge-vision-walkthrough.mp4');
const W = 1280, H = 720;

const log = (...a) => console.log('·', ...a);
const sleep = (s) => new Promise(r => setTimeout(r, s * 1000 * SPEED));

if (existsSync(VID_DIR)) rmSync(VID_DIR, { recursive: true, force: true });
mkdirSync(VID_DIR, { recursive: true });

const browser = await chromium.launch({
  headless: !process.env.HEADED,
  args: [
    '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
    '--autoplay-policy=no-user-gesture-required',
    '--disable-blink-features=AutomationControlled',
  ],
});
const ctx = await browser.newContext({
  viewport: { width: W, height: H },
  permissions: ['camera', 'microphone'],
  recordVideo: { dir: VID_DIR, size: { width: W, height: H } },
});
ctx.setDefaultTimeout(20000);
let navFails = 0, bail = false;   // if the Space stops responding, skip to the closing slides
const page = await ctx.newPage();
page.on('console', m => { if (m.type() === 'error') log('  [page-err]', m.text().slice(0, 100)); });

// ── FX layer: animated caption + moving pointer + highlight ring ───────────
async function ensureFx() {
  await page.evaluate(() => {
    if (window.__fx) return;
    const css = document.createElement('style');
    css.textContent = `
      #forge-fx, #forge-fx *{ box-sizing:border-box; }
      #fc-cap{ position:fixed; left:0; right:0; bottom:0; z-index:2147483646; pointer-events:none;
        padding:20px 34px 26px; font-family:Inter,'Segoe UI',sans-serif;
        background:linear-gradient(to top, rgba(7,11,20,.95) 28%, rgba(7,11,20,0)); }
      #fc-t{ font-family:Anton,Inter,sans-serif; letter-spacing:2px; text-transform:uppercase;
        color:#FFCC00; font-size:15px; margin-bottom:7px; opacity:0; transform:translateY(10px);
        transition:opacity .45s ease, transform .45s ease; }
      #fc-x{ color:#eef3fb; font-size:21px; line-height:1.36; max-width:1060px;
        text-shadow:0 1px 3px rgba(0,0,0,.6); opacity:0; transform:translateY(14px);
        transition:opacity .55s ease .08s, transform .55s ease .08s; }
      #fc-cap.show #fc-t, #fc-cap.show #fc-x{ opacity:1; transform:translateY(0); }
      #fc-ring{ position:fixed; z-index:2147483645; pointer-events:none; border:3px solid #FFCC00;
        border-radius:12px; box-shadow:0 0 0 4px rgba(255,204,0,.18), 0 0 26px rgba(255,204,0,.35);
        opacity:0; transition:left .6s cubic-bezier(.22,1,.36,1), top .6s cubic-bezier(.22,1,.36,1),
        width .6s cubic-bezier(.22,1,.36,1), height .6s cubic-bezier(.22,1,.36,1), opacity .3s ease; }
      #fc-ring.on{ opacity:1; animation:fcpulse 1.6s ease-in-out infinite; }
      @keyframes fcpulse{ 0%,100%{ box-shadow:0 0 0 4px rgba(255,204,0,.18),0 0 22px rgba(255,204,0,.30);}
        50%{ box-shadow:0 0 0 7px rgba(255,204,0,.10),0 0 34px rgba(255,204,0,.55);} }
      #fc-ptr{ position:fixed; z-index:2147483647; pointer-events:none; width:26px; height:26px;
        margin:-2px 0 0 -2px; opacity:0; transition:left .6s cubic-bezier(.22,1,.36,1),
        top .6s cubic-bezier(.22,1,.36,1), opacity .3s ease;
        filter:drop-shadow(0 2px 3px rgba(0,0,0,.5)); }
      #fc-ptr.on{ opacity:1; }
      #fc-ptr .dot{ position:absolute; left:0; top:0; width:14px; height:14px; border-radius:50%;
        background:#FFCC00; box-shadow:0 0 0 3px rgba(255,204,0,.35); }
      #fc-ptr .wave{ position:absolute; left:-6px; top:-6px; width:26px; height:26px; border-radius:50%;
        border:2px solid rgba(255,204,0,.7); animation:fcwave 1.4s ease-out infinite; }
      @keyframes fcwave{ 0%{ transform:scale(.4); opacity:.9;} 100%{ transform:scale(1.9); opacity:0;} }`;
    document.head.appendChild(css);
    const root = document.createElement('div'); root.id = 'forge-fx';
    root.innerHTML = `<div id="fc-cap"><div id="fc-t"></div><div id="fc-x"></div></div>
      <div id="fc-ring"></div>
      <div id="fc-ptr"><span class="wave"></span><span class="dot"></span></div>`;
    document.body.appendChild(root);
    window.__fx = {
      cap(title, text) {
        const cap = document.getElementById('fc-cap');
        document.getElementById('fc-t').textContent = title;
        document.getElementById('fc-x').textContent = text;
        cap.classList.remove('show'); void cap.offsetWidth; cap.classList.add('show');
      },
      point(b) {
        const ring = document.getElementById('fc-ring'), ptr = document.getElementById('fc-ptr');
        const pad = 8;
        ring.style.left = (b.x - pad) + 'px'; ring.style.top = (b.y - pad) + 'px';
        ring.style.width = (b.width + pad * 2) + 'px'; ring.style.height = (b.height + pad * 2) + 'px';
        ring.classList.add('on');
        const px = b.x + Math.min(b.width - 6, 30), py = b.y + Math.min(b.height - 6, 26);
        ptr.style.left = px + 'px'; ptr.style.top = py + 'px'; ptr.classList.add('on');
      },
      hide() {
        document.getElementById('fc-ring')?.classList.remove('on');
        document.getElementById('fc-ptr')?.classList.remove('on');
      },
    };
  }).catch(() => {});
}
async function cap(title, text) { log('CAP:', title); await ensureFx(); await page.evaluate(a => window.__fx.cap(a.t, a.x), { t: title, x: text }); }
async function hideFx() { await page.evaluate(() => window.__fx && window.__fx.hide()).catch(()=>{}); }
async function point(loc, dwell = 2.6) {
  try {
    await ensureFx();
    const el = (typeof loc === 'string' ? page.locator(loc) : loc).first();
    await el.scrollIntoViewIfNeeded({ timeout: 5000 }).catch(()=>{});
    const b = await el.boundingBox();
    if (b) await page.evaluate(box => window.__fx.point(box), b);
    else log('  (no bbox)');
    await sleep(dwell);
  } catch (e) { log('  point skip:', e.message.split('\n')[0]); await sleep(dwell); }
}
async function glide(px = 500, steps = 26) { for (let i=0;i<steps;i++){ await page.mouse.wheel(0, px/steps); await sleep(0.05);} }

// ── slides ────────────────────────────────────────────────────────────────
async function slide(n, dwell) {
  if (!page.url().startsWith('file:')) { await page.goto(SLIDES); await sleep(1.2); }
  await page.evaluate(i => window.Reveal && window.Reveal.slide(i), n);
  await sleep(dwell);
}

// ── app helpers ───────────────────────────────────────────────────────────
const sb = () => page.locator('[data-testid="stSidebar"]');
const M = () => page.locator('[data-testid="stMain"]');
async function expandGroups() {
  // Open the sidebar <details> groups directly via JS — instant and reliable even
  // when the Space is slow (clicking each summary is timing-dependent and can hang).
  await page.evaluate(() => document.querySelectorAll('[data-testid="stSidebar"] details')
    .forEach(d => { d.open = true; })).catch(()=>{});
  await sleep(0.3);
}
// Wait for content unique to the target page/tab so captions stay in sync with
// what's on screen (the free Space renders slowly and unevenly).
async function waitFor(re, t = 6000) {
  try { await M().getByText(new RegExp(re, 'i')).first().waitFor({ state: 'visible', timeout: t }); }
  catch { log('  (waitFor timeout:', re, ')'); }
}
async function nav(label, waitOrSettle) {
  if (bail) { await sleep(0.2); return; }
  let waitText = null, settle = 3;
  if (typeof waitOrSettle === 'string') waitText = waitOrSettle;
  else if (typeof waitOrSettle === 'number') settle = waitOrSettle;
  try {
    await hideFx(); await expandGroups();
    const b = sb().getByRole('button', { name: new RegExp(label, 'i') }).first();
    await b.scrollIntoViewIfNeeded({ timeout: 4000 }).catch(()=>{});
    await b.click({ timeout: 8000 });
    navFails = 0;
    if (waitText) await waitFor(waitText);
    await sleep(settle); await ensureFx();
  } catch (e) {
    log(`  nav(${label}) skipped:`, e.message.split('\n')[0]);
    if (++navFails >= 4) { bail = true; log('  !! Space unresponsive — skipping to closing slides'); }
    await sleep(0.5);
  }
}
async function tab(name, waitText, settle = 2) {
  await hideFx();
  await page.getByRole('tab', { name: new RegExp(name, 'i') }).first().click({ timeout: 8000 })
    .catch(() => page.getByText(new RegExp(name, 'i')).first().click().catch(()=>{}));
  if (waitText) await waitFor(waitText);
  await sleep(settle); await ensureFx();
}
// point at a heading / labelled element by text, within main
const byText = (re) => M().getByText(new RegExp(re, 'i'));
const metric = (i = 0) => M().locator('[data-testid="stMetric"]').nth(i);

// ════════════════════════════ SCRIPT ════════════════════════════
try {
  // PART 1 — framing slides
  log('PART 1 — framing slides');
  await page.goto(SLIDES); await sleep(1.5);
  await slide(0, 6); await slide(1, 9); await slide(2, 9); await slide(3, 11);

  // PART 2 — real-time dashboard
  log('PART 2 — dashboard');
  await page.goto(SPACE, { waitUntil: 'domcontentloaded' }); await sleep(6);
  await page.locator('input[type="text"]').first().fill(EMAIL);
  await page.locator('input[type="password"]').first().fill(PASS);
  await ensureFx(); await cap('The live system', 'Authenticating to the deployed cloud demo — free to run, backed by a real database.');
  await sleep(2.5);
  await page.getByRole('button', { name: /sign in/i }).first().click();
  await waitFor('System Status'); await sleep(2);
  await ensureFx(); await expandGroups();

  await cap('Real-time operations dashboard', 'The command centre. Every figure is queried live from PostgreSQL.');
  await sleep(2.5);
  await cap('Service heartbeat', 'Live status of the three critical services — API, PostgreSQL (with query latency), and the active LLM provider.');
  await point(byText('System Status'), 3);
  await cap('Programme metrics', 'Active sessions now, total sessions, deviations detected, and high-severity events.');
  await point(metric(0), 2.2); await point(metric(1), 2.2); await point(metric(3), 2.2);
  await cap('Live Activity Feed', 'Each session, colour-coded by severity, with deviations, duration, and its p95 inference latency — the real-time guarantee, self-reported.');
  await point(byText('Live Activity Feed'), 3.5); await glide(360); await sleep(2);
  await point(byText('Recent Sessions'), 3).catch(()=>{}); await page.mouse.wheel(0, -1200); await sleep(1.5);

  // PART 3 — live SOP test
  log('PART 3 — live SOP test');
  await nav('Live Training', 'Data & Privacy');
  await cap('Step 1 — consent', 'The first thing shown is a GDPR notice: frames are processed in memory and never stored. Consent is explicit and required.');
  await point(byText('Data & Privacy Notice'), 4);
  try {
    const cb = page.getByRole('checkbox').first();
    if (await cb.count()) { await cb.scrollIntoViewIfNeeded().catch(()=>{}); await cb.click({ force:true, timeout:8000 }).catch(()=>{}); await sleep(1.5); }
    const start = page.getByRole('button', { name: /start|begin|consent|continue/i }).first();
    if (await start.count()) { await start.scrollIntoViewIfNeeded().catch(()=>{}); await start.click({ timeout:10000 }).catch(()=>{}); await sleep(5); }
  } catch (e) { log('  consent:', e.message.split('\n')[0]); }
  await ensureFx();
  await cap('Step 2 — live perception', 'The browser webcam streams to the server: a live pose skeleton and detected tools/PPE overlay the feed. (Synthetic feed shown.)');
  try { const camBtn = page.getByRole('button', { name: /start camera|▶/i }).first(); if (await camBtn.count()) { await camBtn.click(); await sleep(7);} } catch {}
  await sleep(6);
  await cap('Step 3 — deviation → explainable feedback', 'A deviation is classified into one of five classes; the LLM writes a corrective instruction explaining what was wrong, and why, within 2 s.');
  await sleep(7);

  // PART 4 — authoring & library
  log('PART 4 — authoring & library');
  await nav('Create SOP', 'SOP Metadata');
  await cap('Create SOP', 'Author a procedure from scratch — or upload a document and let an LLM parse it into a structured, machine-readable SOP.');
  await point(byText('SOP Metadata'), 3); await point(byText('Steps'), 3);
  await nav('SOP Library', 'Showing');
  await cap('SOP Library', '22 approved procedures — data science, security, lab safety, food hygiene, emergency response. Domain-general by design.');
  await glide(420); await sleep(2.5);

  // PART 5 — data & analytics
  log('PART 5 — analytics');
  await nav('Analytics', 'Worker Performance');
  await cap('Analytics — programme KPIs', 'Six indicators, including the latency-target pass rate above 99% — the 2-second guarantee holding at scale.');
  await point(metric(4), 2.5); await point(metric(5), 2.5);
  await tab('Study Groups', 'Study-Group Comparison', 4);
  await cap('Study Groups — evidence for H1 & H2', 'Four experimental arms. Hybrid reaches the highest weighted accuracy (~70%); control trails near 22%.');
  await glide(420); await sleep(4);
  await tab('Bias Audit', 'Per-Department', 3);
  await cap('Responsible AI — fairness audit', 'Outcome parity across departments; any group significantly below the cohort is flagged.');
  await sleep(3.5);
  await tab('Emotion Breakdown', 'Emotion & Stress', 3);
  await cap('Wellbeing analytics', 'Engagement states — focused, neutral, stressed, fatigued — from facial-expression analysis.');
  await sleep(3.5);
  await nav('Session History', 'Deviation Drill-Down');
  await cap('Session History', 'The forensic record: filter all 1,555 sessions, then drill down into any session\'s individual deviations.');
  await glide(360); await sleep(3);
  await nav('Staff Profiles', 'Profile Detail');
  await cap('Staff Profiles', 'Per-worker development record — sessions, deviations, and a derived skill level with time-to-competency.');
  await point(byText('Skill'), 3).catch(()=>{}); await sleep(1.5);
  await nav('Reports', 'Generate Report');
  await cap('Reports', 'Filtered, publication-ready PDF exports with the deviation breakdown — the artefacts for the thesis.');
  await sleep(3);
  await nav('Leaderboard', 'Study group');
  await cap('Leaderboard', 'Severity-weighted ranking by period, study group, or department — gamification aligned with safe, correct execution.');
  await sleep(3);

  // PART 6 — academic evaluation
  log('PART 6 — evaluation');
  await nav('Simulation', 'Experiment Configuration');
  await cap('Formal hypothesis testing', 'All data clearly labelled SYNTHETIC. The platform runs the inferential statistics behind the thesis.');
  await point(byText('Operational-Data Hypothesis Tests'), 3.5);
  try { const run = page.getByRole('button',{name:/run hypothesis tests/i}).first(); if (await run.count()){ await run.click(); await sleep(5);} } catch {}
  await ensureFx();
  await cap('H1 / H2 results', 'Welch t-test for H1 and ANOVA for H2 — both significant, with large effect sizes and reported assumption checks.');
  await point(metric(0), 2.5).catch(()=>{}); await point(metric(1), 2.5).catch(()=>{});
  await glide(420); await sleep(3);
  await cap('Continual learning (EWC)', 'The model absorbs new data without catastrophically forgetting — verified at full retention.');
  await point(byText('Continual Learning'), 3).catch(()=>{}); await sleep(1.5);

  // PART 7 — administration & governance
  log('PART 7 — administration');
  await nav('Settings', 'LLM Configuration');
  await cap('Settings — LLM configuration', 'Choose among 5 providers; the API key is stored encrypted in the DB; Test Connection verifies it live.');
  await point(byText('LLM Configuration'), 3.5);
  await nav('User Management', 'Add New User');
  await cap('User Management — RBAC', 'Every account has a role governing access, enforced server-side. Synthetic accounts are systematically labelled.');
  await point(byText('User Management'), 3); await glide(300); await sleep(2);
  await nav('System Health', 'LLM Latency');
  await cap('System Health', 'Live service status with uptime and query time, auto-refreshing, plus LLM latency history over time.');
  await glide(300); await sleep(3);
  await nav('Audit Log', 'entries');
  await cap('Audit Log', 'Every consequential action is recorded — searchable and exportable. Accountability as a security and ethics control.');
  await sleep(3);
  await nav('Notifications', 'Mark all read');
  await cap('Notifications', 'System events grouped by day with unread tracking — completed runs, new procedures, health checks.');
  await sleep(3);
  await nav('My Account', 'Account Lookup');
  await cap('My Account', 'Self-service profile and security; the place a worker exercises their right to request data deletion.');
  await sleep(3);

  // PART 8 — closing slides
  log('PART 8 — closing slides');
  await hideFx(); await page.evaluate(()=>document.getElementById('forge-fx')?.remove()).catch(()=>{});
  await slide(4, 9); await slide(5, 8); await slide(6, 9);
} catch (e) {
  log('!! capture error:', e.message);
  await page.screenshot({ path: resolve(__dir, 'capture-error.png') }).catch(()=>{});
} finally {
  log('finalising video…');
  await ctx.close(); await browser.close();
}

// ── transcode webm → mp4 with a background-music bed ──────────────────────
const webm = readdirSync(VID_DIR).filter(f => f.endsWith('.webm')).map(f => join(VID_DIR, f))[0];
if (!webm) { log('NO VIDEO PRODUCED'); process.exit(1); }
log('raw webm:', webm);

function duration(file) {
  const out = spawnSync(ffmpeg.path, ['-i', file], { encoding: 'utf8' }).stderr || '';
  const m = out.match(/Duration:\s*(\d+):(\d+):(\d+\.\d+)/);
  return m ? (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) : 0;
}

// Use the user's own track if present (music.mp3/.wav/.m4a/.ogg); else synthesise
// a soft royalty-free ambient pad (a 4-chord loop) so the video ships with music.
function findUserMusic() {
  return readdirSync(__dir).find(f => /^music\.(mp3|wav|m4a|ogg|aac)$/i.test(f));
}
function makeAmbient(out) {
  const env = 'max(0\\,min(1\\,min(t/0.6\\,(8-t)/0.6)))';              // smooth 0.6s edge fades
  const chord = (fs) => `aevalsrc=(${fs.map(f => `0.22*sin(2*PI*${f}*t)`).join('+')})*${env}:d=8:s=44100`;
  const chords = [
    [261.63, 329.63, 392.00],   // C major
    [220.00, 261.63, 329.63],   // A minor
    [174.61, 220.00, 261.63],   // F major
    [196.00, 246.94, 293.66],   // G major
  ];
  const args = ['-y'];
  chords.forEach(c => args.push('-f', 'lavfi', '-i', chord(c)));
  args.push('-filter_complex',
    '[0:a][1:a][2:a][3:a]concat=n=4:v=0:a=1[c];' +
    '[c]lowpass=f=1150,tremolo=f=0.20:d=0.5,aecho=0.8:0.6:60:0.28,' +
    'aformat=sample_fmts=s16:channel_layouts=stereo[a]',
    '-map', '[a]', out);
  return spawnSync(ffmpeg.path, args, { stdio: 'ignore' }).status === 0;
}

const VOL = process.env.MUSIC_VOL || '0.16';
const userMusic = findUserMusic();
let music = userMusic ? resolve(__dir, userMusic) : resolve(VID_DIR, 'ambient_loop.wav');
if (userMusic) log('music: user track', userMusic);
else { log('music: synthesising ambient bed…'); if (!makeAmbient(music)) { log('  ambient synth failed — muxing silent'); music = null; } }

const dur = duration(webm);
const fadeOut = Math.max(1, dur - 4);
log(`transcoding → mp4 (${dur.toFixed(0)}s)${music ? ', mixing music vol=' + VOL : ''}…`);

const base = ['-y', '-i', webm];
const tail = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p',
  '-r', '30', '-movflags', '+faststart'];
let args;
if (music) {
  args = [...base, '-stream_loop', '-1', '-i', music,
    '-filter_complex', `[1:a]volume=${VOL},afade=t=in:st=0:d=3,afade=t=out:st=${fadeOut.toFixed(2)}:d=4[m]`,
    '-map', '0:v', '-map', '[m]', ...tail, '-c:a', 'aac', '-b:a', '160k', '-shortest', OUT_MP4];
} else {
  args = [...base, ...tail, OUT_MP4];
}
const r = spawnSync(ffmpeg.path, args, { stdio: 'inherit' });
if (r.status === 0) log('✓ DONE →', OUT_MP4);
else log('ffmpeg failed; the .webm is still usable:', webm);
