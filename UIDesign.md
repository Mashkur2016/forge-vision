# UI Design Specification — Project FORGE-Vision

> **Last Updated: 2026-04-23** — See "Implemented State" section below for current as-built status.

---

## Implemented State — As Built (2026-04-23)

### React Frontend (http://localhost:5173)

| Page | File | Status | Notes |
|------|------|--------|-------|
| Login | `frontend/src/pages/Login.tsx` | ✅ Live | JWT auth, redirect by role |
| Register | `frontend/src/pages/Register.tsx` | ✅ Live | Email + MFA setup |
| Forgot / Reset Password | `frontend/src/pages/ForgotPassword.tsx` | ✅ Live | |
| Onboarding Wizard | `frontend/src/pages/OnboardingWizard.tsx` | ✅ Live | 3-step: AI Model → SOP → Launch. Dark sidebar (#111827), gold accents, SOP hero card when selected |
| Setup Reset route | `frontend/src/App.tsx` (SetupReset) | ✅ Live | forge_force_wizard flag re-triggers wizard after next login |

### Streamlit Dashboard (http://localhost:8501)

| Page | File | Status | Notes |
|------|------|--------|-------|
| App shell + routing | `src/ui/app.py` | ✅ Live | JWT auth gate; tree sidebar nav (`NAV_GROUPS`); topbar with Help + Sign Out; role-switcher Admin-only |
| Dashboard | `src/ui/pages/dashboard_page.py` | ✅ Live | System status, live activity feed, Recent Sessions table with worker names |
| Live Training | `src/ui/pages/live_training_page.py` | ✅ Live | Step-by-step session; dual timers; IP camera; manual/offline mode; Session Summary |
| Simulation / Evaluation | `src/ui/pages/evaluation_page.py` | ✅ Live | Academic H1/H2/H3 evaluation dashboard |
| Session History | `src/ui/pages/session_history_page.py` | ✅ Live | Paginated table, date filters, CSV export |
| Worker Profiles | `src/ui/pages/worker_profiles_page.py` | ✅ Live | Search, skill level edit, session drill-down |
| Analytics | `src/ui/pages/analytics_page.py` | ✅ Live | 4 tabs: sessions, worker, SOP, heatmap |
| Reports | `src/ui/pages/report_generator_page.py` | ✅ Live | |
| Settings | `src/ui/pages/settings_page.py` | ✅ Live | LLM provider config + test |
| Leaderboard | `src/ui/pages/leaderboard_page.py` | ✅ Live | |
| My Progress | `src/ui/pages/my_progress_page.py` | ✅ Live | Worker self-view |
| Notifications | `src/ui/pages/notifications_page.py` | ✅ Live | |
| My Account | `src/ui/pages/account_page.py` | ✅ Live | RBAC: workers/trainers/supervisors own account only; Admin has lookup panel |
| User Management | `src/ui/pages/admin_users_page.py` | ✅ Live | Admin only |
| System Health | `src/ui/pages/admin_health_page.py` | ✅ Live | Admin only; LLM latency chart |
| Audit Log | `src/ui/pages/admin_audit_page.py` | ✅ Live | Admin only |
| Help | `src/ui/pages/help_page.py` | ✅ Live | All roles; accessible via topbar Help button |

### Design System (Implemented — overrides original spec below)

| Token | Value |
|-------|-------|
| Primary / Gold | `#D4B200` (Streamlit) / `#FFCC00` (React) |
| Active nav border | `#D4B200` left border |
| Page background | `#FEFFFF` |
| Sidebar background | `#FFFFFF` with gold divider |
| Card border | `#E5E7EB` |
| Font (React headings) | Anton (Google Fonts) |
| Font (React body) | Source Sans 3 |
| Button radius | 6–8px |

### Sidebar Navigation — Tree Structure (as of 2026-04-23)

```
🏠 Dashboard                    ← always pinned at top

── (divider) ──

🎬  TRAINING          ▶/▼       Admin / Trainer
    ├─ Live Training
    └─ Simulation

📊  DATA & ANALYTICS  ▶/▼       Admin / Trainer / Supervisor
    ├─ Session History
    ├─ Worker Profiles
    ├─ Analytics
    ├─ Reports
    └─ Leaderboard

⚙️  ADMINISTRATION    ▶/▼       Admin only
    ├─ Settings
    ├─ User Management
    ├─ System Health
    └─ Audit Log

👤  ACCOUNT           ▶/▼       All roles
    ├─ Notifications
    └─ My Account

[Help]  [Sign Out]              ← topbar (all roles)
```

Groups auto-expand when the active page is inside them. Slide-in animation on expand.

### Live Training — Current Layout

**Idle state (before session starts):**
```
┌─────────────────────────────────┬────────────────────────────┐
│  Training Ready banner (opt.)   │  ┌──────────────────────┐  │
│                                 │  │ ■ SESSION SETUP       │  │
│  📋 [SOP Name]                  │  │ (dark header, gold)   │  │
│  Steps: N  Duration: X min      │  │ Select SOP [dropdown] │  │
│  Category: Safety               │  │ Camera Source [0]     │  │
│                                 │  │ 🔊 Audio Feedback     │  │
│  Step 1: ... (expanded)         │  │                       │  │
│  Step 2: ... (collapsed)        │  │ ▶ START SESSION       │  │
│  ...                            │  │   (gold gradient btn) │  │
└─────────────────────────────────┴────────────────────────────┘
```

**Active session (step-by-step):**
```
Step X of N  [████████░░░░]  33%
⏱ 00:24 remaining    ⏳ 1:42 elapsed / 5:00 allocated

📋 Step X — [step name]  [🛑 SAFETY CRITICAL if applicable]
[Step description]
Required objects: `obj1`, `obj2`

[Camera feed col]  |  [AI Feedback col]

✓ Mark Step Complete    [ ⚠ Skip this step ▼ ]
```

**Session Summary (after all steps complete):**
```
✅ Session Complete — [SOP Name]
Total Time | Steps Done | Skipped | Score %
Per-step table: Step | Time (s) | Status | Notes
AI Deviation Log (collapsible)
[ Start New Session ]
```

---

## Design Decisions (Confirmed)

| Decision | Choice | Reason |
|----------|--------|--------|
| Theme | Dual Mode (Light + Dark, toggle per user) | Accessibility + user preference; saved in account |
| Frontend split | React (auth + live training) + Streamlit (data pages) | Best of both — proper auth UX, rapid analytics |
| Dashboard layout | Activity Feed + Status | Operational feel; real-time awareness for trainers |
| Extra pages | Onboarding Wizard, SOP Builder, Leaderboard, Report Generator | All 4 confirmed |

---

## Design System

### Colour Palette

```
LIGHT MODE                          DARK MODE
──────────────────────────────      ──────────────────────────────
Background:    #FFFFFF              Background:    #0D1117
Surface:       #F8FAFC              Surface:       #161B22
Surface-2:     #F1F5F9              Surface-2:     #21262D
Border:        #E2E8F0              Border:        #30363D

Primary:       #2563EB  (blue)      Primary:       #00D4FF  (cyan)
Primary-hover: #1D4ED8              Primary-hover: #00B8E6

Success:       #16A34A  (green)     Success:       #22C55E
Warning:       #D97706  (amber)     Warning:       #F59E0B
Error:         #DC2626  (red)       Error:         #EF4444
Info:          #0284C7             Info:          #38BDF8

Text-primary:  #0F172A             Text-primary:  #F0F6FC
Text-secondary:#64748B             Text-secondary:#8B949E
Text-muted:    #94A3B8             Text-muted:    #6E7681
```

### Typography

```
Font family:   Inter (headings) + system-ui (body)
               CDN: fonts.googleapis.com/css2?family=Inter

Heading 1:     32px / 700 weight
Heading 2:     24px / 600 weight
Heading 3:     18px / 600 weight
Body:          14px / 400 weight
Caption:       12px / 400 weight / text-secondary colour
Code/mono:     13px / JetBrains Mono or Consolas
```

### Spacing & Radius

```
Border radius:  cards = 12px | buttons = 8px | inputs = 6px | badges = 20px
Spacing scale:  4 | 8 | 12 | 16 | 24 | 32 | 48 | 64 px
Shadow (light): 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)
Shadow (dark):  0 1px 3px rgba(0,0,0,0.4),  0 1px 2px rgba(0,0,0,0.3)
```

### Status Colours (Used across all pages)

```
✅ Correct / Online / Approved   → Success green
⚠️ Warning / Needs attention     → Warning amber
❌ Error / Offline / Failed      → Error red
🔵 Info / In Progress / Pending  → Info blue
🟣 AI Feedback active            → Primary cyan (dark) / blue (light)
```

---

## Technology Stack

### React Pages (Vite + TypeScript)
- **Framework:** React 18 + Vite + TypeScript
- **Component library:** shadcn/ui (Radix UI primitives + Tailwind CSS)
- **Routing:** React Router v6
- **State:** Zustand (auth state) + React Query (server state)
- **HTTP:** Axios
- **WebSocket:** native browser WebSocket API
- **Dark mode:** Tailwind CSS `dark:` variant + localStorage preference
- **Charts (if needed):** Recharts

### Streamlit Pages
- **Custom theme:** `.streamlit/config.toml` — matches design system colours
- **Dark/Light:** Streamlit built-in theme toggle + custom CSS injection
- **Charts:** Plotly (interactive) + Altair
- **Tables:** `st.dataframe` with custom styling

---

## Complete Page List (26 Pages)

### A. React Pages (Auth + Live Training)

| Code | Page | Route | Role |
|------|------|-------|------|
| A1 | Login | `/login` | Public |
| A2 | Register | `/register` | Public |
| A3 | Forgot Password | `/forgot-password` | Public |
| A4 | Reset Password | `/reset-password?token=...` | Public |
| A5 | MFA Verification | `/mfa` | Admin, Supervisor |
| A6 | Live Training Session | `/training/live` | Worker, Trainer |
| A7 | Onboarding Wizard | `/onboarding` | All (first login) |

### B. Streamlit Pages (Data + Admin)

| Code | Page | Route | Role |
|------|------|-------|------|
| B1 | Dashboard | `/` | All (role-personalised) |
| B2 | My Progress | `/my-progress` | Worker |
| B3 | Simulation Mode | `/simulation` | Trainer, Admin |
| B4 | SOP Library | `/sops` | Trainer, Supervisor, Admin |
| B5 | SOP Builder | `/sops/builder` | Trainer, Admin |
| B6 | Session History | `/sessions` | Trainer, Supervisor, Admin |
| B7 | Worker Profiles | `/workers` | Trainer, Supervisor, Admin |
| B8 | Analytics & Reports | `/analytics` | Supervisor, Admin |
| B9 | Report Generator | `/reports` | Supervisor, Admin |
| B10 | Leaderboard & Badges | `/leaderboard` | Worker, Trainer |
| B11 | Settings (LLM + system) | `/settings` | Admin |
| B12 | My Account | `/account` | All |
| B13 | Notifications Centre | `/notifications` | All |
| B14 | User Management | `/admin/users` | Admin |
| B15 | System Health | `/admin/health` | Admin |
| B16 | Audit Log | `/admin/audit` | Admin |
| B17 | Help & Documentation | `/help` | All |

---

## Wireframes

---

### A1 — Login Page (React)

```
┌─────────────────────────────────────────────────────────────────┐
│                                              ☀️/🌙 toggle        │
│                                                                 │
│              🏭  FORGE-Vision                                   │
│         AI-Powered Employee Training System                     │
│                                                                 │
│         ┌───────────────────────────────────┐                  │
│         │           Sign In                 │                  │
│         │                                   │                  │
│         │  Email                            │                  │
│         │  ┌─────────────────────────────┐  │                  │
│         │  │ you@company.com             │  │                  │
│         │  └─────────────────────────────┘  │                  │
│         │                                   │                  │
│         │  Password               Forgot? → │                  │
│         │  ┌─────────────────────────────┐  │                  │
│         │  │ ••••••••••••         👁      │  │                  │
│         │  └─────────────────────────────┘  │                  │
│         │                                   │                  │
│         │  ┌─────────────────────────────┐  │                  │
│         │  │       Sign In →             │  │  ← primary btn   │
│         │  └─────────────────────────────┘  │                  │
│         │                                   │                  │
│         │  Don't have an account? Register  │                  │
│         └───────────────────────────────────┘                  │
│                                                                 │
│         🔒 Secured with AES-256 · GDPR Compliant               │
└─────────────────────────────────────────────────────────────────┘
```

---

### A2 — Register Page (React)

```
┌─────────────────────────────────────────────────────────────────┐
│                                              ☀️/🌙 toggle        │
│              🏭  FORGE-Vision                                   │
│                                                                 │
│         ┌───────────────────────────────────┐                  │
│         │        Create Account             │                  │
│         │                                   │                  │
│         │  ┌─────────────┐ ┌─────────────┐  │                  │
│         │  │ First name  │ │ Last name   │  │                  │
│         │  └─────────────┘ └─────────────┘  │                  │
│         │                                   │                  │
│         │  Email                            │                  │
│         │  ┌─────────────────────────────┐  │                  │
│         │  │ you@company.com             │  │                  │
│         │  └─────────────────────────────┘  │                  │
│         │                                   │                  │
│         │  Department / Team (optional)     │                  │
│         │  ┌─────────────────────────────┐  │                  │
│         │  │ e.g. Assembly Line A        │  │                  │
│         │  └─────────────────────────────┘  │                  │
│         │                                   │                  │
│         │  Password          Confirm PW     │                  │
│         │  ┌──────────────┐ ┌────────────┐  │                  │
│         │  │ ••••••  👁   │ │ ••••• 👁  │  │                  │
│         │  └──────────────┘ └────────────┘  │                  │
│         │  ████░░░░  Strength: Good         │                  │
│         │                                   │                  │
│         │  ☑ I agree to data processing     │                  │
│         │    terms (GDPR consent)           │                  │
│         │                                   │                  │
│         │  ┌─────────────────────────────┐  │                  │
│         │  │     Create Account →        │  │                  │
│         │  └─────────────────────────────┘  │                  │
│         │  Already registered? Sign in      │                  │
│         └───────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### A3 — Forgot Password (React)

```
┌─────────────────────────────────────────────────────────────────┐
│              🏭  FORGE-Vision                                   │
│                                                                 │
│         ┌───────────────────────────────────┐                  │
│         │       Reset your password         │                  │
│         │                                   │                  │
│         │  Enter your email and we'll send  │                  │
│         │  a reset link.                    │                  │
│         │                                   │                  │
│         │  Email                            │                  │
│         │  ┌─────────────────────────────┐  │                  │
│         │  │ you@company.com             │  │                  │
│         │  └─────────────────────────────┘  │                  │
│         │                                   │                  │
│         │  ┌─────────────────────────────┐  │                  │
│         │  │    Send Reset Link →        │  │                  │
│         │  └─────────────────────────────┘  │                  │
│         │                                   │                  │
│         │  ← Back to Sign In               │                  │
│         └───────────────────────────────────┘                  │
│                                                                 │
│    ✅ Success state:                                            │
│    "Check your inbox — link expires in 30 minutes"             │
└─────────────────────────────────────────────────────────────────┘
```

---

### A5 — MFA Verification (React)

```
┌─────────────────────────────────────────────────────────────────┐
│              🏭  FORGE-Vision                                   │
│                                                                 │
│         ┌───────────────────────────────────┐                  │
│         │   Two-Factor Authentication       │                  │
│         │                                   │                  │
│         │  🔐 Open your authenticator app  │                  │
│         │     and enter the 6-digit code.   │                  │
│         │                                   │                  │
│         │  ┌────┐ ┌────┐ ┌────┐ ┌────┐     │                  │
│         │  │ 4  │ │ 8  │ │ 1  │ │    │     │  ← 6 digit boxes │
│         │  └────┘ └────┘ └────┘ └────┘     │                  │
│         │  ┌────┐ ┌────┐                   │                  │
│         │  │    │ │    │    (auto-submit)   │                  │
│         │  └────┘ └────┘                   │                  │
│         │                                   │                  │
│         │  Code expires in 00:28            │                  │
│         │  Didn't receive it? Resend code   │                  │
│         │                                   │                  │
│         │  ← Sign in as different user     │                  │
│         └───────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### B1 — Dashboard (Streamlit — Activity Feed Layout)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🏭 FORGE-Vision        🔍 Search...      🔔 3  ☀️/🌙   👤 Dr. Karim │
├──────────┬───────────────────────────────────────────────────────────┤
│          │                                                           │
│ 🏠 Home  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │
│          │  │ ▶ Start      │ │ 📋 New SOP   │ │ 📊 Reports   │     │
│ 🎬 Train │  │   Session    │ │              │ │              │     │
│          │  └──────────────┘ └──────────────┘ └──────────────┘     │
│ 🎮 Sim   │                                                           │
│          │  ┌─────────────────────────────┬───────────────────────┐ │
│ 📋 SOPs  │  │  System Status              │  Live Activity Feed   │ │
│          │  │                             │                       │ │
│ 👷 Workers│ │  ✅ API Backend   Online    │  10:32 👷 John S.     │ │
│          │  │  ✅ LLM: Groq    Tested    │  Started Wiring SOP   │ │
│ 📊 Data  │  │  ✅ Database     Connected │                       │ │
│          │  │  ⚠️ 2 Alerts    View →     │  10:28 ❌ Error       │ │
│ 🏆 Board │  │                             │  Mary K. — Step 3     │ │
│          │  │  Active Sessions            │  missing PPE          │ │
│ ⚙️ Admin │  │  👷 3 workers training      │                       │ │
│          │  │  📍 Assembly, Wiring, Test  │  10:15 ✅ Completed   │ │
│ 🔔 Alerts│  │                             │  Ahmed R. — SOP #4    │ │
│          │  │  Today's Stats              │  Time: 8m 42s         │ │
│ 👤 Me    │  │  Sessions: 12  Errors: 3.2% │                       │ │
│          │  │  Avg Time: 9m  Accuracy:87% │  09:58 👷 Maria L.    │ │
│          │  └─────────────────────────────┴───────────────────────┘ │
│          │                                                           │
│          │  ┌───────────────────────────────────────────────────┐   │
│          │  │  Recent Sessions                          View all→│   │
│          │  │  Worker      SOP            Score  Duration Status │   │
│          │  │  John S.     Motor Wiring   87%    9m 12s  ✅      │   │
│          │  │  Mary K.     Assembly A     72%    14m 3s  ⚠️      │   │
│          │  │  Ahmed R.    Safety Check   95%    6m 58s  ✅      │   │
│          │  └───────────────────────────────────────────────────┘   │
└──────────┴───────────────────────────────────────────────────────────┘
```

---

### A6 — Live Training Session (React + WebSocket)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🏭 FORGE-Vision  │  🎬 Live Training: Motor Wiring SOP   [■ End]    │
├──────────────────┴───────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────┐  ┌─────────────────────┐  │
│  │                                      │  │  SOP Progress       │  │
│  │                                      │  │  ─────────────────  │  │
│  │         LIVE CAMERA FEED             │  │  ✅ Step 1: Power off│  │
│  │         (WebSocket stream)           │  │  ✅ Step 2: Red wire  │  │
│  │                                      │  │  🔵 Step 3: Blue wire│  │  ← current
│  │   [bounding box overlay]             │  │  ○  Step 4: Verify   │  │
│  │   "Right hand — terminal area"       │  │  ○  Step 5: Power on │  │
│  │                                      │  │                     │  │
│  │   ┌───────────────────────────────┐  │  │  ─────────────────  │  │
│  │   │ 🤖 AI Feedback                │  │  │  Step 3 of 5        │  │
│  │   │ "Connect the blue wire to     │  │  │  ████████░░  60%    │  │
│  │   │  terminal B — make sure the   │  │  │                     │  │
│  │   │  power is still OFF before    │  │  │  ─────────────────  │  │
│  │   │  tightening."                 │  │  │  Session Timer      │  │
│  │   └───────────────────────────────┘  │  │  ⏱ 04:32            │  │
│  │                                      │  │                     │  │
│  └──────────────────────────────────────┘  │  Error Count: 1     │  │
│                                            │  ⚠️ Step 2: wrong   │  │
│  Confidence: ████████░░ 82%   Latency: 1.1s│  terminal used      │  │
│                                            └─────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

### A7 — Onboarding Wizard (React — 3 Steps)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🏭 FORGE-Vision — Welcome, Dr. Karim!                               │
│                                                                      │
│          ●────────────●────────────○                                 │
│         Step 1      Step 2      Step 3                               │
│     Configure LLM  Load SOP   Try Demo                              │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Step 1: Configure your AI Language Model                  │     │
│  │                                                            │     │
│  │  FORGE-Vision uses an LLM to generate real-time feedback.  │     │
│  │  Start with a free option — you can change this anytime.  │     │
│  │                                                            │     │
│  │  ┌──────────────────────────────────┐                      │     │
│  │  │  ● Groq (Free — Recommended)    │                      │     │
│  │  │  ○ Google Gemini (Free)          │                      │     │
│  │  │  ○ OpenAI GPT-4o mini            │                      │     │
│  │  │  ○ Ollama Local                  │                      │     │
│  │  └──────────────────────────────────┘                      │     │
│  │                                                            │     │
│  │  API Key:  [────────────────────────]  [Test Connection]  │     │
│  │            ✅ Connected in 847ms                           │     │
│  │                                                            │     │
│  │              [Skip for now]  [Next: Load SOP →]           │     │
│  └────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

---

### B5 — SOP Builder (Streamlit — Visual Wizard)

```
┌──────────────────────────────────────────────────────────────────────┐
│  📋 SOP Builder                              [💾 Save] [Preview YAML]│
│  ─────────────────────────────────────────────────────────────────── │
│  SOP Name:  [Motor Wiring Procedure v1        ]  Category: [Elec. ▾]│
│  Department:[Assembly Line A                  ]  Est. Time: [15 min] │
│                                                                      │
│  ─────────── Steps ──────────────────────────────────────────────── │
│                                                                      │
│  ┌─ Step 1 ──────────────────────────────────────────────── [✕] ─┐  │
│  │  Name: [Switch off main power supply                         ]│  │
│  │  ┌──────────────────────────┐  ┌──────────────────────────┐  │  │
│  │  │ Required Objects         │  │ Expected Pose            │  │  │
│  │  │ [+ power_switch] [+ ...]│  │ [right_hand_reach_switch]│  │  │
│  │  └──────────────────────────┘  └──────────────────────────┘  │  │
│  │  Time limit: [30] seconds   ☑ Safety critical step          │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ Step 2 ──────────────────────────────────────────────── [✕] ─┐  │
│  │  Name: [Connect red wire to terminal A                       ]│  │
│  │  ...                                                          │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  [+ Add Step]        [⬆ Move up] [⬇ Move down]  [🗑 Delete step]   │
│                                                                      │
│  ─── OR import from document ──────────────────────────────────── │
│  [📄 Upload PDF/Word manual]  → AI will auto-extract steps         │
│  (uses LLM SOP Parser — Enhancement 1)                            │
└──────────────────────────────────────────────────────────────────────┘
```

---

### B10 — Leaderboard & Badges (Streamlit)

```
┌──────────────────────────────────────────────────────────────────────┐
│  🏆 Leaderboard & Achievements           This week ▾  Assembly ▾    │
│  ──────────────────────────────────────────────────────────────────  │
│                                                                      │
│  ┌──────────────────────────────────┐  ┌────────────────────────┐   │
│  │  TOP PERFORMERS                  │  │  YOUR BADGES           │   │
│  │                                  │  │                        │   │
│  │  🥇 Ahmed R.     95%  12 sessions│  │  🎯 Zero Error Day     │   │
│  │  🥈 Maria L.     91%   9 sessions│  │  ⚡ Speed Demon        │   │
│  │  🥉 John S.      87%  15 sessions│  │  🔒 Safety First  x3   │   │
│  │  4.  Sarah K.    84%   8 sessions│  │  📈 Improving Fast     │   │
│  │  5.  You →       82%  11 sessions│  │                        │   │
│  │     ↑ Up 2 this week            │  │  [View all badges →]   │   │
│  └──────────────────────────────────┘  └────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  YOUR PROGRESS THIS WEEK                                     │   │
│  │                                                              │   │
│  │  Accuracy trend:  75% → 78% → 80% → 82%  ▲ Improving!       │   │
│  │  Errors per session: 5 → 4 → 3 → 2  ▲ Getting better!       │   │
│  │                                                              │   │
│  │  Next badge: 🏅 "Consistent Performer" — 3 more sessions    │   │
│  │  at 85%+ accuracy required.                   ████░░  80%   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

### B11 — Settings Page (Streamlit — Already Built)

Already implemented in Phase 0. Will add dark/light theme toggle here.

---

### B14 — User Management (Streamlit — Admin Only)

```
┌──────────────────────────────────────────────────────────────────────┐
│  👥 User Management            [+ Invite User]  [📥 Export CSV]      │
│  ─────────────────────────────────────────────────────────────────── │
│  Search: [──────────────]  Role: [All ▾]  Status: [Active ▾]        │
│                                                                      │
│  ┌──────┬─────────────────┬───────────┬──────────┬────────┬───────┐ │
│  │  ID  │  Name           │  Role     │ Sessions │ Last   │Action │ │
│  ├──────┼─────────────────┼───────────┼──────────┼────────┼───────┤ │
│  │  001 │  Dr. K. Rezaul  │ 🔴 Admin  │    —     │ Today  │ Edit  │ │
│  │  002 │  John Smith     │ 🟡 Worker │   15     │ Today  │ Edit  │ │
│  │  003 │  Maria López    │ 🟢 Trainer│   9      │ 2h ago │ Edit  │ │
│  │  004 │  Ahmed Rahman   │ 🟡 Worker │   12     │ 1h ago │ Edit  │ │
│  │  005 │  Sarah K.       │ 🔵 Supv.  │    —     │ Today  │ Edit  │ │
│  └──────┴─────────────────┴───────────┴──────────┴────────┴───────┘ │
│                                                                      │
│  Roles: 🔴 Admin  🔵 Supervisor  🟢 Trainer  🟡 Worker              │
└──────────────────────────────────────────────────────────────────────┘
```

---

### B15 — System Health (Streamlit — Admin Only)

```
┌──────────────────────────────────────────────────────────────────────┐
│  🖥️ System Health                     Last refresh: 10:34:21  [🔄]  │
│  ─────────────────────────────────────────────────────────────────── │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐           │
│  │ API Backend    │ │ PostgreSQL DB  │ │ LLM Provider   │           │
│  │ ✅ Online      │ │ ✅ Connected   │ │ ✅ Groq/Llama  │           │
│  │ 45ms latency   │ │ 12ms query avg │ │ 847ms response │           │
│  └────────────────┘ └────────────────┘ └────────────────┘           │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  LLM Response Latency (last 24h)                              │  │
│  │  [line chart: latency over time]                              │  │
│  │  Avg: 847ms  P95: 1.2s  Max: 2.1s                            │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐  │
│  │  Active Sessions: 3      │  │  DB Storage                      │  │
│  │  API Requests/min: 24    │  │  Sessions: 1,240   12MB          │  │
│  │  Errors (1h): 0          │  │  Videos: 0 (not stored)          │  │
│  │  Uptime: 99.8%           │  │  Audit log: 4,521  2.1MB         │  │
│  └──────────────────────────┘  └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Navigation Logic (Role-Aware Sidebar)

```python
# Sidebar items shown based on role
NAVIGATION = {
    "worker":     ["Dashboard", "My Progress", "Leaderboard", "Notifications", "My Account"],
    "trainer":    ["Dashboard", "Live Training", "Simulation", "SOP Library",
                   "SOP Builder", "Session History", "Worker Profiles",
                   "Leaderboard", "Notifications", "My Account"],
    "supervisor": ["Dashboard", "Session History", "Worker Profiles",
                   "Analytics & Reports", "Report Generator",
                   "Notifications", "My Account"],
    "admin":      ["Dashboard", "Live Training", "Simulation", "SOP Library",
                   "SOP Builder", "Session History", "Worker Profiles",
                   "Analytics & Reports", "Report Generator", "Settings",
                   "Leaderboard", "User Management", "System Health",
                   "Audit Log", "Notifications", "My Account"],
}
```

---

## Streamlit Theme Configuration

```toml
# .streamlit/config.toml
[theme]
# Light mode base (user can toggle to dark)
primaryColor = "#2563EB"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F8FAFC"
textColor = "#0F172A"
font = "sans serif"
```

---

## File Structure for UI

```
src/ui/
├── app.py                      ← Streamlit main app (already built)
├── components/
│   ├── sidebar.py              ← Role-aware navigation
│   ├── header.py               ← Top bar (search, notifications, theme toggle)
│   ├── kpi_card.py             ← Reusable metric card component
│   ├── activity_feed.py        ← Live activity feed component
│   └── status_badge.py         ← Coloured status badges
└── pages/
    ├── dashboard_page.py       ← Already built (update to full design)
    ├── settings_page.py        ← Already built
    ├── my_progress_page.py
    ├── simulation_page.py
    ├── sop_library_page.py
    ├── sop_builder_page.py
    ├── session_history_page.py
    ├── worker_profiles_page.py
    ├── analytics_page.py
    ├── report_generator_page.py
    ├── leaderboard_page.py
    ├── account_page.py
    ├── notifications_page.py
    ├── admin_users_page.py
    ├── admin_health_page.py
    ├── admin_audit_page.py
    └── help_page.py

frontend/                       ← React app (Vite + TypeScript)
├── src/
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── Register.tsx
│   │   ├── ForgotPassword.tsx
│   │   ├── ResetPassword.tsx
│   │   ├── MFAVerification.tsx
│   │   ├── LiveTraining.tsx
│   │   └── OnboardingWizard.tsx
│   ├── components/
│   │   ├── ui/                 ← shadcn/ui components
│   │   ├── ThemeToggle.tsx
│   │   ├── CameraFeed.tsx
│   │   ├── FeedbackOverlay.tsx
│   │   └── SOPProgressPanel.tsx
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useWebSocket.ts
│   │   └── useTheme.ts
│   ├── store/
│   │   └── authStore.ts        ← Zustand auth state
│   └── lib/
│       ├── api.ts              ← Axios instance
│       └── theme.ts            ← Light/dark CSS variables
├── package.json
├── tailwind.config.ts
└── vite.config.ts
```

---

## Summary — Final Page Count

| Category | Count | Technology |
|----------|-------|-----------|
| Auth pages | 5 | React |
| Live Training + Onboarding | 2 | React |
| Dashboard + data pages | 12 | Streamlit |
| Admin pages | 3 | Streamlit |
| Utility pages | 3 | Streamlit |
| **Total** | **25 pages** | React (7) + Streamlit (18) |

---

## Implementation Status (as of 2026-04-16)

### Streamlit Pages — Built and Tested

The following Streamlit pages have been fully implemented as part of the FORGE-Vision system:

| Code | Page | File | Phase | Status |
|------|------|------|-------|--------|
| B1 | Dashboard | `src/ui/pages/dashboard_page.py` | Phase 0 / 4 | ✅ Built |
| B3 | Live Training | `src/ui/pages/live_training_page.py` | Phase 3 | ✅ Built |
| B8 | Analytics & Reports | `src/ui/pages/analytics_page.py` | Phase 4 | ✅ Built |
| B11 | Settings (LLM + system) | `src/ui/pages/settings_page.py` | Phase 0 | ✅ Built |
| — | Academic Evaluation | `src/ui/pages/evaluation_page.py` | Phase 5 | ✅ Built |

All five pages are wired into the multi-page Streamlit app via `src/ui/app.py` with role-aware navigation routing.

### React Frontend Pages — Scaffolded

The React frontend (`frontend/`) was scaffolded with Vite + TypeScript + Tailwind CSS and the auth page structure defined. Full implementation of all 7 React pages (A1–A7) is planned for Phase B production deployment but is outside the scope of the academic DBA prototype, which uses Streamlit throughout.

### Analytics Page (B8) — Implemented Features

`src/ui/pages/analytics_page.py` implements the full B8 design with four tabs:

| Tab | Content |
|-----|---------|
| Session History | Paginated session table with worker filter; session score, duration, deviation count |
| Worker Performance | Per-worker accuracy chart; sessions-to-competency estimate; trend (improving/plateau/regressing) |
| SOP Analytics | SOP completion rates; avg score per SOP; top deviation types per SOP |
| Deviation Heatmap | Heatmap of error type × SOP step; filterable by SOP; Altair interactive charts |

All tabs connect to `/api/v1/analytics/*` endpoints via `httpx`; Altair charts used with pandas fallback.

### Evaluation Page (Academic) — Implemented Features

`src/ui/pages/evaluation_page.py` implements the Phase 5 academic evaluation UI:

- Configurable experiment parameters (n per group, α, effect size, random seed)
- Prominent `⚠️ SYNTHETIC DATA` banner for academic integrity compliance (Rules.md §3.1)
- Distribution plots: pre/post error rates, completion times by group (Altair box plots)
- One-click hypothesis test runner: H1 (Welch t), H2 (ANOVA + Tukey HSD), H3 (Welch t)
- Results display: t/F statistics, p-values, effect sizes (Cohen's d / η²), supported/not-supported verdict
- JSON results download for thesis appendix

### Pages Documented for Future Implementation

The following pages from the full design specification are documented but not yet implemented (deferred to production deployment phase):

| Code | Page | Reason Deferred |
|------|------|-----------------|
| A1–A7 | React Auth + Live Training pages | Phase B production; academic prototype uses Streamlit |
| B2 | My Progress | Worker-facing; requires real participant data |
| B4–B5 | SOP Library + Builder | Admin tooling; SOPs currently loaded from YAML files |
| B6 | Session History | Covered in Analytics page for thesis purposes |
| B7 | Worker Profiles | API built; dedicated UI page deferred |
| B9 | Report Generator | Analytics page covers report needs for thesis |
| B10 | Leaderboard & Badges | Gamification feature; not required for thesis evaluation |
| B12–B13 | My Account + Notifications | Phase B production features |
| B14–B16 | Admin (User Mgmt, Health, Audit Log) | Admin tooling; covered by API endpoints |
| B17 | Help & Documentation | Covered by CLAUDE.md and Architecture.md |
