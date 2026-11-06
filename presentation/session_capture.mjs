/**
 * Auto-capture the ANALYTICS of your real live SOP test session as a video
 * segment (Dashboard → Session History drill-down → Analytics), with the same
 * animated captions + gold pointer + music as the main walkthrough.
 *
 * Output: presentation/session_report.mp4  (then: node splice_live.mjs live_test.mp4 session_report.mp4)
 *
 * It auto-targets the NEWEST real session for worker 260 (Mashkur Rezaul),
 * skipping the smoke-test row. Override with SESSION_ID=<8-char id>.
 *
 * Run:  cd presentation && node session_capture.mjs
 * Env:  SPEED=1 · HEADED=1 · MUSIC_VOL=0.16 · SESSION_ID=...
 */
import { chromium } from 'playwright';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';
import ffmpeg from '@ffmpeg-installer/ffmpeg';

const __dir = dirname(fileURLToPath(import.meta.url));
const SPACE = 'https://mashkura-forge-vision.hf.space';
const API = SPACE + '/api/v1';
const EMAIL = 'mashkur.alam@hotmail.co.uk', PASS = 'ForgeDemo123!';
const SPEED = parseFloat(process.env.SPEED || '1');
const VID_DIR = resolve(__dir, 'videos');
const OUT = resolve(__dir, 'session_report.mp4');
const W = 1280, H = 720;
const SKIP = new Set(['smoke2283']);
const log = (...a) => console.log('·', ...a);
const sleep = (s) => new Promise(r => setTimeout(r, s * 1000 * SPEED));

// ── find the session to feature ───────────────────────────────────────────
async function token() {
  const r = await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: EMAIL, password: PASS }) });
  return (await r.json()).access_token;
}
const tok = await token();
const sessions = await (await fetch(`${API}/analytics/sessions?page=1&page_size=20`, { headers: { Authorization: 'Bearer ' + tok } })).json();
const rows = Array.isArray(sessions) ? sessions : (sessions.sessions || sessions.items || sessions.data || []);
let target;
if (process.env.SESSION_ID) target = rows.find(s => (s.session_id || '').startsWith(process.env.SESSION_ID));
else target = rows.find(s => s.worker_id === 260 && !SKIP.has(s.session_id) && !(s.sop_name || '').toLowerCase().includes('connectivity'));
if (!target) { console.error('No target session found. Pass SESSION_ID=...'); process.exit(1); }
const SID = (target.session_id || '').slice(0, 8);
const SOP = target.sop_name || 'SOP';
const DEV = target.deviation_count ?? 0;
const HIGH = target.high_severity_count ?? 0;
const DUR = Math.round(target.duration_seconds || 0);
log(`featuring session ${SID} — "${SOP}" · ${DUR}s · ${DEV} deviation(s), ${HIGH} high`);
if (DEV === 0) log('  NOTE: this session has 0 deviations — the drill-down will be sparse. Consider a run with deviations.');

// ── recorder + FX ──────────────────────────────────────────────────────────
if (existsSync(VID_DIR)) rmSync(VID_DIR, { recursive: true, force: true });
mkdirSync(VID_DIR, { recursive: true });
const browser = await chromium.launch({ headless: !process.env.HEADED });
const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir: VID_DIR, size: { width: W, height: H } } });
ctx.setDefaultTimeout(20000);
const page = await ctx.newPage();

async function ensureFx() {
  await page.evaluate(() => {
    if (window.__fx) return;
    const css = document.createElement('style');
    css.textContent = `
      #fc-cap{position:fixed;left:0;right:0;bottom:0;z-index:2147483646;pointer-events:none;padding:20px 34px 26px;font-family:Inter,Segoe UI,sans-serif;background:linear-gradient(to top,rgba(7,11,20,.95) 28%,rgba(7,11,20,0))}
      #fc-t{font-family:Anton,Inter,sans-serif;letter-spacing:2px;text-transform:uppercase;color:#FFCC00;font-size:15px;margin-bottom:7px;opacity:0;transform:translateY(10px);transition:opacity .45s,transform .45s}
      #fc-x{color:#eef3fb;font-size:21px;line-height:1.36;max-width:1060px;text-shadow:0 1px 3px rgba(0,0,0,.6);opacity:0;transform:translateY(14px);transition:opacity .55s .08s,transform .55s .08s}
      #fc-cap.show #fc-t,#fc-cap.show #fc-x{opacity:1;transform:translateY(0)}
      #fc-ring{position:fixed;z-index:2147483645;pointer-events:none;border:3px solid #FFCC00;border-radius:12px;box-shadow:0 0 0 4px rgba(255,204,0,.18),0 0 26px rgba(255,204,0,.35);opacity:0;transition:left .6s cubic-bezier(.22,1,.36,1),top .6s cubic-bezier(.22,1,.36,1),width .6s,height .6s,opacity .3s}
      #fc-ring.on{opacity:1;animation:fcp 1.6s ease-in-out infinite}
      @keyframes fcp{0%,100%{box-shadow:0 0 0 4px rgba(255,204,0,.18),0 0 22px rgba(255,204,0,.3)}50%{box-shadow:0 0 0 7px rgba(255,204,0,.1),0 0 34px rgba(255,204,0,.55)}}
      #fc-ptr{position:fixed;z-index:2147483647;pointer-events:none;width:14px;height:14px;border-radius:50%;background:#FFCC00;box-shadow:0 0 0 4px rgba(255,204,0,.4);opacity:0;transition:left .6s cubic-bezier(.22,1,.36,1),top .6s cubic-bezier(.22,1,.36,1),opacity .3s}
      #fc-ptr.on{opacity:1}`;
    document.head.appendChild(css);
    const r = document.createElement('div'); r.id = 'forge-fx';
    r.innerHTML = '<div id="fc-cap"><div id="fc-t"></div><div id="fc-x"></div></div><div id="fc-ring"></div><div id="fc-ptr"></div>';
    document.body.appendChild(r);
    window.__fx = {
      cap(t, x){ const c=document.getElementById('fc-cap'); document.getElementById('fc-t').textContent=t; document.getElementById('fc-x').textContent=x; c.classList.remove('show'); void c.offsetWidth; c.classList.add('show'); },
      point(b){ const ring=document.getElementById('fc-ring'),p=document.getElementById('fc-ptr'); ring.style.left=(b.x-8)+'px';ring.style.top=(b.y-8)+'px';ring.style.width=(b.width+16)+'px';ring.style.height=(b.height+16)+'px';ring.classList.add('on'); p.style.left=(b.x+Math.min(b.width-6,30))+'px';p.style.top=(b.y+Math.min(b.height-6,26))+'px';p.classList.add('on'); },
      hide(){ document.getElementById('fc-ring')?.classList.remove('on'); document.getElementById('fc-ptr')?.classList.remove('on'); },
    };
  }).catch(()=>{});
}
const cap = async (t,x)=>{ log('CAP:',t); await ensureFx(); await page.evaluate(a=>window.__fx.cap(a.t,a.x),{t,x}); };
const hideFx = ()=>page.evaluate(()=>window.__fx&&window.__fx.hide()).catch(()=>{});
async function point(loc, dwell=2.8){ try{ await ensureFx(); const el=(typeof loc==='string'?page.locator(loc):loc).first(); await el.scrollIntoViewIfNeeded({timeout:5000}).catch(()=>{}); const b=await el.boundingBox(); if(b) await page.evaluate(x=>window.__fx.point(x),b); await sleep(dwell);}catch(e){log('point skip',e.message.split('\n')[0]); await sleep(dwell);} }
async function glide(px=400,steps=22){ for(let i=0;i<steps;i++){ await page.mouse.wheel(0,px/steps); await sleep(0.05);} }
const sb=()=>page.locator('[data-testid="stSidebar"]'), M=()=>page.locator('[data-testid="stMain"]');
const byText=(re)=>M().getByText(new RegExp(re,'i'));
const metric=(i=0)=>M().locator('[data-testid="stMetric"]').nth(i);
async function expandGroups(){ await page.evaluate(()=>document.querySelectorAll('[data-testid="stSidebar"] details').forEach(d=>d.open=true)).catch(()=>{}); await sleep(0.3); }
async function waitFor(re,t=8000){ try{ await M().getByText(new RegExp(re,'i')).first().waitFor({state:'visible',timeout:t}); }catch{ log('  (waitFor timeout',re,')'); } }
async function nav(label, wait){ try{ await hideFx(); await expandGroups(); const b=sb().getByRole('button',{name:new RegExp(label,'i')}).first(); await b.scrollIntoViewIfNeeded({timeout:4000}).catch(()=>{}); await b.click({timeout:8000}); if(wait) await waitFor(wait); await sleep(3); await ensureFx(); }catch(e){ log('nav skip',label,e.message.split('\n')[0]); } }

// ── flow ───────────────────────────────────────────────────────────────────
const esc = (s)=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
try {
  await page.goto(SPACE, { waitUntil: 'domcontentloaded' }); await sleep(6);
  await page.locator('input[type="text"]').first().fill(EMAIL);
  await page.locator('input[type="password"]').first().fill(PASS);
  await page.getByRole('button', { name: /sign in/i }).first().click();
  await waitFor('System Status'); await sleep(2); await ensureFx(); await expandGroups();

  // Dashboard — the session in the live activity feed
  await cap('Your live test — captured', `“${SOP}” · ${DUR}s · ${DEV} deviation${DEV===1?'':'s'} detected. Recorded live to the research database.`);
  await sleep(2.5);
  await point(byText('Live Activity Feed'), 3);
  await point(byText(esc(SOP)), 3.5);                      // their session row
  await cap('Counted in the programme totals', 'Total sessions and deviations have ticked up to include this run.');
  await point(metric(1), 2.6); await point(metric(2), 2.6);

  // Session History — your run in the table, then drill into its deviations
  await nav('Session History', 'Deviation Drill-Down');
  await cap('Session History — this run', 'Your session is now a queryable record, alongside the whole cohort.');
  await point(byText(esc(SOP)), 3).catch(()=>{});                 // their row in the table (DOM text)
  await sleep(0.5);
  // scroll to the drill-down section, then to the per-deviation table (a canvas
  // dataframe — target the element, not its text)
  await page.mouse.move(640, 400);
  await byText('Deviation Drill-Down').first().scrollIntoViewIfNeeded().catch(()=>{});
  await sleep(1);
  await point(byText('Deviation Drill-Down'), 2.5).catch(()=>{});
  if (DEV > 0) {
    const devTable = M().locator('[data-testid="stDataFrame"], [data-testid="stTable"]').last();
    await devTable.scrollIntoViewIfNeeded().catch(()=>{});
    await page.mouse.move(640, 400); await glide(160, 10); await sleep(1);
    await cap('Every deviation, drilled down', `${DEV} deviation${DEV===1?'':'s'}${HIGH?` (${HIGH} high-severity)`:''} — class, severity, the exact step, and why.`);
    await point(devTable, 5).catch(()=>{});
    await sleep(3);
  } else {
    await cap('A clean run', 'Zero deviations logged — a fully correct execution.');
    await sleep(3);
  }

  // Analytics — part of the dataset
  await nav('Analytics', 'Worker Performance');
  await cap('Now part of the analytics', 'This live run joins the dataset behind every chart and hypothesis test.');
  await point(metric(0), 3); await point(metric(1), 3);
  await sleep(1);
} catch (e) {
  log('!! error', e.message);
  await page.screenshot({ path: resolve(__dir, 'session-capture-error.png') }).catch(()=>{});
} finally {
  await ctx.close(); await browser.close();
}

// ── transcode + ambient music ──────────────────────────────────────────────
const FF = ffmpeg.path;
const webm = readdirSync(VID_DIR).filter(f => f.endsWith('.webm')).map(f => join(VID_DIR, f))[0];
if (!webm) { console.error('no video'); process.exit(1); }
const env = 'max(0\\,min(1\\,min(t/0.6\\,(8-t)/0.6)))';
const chord = (fs) => `aevalsrc=(${fs.map(f => `0.22*sin(2*PI*${f}*t)`).join('+')})*${env}:d=8:s=44100`;
const music = join(VID_DIR, 'amb.wav');
spawnSync(FF, ['-y',
  '-f','lavfi','-i',chord([261.63,329.63,392]), '-f','lavfi','-i',chord([220,261.63,329.63]),
  '-f','lavfi','-i',chord([174.61,220,261.63]), '-f','lavfi','-i',chord([196,246.94,293.66]),
  '-filter_complex','[0:a][1:a][2:a][3:a]concat=n=4:v=0:a=1[c];[c]lowpass=f=1150,tremolo=f=0.2:d=0.5,aecho=0.8:0.6:60:0.28,aformat=sample_fmts=s16:channel_layouts=stereo[a]',
  '-map','[a]', music], { stdio: 'ignore' });
const dur = (() => { const m=(spawnSync(FF,['-i',webm],{encoding:'utf8'}).stderr||'').match(/Duration:\s*(\d+):(\d+):(\d+\.\d+)/); return m?(+m[1])*3600+(+m[2])*60+(+m[3]):0; })();
const VOL = process.env.MUSIC_VOL || '0.16';
log(`transcoding session_report.mp4 (${dur.toFixed(0)}s)…`);
const r = spawnSync(FF, ['-y','-i',webm,'-stream_loop','-1','-i',music,
  '-filter_complex',`[1:a]volume=${VOL},afade=t=in:st=0:d=2,afade=t=out:st=${Math.max(1,dur-3).toFixed(2)}:d=3[m]`,
  '-map','0:v','-map','[m]','-c:v','libx264','-preset','medium','-crf','21','-pix_fmt','yuv420p','-r','30',
  '-c:a','aac','-b:a','160k','-movflags','+faststart','-shortest', OUT], { stdio: 'inherit' });
console.log(r.status===0 ? '✓ DONE → '+OUT : 'ffmpeg failed; webm at '+webm);
