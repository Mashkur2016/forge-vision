/**
 * Shared config for the full narrated presentation video build.
 * Segment order → output clip name (seg_NN.mp4). Sorted concat = final order.
 *
 *   00–06  intro slides           (render_slides.mjs)
 *   10–13  Login, Top Bar, Sidebar, Dashboard   (record_walkthrough.mjs)
 *   14     E1 Live Training GAP   (user's clip + E1.mp3)
 *   15–30  Simulation … Logout    (record_walkthrough.mjs)
 *   90–92  outro slides           (render_slides.mjs)
 */
import { spawnSync } from 'node:child_process';
import ffmpeg from '@ffmpeg-installer/ffmpeg';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

export const FF = ffmpeg.path;
export const DIR = dirname(fileURLToPath(import.meta.url));
export const VO = resolve(DIR, 'voiceover');
export const BG = resolve(DIR, 'bgmusic');
export const SEG = resolve(DIR, 'segments');
export const W = 1920, H = 1080;
export const SPACE = 'https://mashkura-forge-vision.hf.space';
export const EMAIL = 'mashkur.alam@hotmail.co.uk', PASS = 'ForgeDemo123!';

export function durationOf(file) {
  const out = spawnSync(FF, ['-i', file], { encoding: 'utf8' }).stderr || '';
  const m = out.match(/Duration:\s*(\d+):(\d+):(\d+\.\d+)/);
  return m ? (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) : 0;
}

// Intro slides: seg id, reveal slide index, mp3 filename
export const INTRO = [
  { id: '00', slide: 0, mp3: 'Slide 1 — Title.mp3' },
  { id: '01', slide: 1, mp3: 'Slide 2 — What it is.mp3' },
  { id: '02', slide: 2, mp3: 'Slide 3 — The problem.mp3' },
  { id: '03', slide: 3, mp3: 'Slide 4 — How it works.mp3' },
  { id: '04', slide: 4, mp3: 'Slide 5 — System architecture.mp3' },
  { id: '05', slide: 5, mp3: 'Slide 6 — Components used.mp3' },
  { id: '06', slide: 6, mp3: "Slide 7 — Let's see it live.mp3" },
];

export const OUTRO = [
  { id: '90', slide: 0, mp3: 'Slide 1 — What we saw.mp3' },
  { id: '91', slide: 1, mp3: 'Slide 2 — Results.mp3' },
  { id: '92', slide: 2, mp3: 'Slide 3 — Contribution-thank you.mp3' },
];

// App pages: seg id, sidebar nav label (null = stay on dashboard), waitText for sync,
// mp3 filename, and a "focus" describing what the pointer should highlight.
export const PAGES = [
  { id: '10', nav: null, wait: null, mp3: 'A. Login.mp3', kind: 'login' },
  { id: '11', nav: 'Dashboard', wait: 'System Status', mp3: 'B. The Top Bar.mp3', focus: 'topbar' },
  { id: '12', nav: 'Dashboard', wait: 'System Status', mp3: 'C. The Sidebar Navigation.mp3', focus: 'sidebar' },
  { id: '13', nav: 'Dashboard', wait: 'System Status', mp3: 'D. Dashboard.mp3', focus: 'dashboard' },
  // 14 = E1 Live Training gap (handled in assemble)
  { id: '15', nav: 'Simulation', wait: 'Experiment Configuration', mp3: 'E2. Simulation — the research instrument.mp3', focus: 'simulation' },
  { id: '16', nav: 'Create SOP', wait: 'SOP Metadata', mp3: 'E3. Create SOP.mp3', focus: 'createsop' },
  { id: '17', nav: 'Session History', wait: 'Deviation Drill-Down', mp3: 'F1. Session History.mp3', focus: 'scroll' },
  { id: '18', nav: 'Staff Profiles', wait: 'Profile Detail', mp3: 'F2. Staff Profiles.mp3', focus: 'scroll' },
  { id: '19', nav: 'SOP Library', wait: 'Showing', mp3: 'F3. SOP Library.mp3', focus: 'scroll' },
  { id: '20', nav: 'Analytics', wait: 'Worker Performance', mp3: 'F4. Analytics.mp3', focus: 'analytics_tabs' },
  { id: '21', nav: 'Reports', wait: 'Generate Report', mp3: 'F5. Reports.mp3', focus: 'scroll' },
  { id: '22', nav: 'Leaderboard', wait: 'Study group', mp3: 'F6. Leaderboard.mp3', focus: 'scroll' },
  { id: '23', nav: 'Settings', wait: 'LLM Configuration', mp3: 'G1. Settings.mp3', focus: 'settings' },
  { id: '24', nav: 'User Management', wait: 'Add New User', mp3: 'G2. User Management.mp3', focus: 'scroll' },
  { id: '25', nav: 'System Health', wait: 'LLM Latency', mp3: 'G3. System Health.mp3', focus: 'scroll' },
  { id: '26', nav: 'Audit Log', wait: 'entries', mp3: 'G4. Audit Log.mp3', focus: 'scroll' },
  { id: '27', nav: 'Notifications', wait: 'Mark all read', mp3: 'H1. Notifications.mp3', focus: 'scroll' },
  { id: '28', nav: 'My Account', wait: 'Account Lookup', mp3: 'H2. My Account.mp3', focus: 'scroll' },
  { id: '29', nav: null, topbarBtn: 'Help', wait: 'Getting Started', mp3: 'Help.mp3', focus: 'help_tabs' },
  { id: '30', nav: null, wait: null, mp3: 'Logout.mp3', focus: 'logout' },
];

// Two Live-Training demonstrations spliced after the Dashboard: a clean run, then
// a run with skips that surfaces the AI coaching. Each = a SILENT screen-capture
// the user records + its TTS narration (overlaid, with bgmusic under it).
//   live_clean.mp4 + E1a.mp3   ·   live_skip.mp4 + E1b.mp3
export const E1 = [
  { id: '14',  mp3: 'E1a.mp3', clip: 'live_clean.mp4', env: 'LIVE_CLEAN' },
  { id: '14b', mp3: 'E1b.mp3', clip: 'live_skip.mp4',  env: 'LIVE_SKIP' },
];
