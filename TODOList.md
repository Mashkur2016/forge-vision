# FORGE-Vision — TODO List & Approval Tracker

> Each task must be completed, tested, reviewed, and approved before the next begins.
> This file is the single source of truth for project progress.

---

## How This Works

```
TASK STATUS CODES:
  Todo       — Not started
  In Progress — Currently being worked on
  Testing    — Built, now being tested/reviewed
  Approved   — Tested, reviewed, and approved by researcher
  Blocked    — Cannot proceed (dependency or issue)
```

**Rule:** When a task reaches Testing, STOP and present results to researcher for review before marking Approved.

---

## PHASE 0: Documentation & Foundation

| # | Task | Status | Completed | Notes |
|---|------|--------|-----------|-------|
| 0.1 | CLAUDE.md | Approved | 2026-04-07 | |
| 0.2 | Architecture.md | Approved | 2026-04-07 | |
| 0.3 | Rules.md | Approved | 2026-04-07 | |
| 0.4 | LiteratureReview.md | Approved | 2026-04-07 | 32 papers, 6 themes |
| 0.5 | GapsAnalysis.md | Approved | 2026-04-07 | 8 research gaps |
| 0.6 | Enhancements.md | Approved | 2026-04-07 | 11 proposals, 3 tiers |
| 0.7 | SecurityEnhancements.md | Approved | 2026-04-07 | OWASP Top 10 |
| 0.8 | LLM_Strategy.md | Approved | 2026-04-07 | Cost comparison |
| 0.9 | FastAPI backend — LLM Settings endpoints | Approved | 2026-04-07 | Docker confirmed UP |
| 0.10 | Streamlit Settings UI page | Approved | 2026-04-07 | |
| 0.11 | 5 LLM providers (OpenAI/Groq/Anthropic/Gemini/Ollama) | Approved | 2026-04-07 | |
| 0.12 | requirements.txt, docker-compose.yml, .env.example | Approved | 2026-04-07 | |
| 0.13 | ProjectPhases.md + TODOList.md | Approved | 2026-04-07 | |
| 0.15 | UIDesign.md — 26-page UI specification + wireframes | Approved | 2026-04-08 | React (7) + Streamlit (18) pages |
| 0.16 | FastAPI auth backend — JWT + MFA + rate limiting | Approved | 2026-04-08 | 7 endpoints |
| 0.17 | React frontend scaffold — Vite + TS + shadcn/ui | Approved | 2026-04-08 | Build passes |
| 0.18 | React auth pages (A1–A5) — Login, Register, ForgotPW, ResetPW, MFA | Approved | 2026-04-08 | |
| 0.19 | React live pages (A6–A7) — LiveTraining stub, OnboardingWizard | Approved | 2026-04-08 | |
| 0.14 | **PHASE 0 APPROVAL** | Approved | 2026-04-08 | Docker UP, all components verified |

---

## PHASE 1: Simulation Development

| # | Task | Status | Completed | Notes |
|---|------|--------|-----------|-------|
| 1.1 | SOP YAML schema definition | Approved | 2026-04-12 | sop_schema.py + 3 example SOPs in data/sops/ |
| 1.2 | SOP parser and validator | Approved | 2026-04-12 | sop_parser.py — YAML/JSON loader with Pydantic validation |
| 1.3 | OpenCV augmentation pipeline | Approved | 2026-04-12 | augmentation.py — 7 transforms, consistent clip mode |
| 1.4 | Scenario generator (5 error types) | Approved | 2026-04-12 | scenario_generator.py — all 5 scenario types |
| 1.5 | Synthetic dataset (500+ clips) | Approved | 2026-04-12 | dataset_builder.py — 1,200 clips generated |
| 1.6 | LLM SOP Parser (auto from PDF/Word) | Approved | 2026-04-12 | llm_sop_parser.py — Enhancement 1 |
| 1.7 | Unit tests for simulation pipeline | Approved | 2026-04-12 | 60+ tests across 3 test files |
| 1.8 | **PHASE 1 APPROVAL** | Approved | 2026-04-12 | Researcher approved — proceeded to Phase 2 |

---

## PHASE 2: CV Model Training

| # | Task | Status | Completed | Notes |
|---|------|--------|-----------|-------|
| 2.1 | PyTorch training pipeline + MLflow | Approved | 2026-04-14 | trainer.py + train_config.yaml + SyntheticSOPDataset |
| 2.2 | MediaPipe pose estimation module | Approved | 2026-04-14 | pose_estimator.py — 33 body + 21x2 hand landmarks, 300-dim |
| 2.3 | YOLOv8n object/PPE detector | Approved | 2026-04-14 | object_detector.py — lazy YOLO load, normalised bbox |
| 2.4 | CNN+LSTM action recognition | Approved | 2026-04-14 | models.py — MobileNetV3-Small + 2-layer LSTM |
| 2.5 | SOP sequence modelling + deviation detector | Approved | 2026-04-14 | sequence_tracker.py + sop_detector.py — 6 deviation classes |
| 2.6 | Accuracy benchmarks (80% / 85% / 75%) | Approved | 2026-04-14 | Test acc=85.8%, val best=93.9%, macro F1=0.875, edge=READY |
| 2.7 | Unit tests (214 tests) | Approved | 2026-04-14 | 214 passed, 3 skipped (mediapipe/ultralytics guards) |
| 2.8 | Model evaluation report | Approved | 2026-04-14 | experiments/eval_report.json |
| 2.9 | Edge model quantisation (INT8) | Todo | | Deferred to Phase 3 |
| 2.10 | Self-supervised pre-training (BYOL) | Todo | | Optional Enhancement 2 |
| 2.11 | **PHASE 2 APPROVAL** | Approved | 2026-04-16 | Researcher approved — proceeded to Phase 3 |

---

## PHASE 3: Real-Time Prototype

| # | Task | Status | Completed | Notes |
|---|------|--------|-----------|-------|
| 3.1 | Live camera capture (OpenCV VideoCapture) | Approved | 2026-04-16 | src/realtime/camera_capture.py — webcam + IP camera |
| 3.2 | Frame -> CV pipeline -> error detection flow | Approved | 2026-04-16 | src/realtime/inference_pipeline.py — end-to-end |
| 3.3 | Error detection -> LLM feedback engine | Approved | 2026-04-16 | src/realtime/session_manager.py — uses Phase 0 LLM Settings |
| 3.4 | WebSocket streaming (FastAPI -> Streamlit) | Approved | 2026-04-16 | src/api/routes/session.py — REST + WebSocket |
| 3.5 | Live Training Streamlit page | Approved | 2026-04-16 | src/ui/pages/live_training_page.py |
| 3.6 | TTS audio feedback | Approved | 2026-04-16 | src/realtime/tts_engine.py — pyttsx3 (offline) |
| 3.7 | Latency benchmarks (< 2s target) | Approved | 2026-04-16 | src/realtime/latency_benchmark.py + experiments/latency_report.json |
| 3.8 | Edge device testing (NVIDIA Jetson) | Todo | | Optional — deferred |
| 3.9 | **PHASE 3 APPROVAL** | Approved | 2026-04-16 | Researcher approved — 35 tests pass, latency benchmark ready |

---

## PHASE 4: Full Integration

| # | Task | Status | Completed | Notes |
|---|------|--------|-----------|-------|
| 4.1 | Analytics dashboard | Approved | 2026-04-16 | src/ui/pages/analytics_page.py — Streamlit + PostgreSQL |
| 4.2 | Session management | Approved | 2026-04-16 | TrainingSessionLog + DeviationLog DB models; auto-persist on stop |
| 4.3 | Worker profile system | Approved | 2026-04-16 | WorkerProfile model + src/api/routes/worker.py + Streamlit page |
| 4.4 | Advanced analytics (time-to-competency) | Approved | 2026-04-16 | src/intelligence/competency_predictor.py — Enhancement 6 |
| 4.5 | Emotion/stress recognition | Approved | 2026-04-16 | src/cv_pipeline/emotion_detector.py — Enhancement 7 (MediaPipe FaceMesh) |
| 4.6 | Continual learning | Approved | 2026-06-09 | src/intelligence/continual_learner.py — Enhancement 5 (EWC). NOTE: prematurely marked done 2026-04-16; code did not exist until implemented 2026-06-09 with EWC + 6 tests (tests/phase4/test_continual_learner.py). Integrity correction. |
| 4.7 | Full OWASP security hardening | Approved | 2026-04-16 | src/api/middleware/security.py — CSP, X-Content-Type, HSTS headers |
| 4.8 | Penetration testing (OWASP ZAP) | Approved | 2026-04-16 | tests/security/owasp_zap_test.py — ZAP passive scan script |
| 4.9 | Load testing | Approved | 2026-04-16 | tests/load/locustfile.py — multi-user concurrent session simulation |
| 4.10 | **PHASE 4 APPROVAL** | Approved | 2026-04-19 | Researcher approved — all Phase 4 tasks complete |

---

## PHASE 4 — UI/UX OVERHAUL (Post-Approval Enhancements, 2026-04-18 to 2026-04-20)

> These tasks were completed after Phase 4 approval as iterative UI improvements required for researcher usability and DBA thesis demonstration quality.

| # | Task | Status | Completed | Notes |
|---|------|--------|-----------|-------|
| 4.11 | Streamlit full UI redesign — gold/dark theme | Approved | 2026-04-18 | app.py — gold (#FFCC00) topbar, dark nav, custom CSS injection |
| 4.12 | Fix Streamlit sidebar nav flash on login/logout | Approved | 2026-04-18 | showSidebarNavigation=false mounted via Docker volume; CSS before auth gate; _sign_out flag pattern |
| 4.13 | Fix SESSION EXPIRED / SIGNED OUT pages showing old sidebar | Approved | 2026-04-18 | CSS injected before st.stop(); early-exit pattern before sidebar renders |
| 4.14 | Local HTTPS — mkcert SSL for Vite + Streamlit | Approved | 2026-04-18 | ssl/ directory; vite.config.ts auto-detect; Docker --server.sslCertFile flags; graceful HTTP fallback |
| 4.15 | Fix "Re-run Setup Wizard" from login page | Approved | 2026-04-18 | forge_force_wizard localStorage flag; redirectByRole honours it after next login |
| 4.16 | Fix Wizard "Launching…" stuck (httpOnly cookie issue) | Approved | 2026-04-19 | Removed hanging refresh call; use current accessToken directly in URL |
| 4.17 | Wizard sidebar logo — remove duplicate, enlarge logo2.jpg | Approved | 2026-04-19 | OnboardingWizard.tsx sidebar logo block |
| 4.18 | SOP Wizard → Live Training handoff | Approved | 2026-04-19 | URL params sop_id + sop_name → Streamlit auth gate → session state → pre-selected SOP + Training Ready banner |
| 4.19 | Live Training — interactive step-by-step session | Approved | 2026-04-20 | Per-step countdown + total elapsed timer; Mark Step Complete; Skip with reason; Safety-critical confirmation checkbox; auto-advance on timeout; Session Summary screen |
| 4.20 | Live Training — offline/manual mode (503 graceful degradation) | Approved | 2026-04-20 | Camera pipeline 503 → generates local UUID session; step-by-step UI still works; yellow Manual Mode banner |
| 4.21 | Wizard full redesign — dark sidebar, SOP hero card | Approved | 2026-04-20 | Dark (#111827) sidebar with gold accents; SOP hero card in Step 2 when selected; Step 3 shows SOP prominently |
| 4.22 | Live Training — Session Setup moved to right-column panel | Approved | 2026-04-20 | Removed from sidebar; two-column idle layout (SOP steps left, Setup card right); gold gradient Start Session button |

---

## PHASE 5: Academic Evaluation

> **UNLOCKED** — Phase 4 approved 2026-04-19.

| # | Task | Status | Completed | Notes |
|---|------|--------|-----------|-------|
| 5.1 | Ethics board approval | Todo | | Ethics board approval |
| 5.2 | Participant recruitment | Todo | | n >= 30 per group (power analysis) |
| 5.3 | Pre-test assessments | Todo | | Baseline measurement |
| 5.4 | Training sessions (both groups) | Todo | | 4-6 weeks |
| 5.5 | Post-test assessments | Todo | | Compare vs baseline |
| 5.6 | Statistical analysis (H1, H2, H3) | Todo | | t-test, Cohen's d, p < 0.05 |
| 5.7 | LLM comparison study | Todo | | Compare Ollama llama3.1:8b (local) vs Groq llama-3.3-70b free vs Gemini flash free — participant-rated feedback quality, zero cost |
| 5.8 | Thesis chapters | Todo | | Literature, methodology, results, discussion |
| 5.9 | Viva preparation | Todo | | DBA viva |

> **Note:** Tasks 5.1–5.5 require **real human participants** and stay **Blocked on ethics approval**. Tasks 5.6 (statistical analysis) and 5.7 (LLM comparison) are **unblocked on synthetic operational data** and have been delivered against it — see the Simulation Evaluation Track below. When ethics approval arrives, the same analysis pipeline re-runs against real-participant data.

### PHASE 5 — Simulation Evaluation Track (synthetic data — no ethics dependency)

> Runs the full statistical evaluation against **synthetic, clearly-labelled** operational data (Rules §3.1: every row tagged `@synthetic.forge.local`). Validates the analysis pipeline and produces the H1/H2/H3 evidence the dashboard/thesis need without real participants. 5.1–5.5 remain ethics-gated.

| # | Task | Status | Completed | Notes |
|---|------|--------|-----------|-------|
| 5S.1 | Synthetic operational-data seeder | Approved | 2026-06-09 | `src/evaluation/seed_simulation_data.py` (+8 tests). Seeded Postgres + Supabase at study scale: 256 workers (64×4 groups), 1,555 sessions, 8,441 deviations. Group learning curves match H1/H2. All rows SYNTHETIC-labelled. |
| 5S.2 | Operational H1/H2 hypothesis tests (synthetic) | Approved | 2026-06-16 | `GET /api/v1/analytics/operational-hypotheses` — per-worker mean deviations by study group → H1 (control vs hybrid) + H2 (sim/realtime/hybrid ANOVA). Verified: H1 control 8.30 vs hybrid 2.80, p≈0, d=−3.41; H2 p≈0, η²=0.27, 3 Tukey pairs. Surfaced in evaluation_page. |
| 5S.3 | H3 paired (within-subjects) test | Approved | 2026-06-16 | `hypothesis_tester.test_h3` → paired t-test (scipy ttest_rel, Cohen's dz, 95% CI of mean diff); `synthetic_participants.generate_paired_feedback`. Assumption checks added (Shapiro-Wilk, Levene, group CIs). |
| 5S.4 | Study-groups analytics + learning curves | Approved | 2026-06-16 | `GET /api/v1/analytics/study-groups` + "📊 Study Groups" tab. Clean H1/H2 story: hybrid 70.4% > realtime 60.4 > sim 49.4 > control 21.6. Severity-weighted scoring (`src/intelligence/scoring.py`). |
| 5S.5 | LLM comparison study (5.7 synthetic variant) | Approved | 2026-06-09 | Seeded sessions spread across groq/gemini/ollama providers for participant-rated-quality comparison; live Groq (llama-3.3-70b-versatile) wired for real feedback generation. |
| 5S.6 | Bias audit (per-department fairness) | Approved | 2026-06-17 | Realistic departments + one injected disparity (Welding 1.5×); `bias-audit` returns cohort mean + relative flag threshold. Verified: Welding 33.0 FLAGGED vs cohort 43.3. |
| 5S.7 | Emotion & stress analytics | Approved | 2026-06-16 | Seeded `emotion_*` rows (group-tied) + live `EmotionDetector` (FaceMesh) wiring in WS camera; emotion-summary endpoint. Kept separate from deviation analytics. |

**Phase 5 model evaluation targets** (gated during academic validation — defined in config/train_config.yaml):
- Overall accuracy >= 0.80 (already met: 0.858)
- Macro F1 >= 0.80 (already met: 0.875) — equal weight to all 5 scenario classes
- Top-3 accuracy = 1.00 (already met: 1.000) — correct class always in top-3 (5-class problem)

---

## Approval Log

| Date | Phase | Approved By | Notes |
|------|-------|------------|-------|
| 2026-04-07 | Phase 0 docs (0.1–0.8) | Researcher | Documentation approved |
| 2026-04-08 | Phase 0 code + UI (0.9–0.19) | Researcher | Docker confirmed UP, LLM settings + React auth functional |
| 2026-04-12 | Phase 1 | Researcher | Simulation pipeline + 1,200 synthetic clips |
| 2026-04-14 | Phase 2 | Pending | All benchmarks met — awaiting researcher sign-off |
| 2026-04-16 | Phase 2 | Researcher | Approved — test acc 0.858, macro F1 0.875, edge READY |
| 2026-04-16 | Phase 3 | Researcher | Approved — 35 tests pass, end-to-end pipeline functional |
| 2026-04-19 | Phase 4 | Researcher | Approved — 74 tests pass, full integration complete |

## PHASE 4 — UI/UX Polish & Bug Fixes (2026-04-21 to 2026-04-23)

> Continued post-approval UI hardening, security fixes, and dashboard improvements.

| # | Task | Status | Completed | Notes |
|---|------|--------|-----------|-------|
| 4.23 | RBAC — My Account page server-side enforcement | Approved | 2026-04-20 | API `_resolve_target()` enforces self-only for non-admins; JWT `Depends(get_current_user)` on all 4 account endpoints |
| 4.24 | RBAC — Topbar role-switcher restricted to Admin only | Approved | 2026-04-20 | Non-admins see plain role text; page-access guard redirects to dashboard if forbidden page in session state |
| 4.25 | Date/time format standardised across all pages | Approved | 2026-04-20 | `src/ui/utils.py` — `fmt_date()` (DD/MM/YYYY) and `fmt_datetime()` (DD/MM/YYYY HH:MM:SS); applied to 10 pages |
| 4.26 | Account Lookup moved to right panel (Admin only) | Approved | 2026-04-20 | Two-column layout col[3,1]; non-admins see full-width own profile |
| 4.27 | Dashboard auth banner removed | Approved | 2026-04-21 | Removed from dashboard_page.py and help_page.py entirely |
| 4.28 | Help page moved to topbar (all roles) | Approved | 2026-04-21 | Help button in topbar next to Sign Out; removed from all sidebar NAVIGATION entries |
| 4.29 | Dashboard Worker column — shows full name instead of empty | Approved | 2026-04-21 | analytics.py sessions endpoint LEFT JOIN users → `worker_name` field; stop session passes `?worker_id=` |
| 4.30 | Camera source persisted in session state | Approved | 2026-04-21 | `lt_last_camera_source` key; text input uses saved value as default |
| 4.31 | Sidebar tree navigation with animated groups | Approved | 2026-04-23 | `NAV_GROUPS` replaces flat `NAVIGATION`; `st.expander` per group; CSS slide-in animation; gold tree-line; Dashboard pinned at top |

---

## Current System State — 2026-04-23

**All phases 0–4 are COMPLETE and APPROVED.  
Phase 5 (Academic Evaluation) is UNLOCKED and waiting to begin.**

### What is running right now

| Service | URL | Status |
|---------|-----|--------|
| React Frontend (Vite) | https://localhost:5173 | ✅ Running (manual `npm run dev`) |
| FastAPI Backend | http://localhost:8000 | ✅ Running (Docker) |
| Streamlit Dashboard | http://localhost:8501 | ✅ Running (Docker) |
| PostgreSQL | localhost:5433 | ✅ Running (Docker) |

### Streamlit Dashboard — current capabilities

**Navigation:**
- Tree-style sidebar with animated expand/collapse groups
- Dashboard pinned at top; groups: Training · Data & Analytics · Administration · Account
- Help button in topbar (all roles); role-switcher in topbar (Admin only)

**Live Training page:**
- Idle: Two-column layout — SOP steps preview + Session Setup card
- Active: Step-by-step guided flow — progress bar, dual timers, step card, Mark Complete / Skip / Safety-critical confirmation
- Manual mode: graceful degradation if camera unavailable (503)
- Session Summary: per-step table, AI deviation log, score %, Start New Session
- Camera source remembered across reruns (`lt_last_camera_source`)

**My Account page:**
- Workers/Trainers/Supervisors: own account only (RBAC enforced server + client)
- Admin: Account Lookup panel (right column) can view/edit any user

**Dashboard:**
- Recent Sessions table: Worker column shows full name (API JOIN with users table)
- Live Activity Feed: worker name displayed

**Camera source options:**

| Source | How |
|--------|-----|
| Built-in webcam | Enter `0` in Camera Source field |
| Mobile phone (Android — IP Webcam app) | Enter `http://192.168.x.x:8080` |
| IP / RTSP camera | Paste full URL |

### Next actions for Phase 5

1. Ethics board approval (task 5.1)
2. Participant recruitment — minimum n=30 per group (task 5.2)
3. Pre-test baseline assessments (task 5.3)
4. Controlled training sessions — 4–6 weeks (task 5.4)
5. Statistical analysis H1/H2/H3 — t-test, p < 0.05 (task 5.6)
6. LLM comparison study — Groq vs Gemini vs Ollama local (task 5.7)
7. Thesis chapters (task 5.8)

---

## Session Log — 2026-06-09 (Review, Integrity Fixes & Documentation)

A four-stream review (research-intent recap, architecture, built-application, code review) was run and cross-verified. Actions taken this session:

| # | Item | Detail |
|---|------|--------|
| S.1 | **Continual Learning (E5) implemented + wired into app** | `src/intelligence/continual_learner.py` (EWC algorithm, 6 tests) + `src/intelligence/continual_learning_service.py` (orchestration, 3 tests) + `src/api/routes/continual.py` (admin endpoints: POST /run background job, GET /runs) + admin panel in `evaluation_page.py`. Corrects the premature 2026-04-16 "done" claim. Verified end-to-end against the real trained model + synthetic clips (100% knowledge retention). `docker-compose.yml` api now mounts `./experiments` for run-record/checkpoint persistence. |
| S.2 | **Synthetic data seeder** | `src/evaluation/seed_simulation_data.py` (+8 tests). Seeded Postgres at study scale: 256 workers, 1,555 sessions, 8,441 deviations — populates the dashboard/analytics without ethics-gated real participants. All rows tagged SYNTHETIC (Rules §3.1). |
| S.3 | **Stale SOP tests fixed** | `tests/simulation/test_sop_parser.py` — fire-evacuation (7→8 steps, category Emergency Procedures) and lab-safety (6→8 steps) assertions updated after the May-06 SOP-library expansion. |
| S.4 | **Coverage measured** | `pytest-cov`: 427 passed, 3 skipped, 0 failed. Core algorithmic modules **87%** (≥80% target met); whole-`src/` 34% (UI pages + CLI entrypoints excluded). HTML report in `experiments/coverage/`. Rules.md §5.4 updated with measured figures. |
| S.5 | **Runtime fix** | `forgevision_api` (down 4 weeks) restarted; host port remapped `8000→8010` in `docker-compose.yml` to avoid clash with another local project. UI→API→Postgres chain verified. |
| S.6 | **Thesis documentation** | System Implementation Report (15–25k words), report figures, and Mermaid diagrams — see `SystemImplementationReport.md`, `report/figures/`, `Mermaid`. |

**Backlog (deferred, documented):** auth-enforcement tests, `crypto.py` tests, DB-migration tests, Streamlit type hints, real SMTP email, `ui/utils.py` error handling, INT8 quantisation (2.9), BYOL pre-training (2.10), Jetson edge testing (3.8); git baseline + `thesis-v1.0` tag pending repo init.

---

## Session Log — 2026-06-10 to 2026-06-23 (Free Cloud Demo + Evaluation/UI Upgrades)

A free, fully-online demo of FORGE-Vision was built and deployed, and the analytics/evaluation surfaces were upgraded to doctoral standard. No phase gate changed — this is post-Phase-4 hardening plus the Simulation Evaluation Track delivery.

| # | Item | Detail |
|---|------|--------|
| C.1 | **Live cloud demo deployed** | **https://huggingface.co/spaces/MashkurA/forge-vision** (HF Docker Space, free CPU tier) + **Supabase** free Postgres (seeded). Login `mashkur.alam@hotmail.co.uk`. Full app online for $0: dashboard, analytics, SOPs, reports, settings, evaluation. |
| C.2 | **Live browser-webcam camera (WebSocket)** | Browser webcam → JPEG over WebSocket → FastAPI → `RealtimeFramePipeline` → annotated frame (pose skeleton + YOLO overlay) + deviation + Groq feedback back. New: `src/api/routes/live_ws.py`, `src/ui/ws_camera.py`, `space/Caddyfile` (single-port routing). **WebRTC was abandoned** (streamlit-webrtc/aiortc event-loop tore down every TURN transport mid-session despite 4 working TURNs in isolation) — see cleanup note below. |
| C.3 | **Groq LLM live** | `LLMSettings` row (provider=groq, model llama-3.3-70b-versatile) written + verified — real coaching feedback, not the rule-based fallback. |
| C.4 | **Analytics / Reports / Leaderboard upgrade** | Severity-weighted `session_accuracy` (`src/intelligence/scoring.py`); deviation breakdown (class×severity) in reports + PDF; study-groups endpoint; shared metric across leaderboard/reports/analytics. |
| C.5 | **Evaluation page rigour** | Paired H3, Shapiro-Wilk/Levene assumption checks + CIs, operational-hypotheses endpoint (H1/H2 on synthetic data). See Simulation Evaluation Track 5S.2–5S.3. |
| C.6 | **Bias audit + Emotion/stress** | Per-department fairness with relative-to-cohort flagging (5S.6); emotion analytics seeded + live-wired (5S.7). |
| C.7 | **Mobile-responsive UI** | `src/ui/app.py` global media queries, off-canvas sidebar drawer, topbar reflow, native-login mobile fix; full per-page audit (fixed a real nested-expander crash in `evaluation_page.py`). |
| C.8 | **Test suite** | Grew to **501 passed** across the above (scoring, study-groups, operational endpoint, paired H3, assumptions, bias-audit, emotion-summary). |

**Deploy note:** Space updates ship via `hf_space_build/` (assembled repo, tokenised `space` remote) — `cp` changed files + `git push space main`; Dockerfile changes require editing both `Dockerfile.hf` and `hf_space_build/Dockerfile`.

**Outstanding (carried):** (1) **rotate exposed secrets** — HF write token, Twilio Auth Token, Groq key, Supabase DB password; (2) **deploy-readiness (Deliverable 2)** — `docker-compose.prod.yml`, `.env.production.example`, prod Caddyfile, wire seeder `--if-empty` into prod startup.

### Cleanup — 2026-06-24 (vestigial WebRTC/coturn removed)

The local WebRTC path was abandoned (the cloud demo uses WebSocket). Removed the dead code/config: `src/ui/webrtc_live.py`, `scripts/run_host_ui.py`, `scripts/_smoke_pipeline.py`, `scripts/_create_test_admin.py`, `coturn_oracle_setup.md`; dropped the `coturn` service + `TURN_*` env from `docker-compose.yml`, the `TURN_*` block from `.env`, and `streamlit-webrtc` from `requirements-web.txt`; corrected docstrings that referenced the deleted module; removed the exited `forge-space-test` container.

---

## Session Log — 2026-11-06 (Cloud redeploy after Supabase free-tier deletion)

The free Supabase project was deleted after its pause window expired; the HF Space survived (sleeping). Redeployed on a new Supabase project (`forge-vision`, eu-central-1) and re-seeded.

| # | Item | Detail |
|---|------|--------|
| R.1 | **New Supabase + Space secrets** | New project, session-pooler `DATABASE_URL`, regenerated `SETTINGS_ENCRYPTION_KEY` / `JWT_SECRET_KEY`, `ALLOWED_HOSTS=*`, one-time `SEED_ON_START=1`. Migrations + seeding ran on first boot. LLM keys must be re-entered (old encrypted keys are unreadable). |
| R.2 | **Admin account** | `/auth/register` always creates `staff`; promoted via SQL (`UPDATE users SET role='admin' …`). DEPLOYMENT.md §A.4 was wrong and is corrected. |
| R.3 | **LLM provider updates** | Groq's Llama 3.x / Mixtral / Gemma models are no longer available to the key; dropdown + `GroqProvider` moved to `openai/gpt-oss-20b` (also gpt-oss-120b, qwen3.8-27b). `GeminiProvider` moved to Google's OpenAI-compatible endpoint with `gemini-2.5-flash-lite` default. Both caps raised to 600 tokens with an empty-reply guard (reasoning models can otherwise return no visible text). Groq and Gemini verified connected. |
| R.4 | **Keep-alive** | Private repo `forge-vision-keepalive`: GitHub Action pings `/health` every 12 h (each call writes an `audit_logs` row) so Space and Supabase stay active. |
| R.5 | **Re-seeded data counts (integrity note)** | New database: 260 users, 1,555 sessions, **9,303 deviations** + 4,665 `emotion_*` rows (13,968 rows in `deviation_logs`). The 2026-06-09 seeding recorded **8,441 deviations**. Sessions match; the deviation total differs, so the dataset is not identical to the one behind earlier results. Figures in the thesis report (e.g. `generate_report_figures.py` title "n=8,441") were produced from the earlier dataset — **re-run the analysis and regenerate figures against the current database, or state which dataset each figure used, before quoting.** **Cause (investigated 2026-11-06):** the seeder is deterministic (a DB-free replication reproduces the live database exactly: 9,303 deviations, 4,665 emotion rows, 1,555 sessions). The gap is the **Welding ×1.5 deviation multiplier** added for the bias audit on 2026-06-17 (task 5S.6), after the 2026-06-09 seeding. With the multiplier set to 1.0 the same seed gives 8,450 (9 above the recorded 8,441; that residual comes from seeder/SOP edits between 06-09 and 06-17 that the available history cannot isolate). The 2026-06-25 SOP edits do not change the totals. The H1/H2 operational-hypothesis values recorded on 2026-06-16 (5S.2) were computed before the multiplier, so **re-run `GET /api/v1/analytics/operational-hypotheses` and regenerate report figures against the current database** before quoting them. |

**Outstanding:** set `SEED_ON_START=0`; revoke the Hugging Face tokens exposed during this session and clear cached credentials; OpenAI provider not set up (needs a card; `OpenAIProvider` still uses `max_tokens=120`).
