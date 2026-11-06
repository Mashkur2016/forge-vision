/**
 * Assemble the full presentation video from the rendered segments.
 *  1. Build the E1 "Live SOP Training" placeholder (seg_14) — your clip replaces it later.
 *  2. Concat every segments/seg_*.mp4 (sorted) into one 1080p video (uniform re-encode).
 *  3. Mix the bgmusic/ tracks under the voiceover at 20% volume.
 * Output: Forge-Vision_FULL.mp4   (voiceover + background music; E1 = placeholder)
 *
 * Run: cd presentation && node assemble_final.mjs
 *      LIVE=path/to/your_clip.mp4 node assemble_final.mjs   (insert your real E1 clip)
 */
import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { FF, DIR, VO, BG, SEG, W, H, durationOf, E1 } from './pres_config.mjs';

const log = (...a) => console.log('·', ...a);
const run = (args, label) => { const r = spawnSync(FF, args, { stdio: 'inherit' }); if (r.status !== 0) { console.error('FAILED:', label); process.exit(1); } };
const FONT = 'C\\:/Windows/Fonts/arialbd.ttf';

// ── 1. Build the two Live-Training E1 segments (clean run + skip run) ───────
// Each = a SILENT screen-capture clip + its TTS narration overlaid; the
// background music plays under it (added in the final mix). Falls back to a
// labelled placeholder card until you supply the clip / narration.
const FONTR = 'C\\:/Windows/Fonts/arial.ttf';
for (const e of E1) {
  const segPath = join(SEG, `seg_${e.id}.mp4`);
  const mp3 = join(VO, e.mp3);
  const hasMp3 = existsSync(mp3);
  const narrDur = hasMp3 ? durationOf(mp3) : 75;
  const clipPath = (process.env[e.env] && resolve(process.env[e.env])) || resolve(DIR, e.clip);
  const aud = hasMp3 ? ['-i', mp3] : ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo'];

  if (existsSync(clipPath)) {
    // Overlay the TTS narration on your silent clip; keep the FULL clip
    // (segment = max(clip, narration); short clips hold the last frame).
    const vlen = durationOf(clipPath);
    const segdur = Math.max(vlen, narrDur);
    log(`E1 ${e.id}: ${e.clip} (${vlen.toFixed(1)}s) + ${e.mp3}${hasMp3 ? ` (${narrDur.toFixed(1)}s)` : ' (no narration yet → silent)'} → ${segdur.toFixed(1)}s`);
    run(['-y', '-i', clipPath, ...aud,
      '-filter_complex',
        `[0:v]scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1,format=yuv420p,tpad=stop_mode=clone:stop_duration=600[v];[1:a]apad[a]`,
      '-map', '[v]', '-map', '[a]', '-t', segdur.toFixed(2),
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-c:a', 'aac', '-ar', '44100', '-ac', '2', segPath], `E1 ${e.id}`);
  } else {
    const label = e.id === '14' ? 'LIVE TEST 1 — CLEAN RUN' : 'LIVE TEST 2 — WITH DEVIATIONS';
    log(`E1 ${e.id}: placeholder card (${narrDur.toFixed(1)}s) — add ${e.clip}`);
    const t1 = `drawtext=fontfile=${FONT}:text='${label}':fontcolor=0xFFCC00:fontsize=60:x=(w-text_w)/2:y=(h/2)-60`;
    const t2 = `drawtext=fontfile=${FONTR}:text='Your live demonstration goes here':fontcolor=white:fontsize=32:x=(w-text_w)/2:y=(h/2)+36`;
    run(['-y', '-f', 'lavfi', '-i', `color=c=0x0B1220:s=${W}x${H}:d=${narrDur.toFixed(2)}`, ...aud,
      '-filter_complex', `[0:v]${t1},${t2},format=yuv420p[v]`, '-map', '[v]', '-map', '1:a',
      '-t', narrDur.toFixed(2), '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-r', '30',
      '-c:a', 'aac', '-ar', '44100', '-ac', '2', segPath], `E1 ${e.id} placeholder`);
  }
}

// ── 2. Concat all segments (uniform re-encode via concat filter) ───────────
const segs = readdirSync(SEG).filter(f => /^seg_\d+[a-z]?\.mp4$/.test(f)).sort();
log('segments:', segs.join(' '));
const missing = ['00','01','02','03','04','05','06','10','11','12','13','14','14b','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30','90','91','92']
  .filter(id => !segs.includes(`seg_${id}.mp4`));
if (missing.length) log('WARNING — missing segments:', missing.join(' '));

const inputs = [];
segs.forEach(s => { inputs.push('-i', join(SEG, s)); });
let fc = '';
segs.forEach((_, i) => { fc += `[${i}:v]scale=${W}:${H},fps=30,setsar=1,format=yuv420p[v${i}];[${i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a${i}];`; });
segs.forEach((_, i) => { fc += `[v${i}][a${i}]`; });
fc += `concat=n=${segs.length}:v=1:a=1[v][a]`;
const full = join(DIR, 'full_voiceover.mp4');
log('concatenating', segs.length, 'segments → full_voiceover.mp4 …');
run(['-y', ...inputs, '-filter_complex', fc, '-map', '[v]', '-map', '[a]',
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-c:a', 'aac', '-b:a', '192k',
  '-movflags', '+faststart', full], 'concat');

// ── 3. Background music bed (concat tracks, loop, 20% volume, mix under) ────
const tracks = readdirSync(BG).filter(f => /\.(mp3|wav|m4a)$/i.test(f)).sort();
log('bgmusic tracks:', tracks.length);
const bgList = join(SEG, '_bg.txt');
writeFileSync(bgList, tracks.map(t => `file '${join(BG, t).replace(/\\/g, '/')}'`).join('\n'));
const bgAll = join(SEG, '_bg_all.mp3');
run(['-y', '-f', 'concat', '-safe', '0', '-i', bgList, '-c:a', 'libmp3lame', '-q:a', '4', bgAll], 'bg concat');

const dur = durationOf(full);
const VOL = process.env.MUSIC_VOL || '0.096';   // background-music level (voiceover stays full)
const out = join(DIR, 'Forge-Vision_FULL.mp4');
// amix in older ffmpeg has no `normalize` option and auto-divides by N inputs,
// so pre-scale voiceover ×2 and music ×(2·VOL) to keep voiceover full + music at VOL.
const v2 = (parseFloat(VOL) * 2).toFixed(3);

const bgvol = `volume=${v2}`;   // music plays evenly under all narration, incl. both E1 demos

log(`mixing music at ${VOL} under ${dur.toFixed(0)}s of voiceover → Forge-Vision_FULL.mp4 …`);
run(['-y', '-i', full, '-stream_loop', '-1', '-i', bgAll,
  '-filter_complex', `[0:a]volume=2.0[vo];[1:a]${bgvol},afade=t=in:st=0:d=2,afade=t=out:st=${Math.max(1, dur - 3).toFixed(2)}:d=3[bg];[vo][bg]amix=inputs=2:duration=first[a]`,
  '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', out], 'music mix');

log('✓ DONE → Forge-Vision_FULL.mp4  (' + dur.toFixed(0) + 's)');
