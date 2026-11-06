/**
 * Splice your real Live SOP Test recording (and any session-results segment)
 * into the walkthrough, replacing the synthetic Live Training scene.
 *
 *   node splice_live.mjs <liveTestClip> [sessionReportClip ...]
 *
 * • The first clip gets a "LIVE SOP TEST · <NAME>" lower-third for its first 6 s.
 * • Each clip is scaled/padded to 1280×720 @30fps, stereo AAC, with fade in/out.
 * • They replace the base video's segment [START,END] (the synthetic scene).
 * • Output: forge-vision-walkthrough-FINAL.mp4 (the base file is left untouched).
 *
 * Env: START=82 END=108 (seconds, the synthetic Live Training slot) · NAME · NO_TITLE=1
 * Auto-detect: with no args, uses presentation/live_test.* then session_report.*
 */
import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';
import ffmpeg from '@ffmpeg-installer/ffmpeg';

const FF = ffmpeg.path;
const __dir = dirname(fileURLToPath(import.meta.url));
const BASE = resolve(__dir, 'forge-vision-walkthrough.mp4');
const OUT  = resolve(__dir, 'forge-vision-walkthrough-FINAL.mp4');
const TMP  = resolve(__dir, 'videos');
const START = parseFloat(process.env.START || '82');
const END   = parseFloat(process.env.END   || '108');
const NAME  = process.env.NAME || 'Mashkur Alam';
const FONT_B = 'C\\:/Windows/Fonts/arialbd.ttf';
const FONT_R = 'C\\:/Windows/Fonts/arial.ttf';
const log = (...a) => console.log('·', ...a);

if (!existsSync(BASE)) { console.error('Base video not found:', BASE); process.exit(1); }
if (!existsSync(TMP)) mkdirSync(TMP, { recursive: true });

// Resolve insert clips (args, else auto-detect).
let inserts = process.argv.slice(2);
if (!inserts.length) {
  for (const re of [/^live_test\./i, /^session_report\./i]) {
    const f = readdirSync(__dir).find(x => re.test(x));
    if (f) inserts.push(resolve(__dir, f));
  }
}
inserts = inserts.map(p => resolve(p));
const missing = inserts.filter(p => !existsSync(p));
if (!inserts.length) {
  console.error('No clips to splice. Pass a file, e.g.:  node splice_live.mjs live_test.mp4');
  process.exit(1);
}
if (missing.length) { console.error('Not found:', missing.join(', ')); process.exit(1); }
log('inserting:', inserts.map(p => p.split(/[\\/]/).pop()).join('  →  '));

const probe = (f) => { const e = spawnSync(FF, ['-i', f], { encoding: 'utf8' }).stderr || ''; return e; };
const durationOf = (f) => { const m = probe(f).match(/Duration:\s*(\d+):(\d+):(\d+\.\d+)/); return m ? +m[1]*3600+ +m[2]*60+ +m[3] : 0; };
const hasAudio = (f) => /Stream #\d+:\d+.*: Audio:/.test(probe(f));

// ── Stage 1: normalise each insert to a uniform temp clip ─────────────────
const NORM = '1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30,format=yuv420p';
const normed = [];
inserts.forEach((src, i) => {
  const out = join(TMP, `insert_${i}.mp4`);
  const d = durationOf(src);
  let vf = `scale=${NORM},fade=t=in:st=0:d=0.4,fade=t=out:st=${Math.max(0, d - 0.5).toFixed(2)}:d=0.4`;
  if (i === 0 && !process.env.NO_TITLE) {  // lower-third title on the live-test clip
    const upto = "enable='lt(t,6)'";
    vf += `,drawbox=x=0:y=h-132:w=iw:h=132:color=black@0.45:t=fill:${upto}` +
          `,drawtext=fontfile=${FONT_B}:text='LIVE SOP TEST':fontcolor=0xFFCC00:fontsize=36:x=44:y=h-108:${upto}` +
          `,drawtext=fontfile=${FONT_R}:text='${NAME}':fontcolor=white:fontsize=26:x=44:y=h-60:${upto}`;
  }
  const a = ['-y'];
  if (hasAudio(src)) a.push('-i', src, '-vf', vf, '-af', 'aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo');
  else a.push('-i', src, '-f', 'lavfi', '-t', String(d || 5), '-i', 'anullsrc=r=44100:cl=stereo', '-vf', vf, '-map', '0:v', '-map', '1:a', '-shortest');
  a.push('-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p', '-r', '30',
         '-c:a', 'aac', '-b:a', '160k', out);
  log(`normalising insert ${i} (${d.toFixed(1)}s, audio=${hasAudio(src)})…`);
  const r = spawnSync(FF, a, { stdio: 'ignore' });
  if (r.status !== 0) { console.error('normalise failed for', src); process.exit(1); }
  normed.push(out);
});

// ── Stage 2: concat  base[0,START] + inserts + base[END,end]  →  FINAL ─────
const args = ['-y', '-ss', '0', '-to', String(START), '-i', BASE];   // input 0 = partA
normed.forEach(f => args.push('-i', f));                              // inputs 1..K
args.push('-ss', String(END), '-i', BASE);                           // input K+1 = partC
const N = normed.length + 2;
let fc = '', maps = '';
for (let k = 0; k < N; k++) {
  fc += `[${k}:v]fps=30,scale=${NORM}[v${k}];[${k}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a${k}];`;
  maps += `[v${k}][a${k}]`;
}
fc += `${maps}concat=n=${N}:v=1:a=1[v][a]`;
args.push('-filter_complex', fc, '-map', '[v]', '-map', '[a]',
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p',
  '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', OUT);

log(`splicing: partA[0–${START}s] + ${normed.length} insert(s) + partC[${END}s–end]…`);
const r = spawnSync(FF, args, { stdio: 'inherit' });
normed.forEach(f => { try { rmSync(f); } catch {} });
if (r.status === 0) log('✓ DONE →', OUT);
else { console.error('splice failed'); process.exit(1); }
