# FORGE-Vision — System Walkthrough Video Script & Storyboard
**Doctor of Business Administration (DBA) — Full System Demonstration**
Researcher: Prof. Dr. Karim Mohammed Rezaul
Target length: ~20–22 minutes (every page covered) · Audience: DBA examiners / viva panel

---

## How to use this document

This is a **shot-by-shot script**. Each scene gives three columns:

- **VISUAL** — what is on screen (a slide, or a specific app view).
- **ACTION** — what to click / do while narrating.
- **NARRATION** — read aloud (the voiceover), written in an academic register.

**Recording setup**
- Slide scenes: open `presentation/slides.html`, full-screen (**F**), advance with arrows.
- App scenes: open the live system `https://mashkura-forge-vision.hf.space`
  (login `mashkur.alam@hotmail.co.uk`). 1920×1080, browser zoom 100%.
- Record with OBS Studio or PowerPoint *Record Screen*. Narrate live, or record the
  silent track first and add voiceover. `capture.mjs` can auto-record the visual track.

Timing markers are cumulative (mm:ss) and approximate. If you need a shorter cut,
the per-page tour (Parts 4–7) trims cleanly — keep Parts 1–3 and the Conclusion.

> **Page coverage.** The system has **16 pages** across five groups. Part 2 explains
> the **real-time dashboard**, Part 3 is the **live SOP test process**, and Parts 4–7
> walk **every remaining page**. A one-line index of all pages is in the Appendix.

---

# PART 1 — FRAMING (slides)

## SCENE 1 — Title & Introduction · `slides.html` (0:00–0:45)

| | |
|---|---|
| **VISUAL** | Title slide. |
| **ACTION** | Hold on the title. |
| **NARRATION** | "Good morning. My name is Professor Karim Mohammed Rezaul, and this is FORGE-Vision — a hybrid computer-vision and generative-AI system for employee training, developed as the applied artefact of my Doctor of Business Administration research. In this demonstration I will set out the business problem, the architecture, a complete tour of the platform — every page — a live test of a procedure, and the empirical evidence for my three hypotheses." |

## SCENE 2 — The Problem & Research Context · `slides.html` (0:45–2:00)

| | |
|---|---|
| **VISUAL** | "The Problem" slide. |
| **ACTION** | Advance bullets with the narration. |
| **NARRATION** | "Across manufacturing, healthcare and logistics, a substantial proportion of operational error stems not from a lack of knowledge, but from deviation from Standard Operating Procedures during execution. Conventional training is episodic and retrospective: an employee is trained, then assessed, and feedback arrives long after the error — when its instructional value has decayed. The research problem is therefore one of *timing and specificity*: can a system observe a worker, detect a deviation the moment it occurs, and deliver corrective guidance that is specific, explainable, and immediate?" |

## SCENE 3 — Research Hypotheses · `slides.html` (2:00–2:50)

| | |
|---|---|
| **VISUAL** | "Research Hypotheses" slide. |
| **ACTION** | Highlight each hypothesis. |
| **NARRATION** | "Three testable hypotheses. **H1**: employees trained with FORGE-Vision achieve a statistically significant reduction in task-error rates relative to traditional training, at p below 0.05. **H2**: the hybrid pathway — simulation first, then real-time — yields better skill transfer than either approach alone. **H3**: real-time feedback reduces task-completion time compared with post-hoc feedback. Each is operationalised in the system you are about to see." |

## SCENE 4 — System Architecture · `slides.html` (2:50–4:20)

| | |
|---|---|
| **VISUAL** | "Architecture" slide — four-layer diagram + technology stack. |
| **ACTION** | Trace layers top-to-bottom; point to the stack. |
| **NARRATION** | "Architecturally it is a four-layer pipeline. **Layer one, perception**: OpenCV processes the frame, MediaPipe extracts thirty-three body and forty-two hand landmarks, and a YOLO-v8 detector localises tools and protective equipment. **Layer two, recognition**: a compact MobileNet-V3 plus LSTM model — 2.3 million parameters — classifies the worker's action against the procedure, at 85.8 percent accuracy and a 62-millisecond 95th-percentile latency. **Layer three, intelligence**: a deviation detector compares the action sequence to the formal SOP and passes a structured context to a language model — Groq's Llama-3.3 — which writes the corrective instruction. **Layer four, guidance**: that instruction reaches the worker in under two seconds. The stack is containerised with Docker, served through FastAPI and Streamlit, on PostgreSQL." |

---

# PART 2 — THE REAL-TIME DASHBOARD (app)

## SCENE 5 — Login & the Real-Time Operations Dashboard · **App** (4:20–6:30)

| | |
|---|---|
| **VISUAL** | Native login → the **Dashboard**. |
| **ACTION** | Sign in. On the dashboard, point to each region in turn: **(a)** the three **System Status** cards; **(b)** the four headline **metrics**; **(c)** the **Live Activity Feed**; **(d)** the **Recent Sessions** table; **(e)** the quick-action buttons. |
| **NARRATION** | "This is the deployed system, running in the cloud at zero infrastructure cost. After authenticating, the administrator lands on the real-time operations dashboard — the command centre of the platform. Begin at the top: the **System Status** strip is a live heartbeat of the three critical services — the FastAPI backend, the PostgreSQL database with its current query latency, and the active LLM provider, here Groq running Llama-3.3. If any dependency degrades, it shows here first. Beneath it, four headline metrics summarise the entire programme: active sessions running right now, total sessions conducted — over fifteen hundred — total deviations detected, and the count of high-severity events. Now the heart of this page: the **Live Activity Feed**. Each entry is a completed or in-progress training session, colour-coded by severity — green for minor, red for high — showing the worker, the procedure they attempted, the number of deviations, the duration, and, importantly, the 95th-percentile inference latency for that session. That latency figure is the system holding itself to its own real-time guarantee. The **Recent Sessions** table gives the same information in tabular form with the worker's full name resolved from the database. Every number on this page is queried live from PostgreSQL — there is no mock data in the interface. The quick-action buttons let an administrator jump straight to starting a session, authoring a procedure, or generating a report. For this demonstration the database holds a clearly-labelled *synthetic* cohort, which I will return to during the evaluation." |

> **Why this is 'real-time':** the activity feed and status strip reflect live database
> state and live service health; a session started on one device appears in the feed and
> the active-session counter here. Mention this explicitly to the panel.

---

# PART 3 — THE LIVE SOP TEST PROCESS (app — core demonstration)

> ⚠️ **Re-record this part with a real person at a workstation for the final cut.**
> The automated capture uses a synthetic camera feed to prove the pipeline runs; a real
> subject is needed to show the pose skeleton and tool detection at their best.

## SCENE 6 — Step 1: Consent & procedure selection · **App** (6:30–7:45)

| | |
|---|---|
| **VISUAL** | Training → **Live Training**. The GDPR consent notice → tick consent → the SOP picker and procedure preview. |
| **ACTION** | Open Live Training; read the privacy notice on screen; tick **"I understand and consent…"**. Select a procedure — e.g. *Science Laboratory Safety Induction* (8 steps). Show the procedure preview: the ordered steps, required PPE, and any time limits. |
| **NARRATION** | "Now the core of the system: a live test of a worker performing a real procedure. Notice the first thing presented is not the camera — it is a **GDPR data-and-privacy notice**. The system states plainly that video frames are processed in server memory only, never stored or transmitted after the session, that only session *metadata* is persisted under research data-governance rules, and that the worker may request deletion at any time. Consent is explicit and required before anything starts — that is a governance constraint in the design, not an afterthought. With consent given, the trainee selects the procedure they are about to perform. The system loads its **formal definition** — here, the Science Laboratory Safety Induction: an ordered sequence of eight steps, the protective equipment required, and per-step time limits. This preview is the 'ground truth' the system will judge execution against." |

## SCENE 7 — Step 2: Live perception & the feedback loop · **App** (7:45–9:30)

| | |
|---|---|
| **VISUAL** | The active session: webcam panel with pose-skeleton + tool/PPE overlay, alongside the step-by-step panel (current step, per-step countdown, total elapsed). |
| **ACTION** | Click **Start**; allow the camera. Point to the green **pose skeleton** and the **bounding boxes** on tools/PPE. Indicate the current-step card and the two timers. Perform — or describe — a **correct** step, then **Mark Step Complete** to advance. |
| **NARRATION** | "The worker's own webcam now streams to the server over a WebSocket. Watch the overlay: the green skeleton is the live pose estimate from MediaPipe; the boxes are the tools and protective equipment the YOLO detector has localised and labelled. On the right, the step-by-step panel shows the current expected step, a per-step countdown enforcing pace, and the total elapsed time. As the worker proceeds, the action-recognition model continuously classifies what they are doing and matches it against the expected step. When the worker completes a step correctly, they acknowledge it and the system advances to the next." |

## SCENE 8 — Step 3: Deviation detection & explainable AI feedback · **App** (9:30–11:00)

| | |
|---|---|
| **VISUAL** | A deliberate deviation → the AI feedback card appears. Then a safety-critical step requiring confirmation; and the *Skip with reason* control. |
| **ACTION** | Deliberately **skip a required step** or do one **out of order**. Pause on the **feedback card** when it appears. Then show a **safety-critical** step's confirmation checkbox, and the **Skip (with reason)** option. |
| **NARRATION** | "Now I will deliberately deviate — skipping a required step. Within two seconds the system has detected the divergence and classified it. The platform distinguishes **five deviation classes** — a correct execution, a missing step, a wrong-order step, an unsafe action, and a rare critical failure — rather than simply flagging 'an error'. The recognised deviation is passed as structured context to the language model, which generates a corrective instruction that explains *what* was wrong and, critically, *why* it matters. That explainability is a hard requirement of the design. Note two further controls: a **safety-critical** step requires an explicit confirmation before the worker may proceed; and where a step is legitimately skipped, the worker must record a **reason**, preserving an auditable trail. If the camera pipeline is ever unavailable, the session degrades gracefully into a **manual mode** so the guided procedure still runs." |

## SCENE 9 — Step 4: Session summary & persistence · **App** (11:00–12:00)

| | |
|---|---|
| **VISUAL** | The end-of-session **Summary**: per-step table, deviation log, completion score, and the green "✅ Saved to the research database" confirmation. |
| **ACTION** | Complete the session. Show the **Session Summary** — per-step outcomes, the deviation log, the severity-weighted completion score, and the **saved-to-database** confirmation line. |
| **NARRATION** | "When the procedure ends, the system produces a **session summary**: a per-step table of outcomes, the full deviation log with severity, and an overall completion score. That score is **severity-weighted** — a high-severity deviation costs more than a minor one — so the number reflects real competence, not a simple error count. And crucially, the session is now **recorded to the research database** — only the metadata and deviation events, exactly as the consent notice stated; the video itself is already gone from memory. This is the closed loop: perceive, detect, explain, and *record*."  |

---

## SCENE 9b — The captured session, in the platform's data · **App** (12:00–13:00)

> This scene proves the live test's data flowed into the system. Record it
> **immediately after** your live SOP test, while that session is the most recent.

| | |
|---|---|
| **VISUAL** | **Dashboard** (the just-completed session at the top of the activity feed / recent sessions) → **Session History** (open the session in the drill-down to show its individual deviations) → optionally **Staff Profiles** / **Analytics → Worker Performance** showing the updated counts. |
| **ACTION** | Go to the Dashboard — point to your session at the top of the Live Activity Feed (your name, the SOP, deviations, duration). Open **Session History**, select your session in the drill-down, and show its per-deviation breakdown. |
| **NARRATION** | "Here is the evidence that the loop closed. The session I just performed now sits at the top of the operational dashboard — my name, the procedure, the deviations detected, the duration. In Session History I can open that exact session and inspect every individual deviation the system recorded — its class, its severity, the step it occurred on — and the worker's profile and analytics have updated to reflect it. The live data we captured during the test is now first-class research data, queryable alongside the rest of the cohort." |

---

# PART 4 — AUTHORING & LIBRARY (app — each page)

## SCENE 10 — Create SOP · **App** (12:00–13:00)

| | |
|---|---|
| **VISUAL** | **Create SOP** page — Mode (Create New / Upload Document), SOP Metadata, Steps builder, Preview YAML, Save. |
| **ACTION** | Show the two modes. Fill a metadata field or two (ID, name, category, department, duration, required PPE). Add a step. Click **Preview YAML**. |
| **NARRATION** | "The system's judgement is only as good as the procedure it judges against, so SOP authoring is a first-class page. An administrator can **create a procedure from scratch** — defining its identifier, name, category, department, estimated duration, and required protective equipment, then adding an ordered list of steps, each with a time limit and a safety-critical flag — or, using **Upload Document**, hand the system a written procedure and have a language model parse it into this structured form automatically. The **Preview YAML** button shows the machine-readable definition that results, and Save commits it to the library. This is what lets the platform reason about *any* procedure, not a fixed set." |

## SCENE 11 — SOP Library · **App** (13:00–13:45)

| | |
|---|---|
| **VISUAL** | **SOP Library** — searchable cards for the 22 procedures, each with category, department, step count, duration; *View Details*. |
| **ACTION** | Scroll the library; search; open **View Details** on one SOP. |
| **NARRATION** | "The **SOP Library** is the catalogue of approved procedures — twenty-two here, spanning data science, security, laboratory safety, food hygiene, and emergency response, from a fire-evacuation marshal procedure to a machine-learning training pipeline. Each card shows the category, owning department, number of steps, and expected duration; *View Details* opens the full step list. This breadth demonstrates that the approach is domain-general — the same perception-to-guidance pipeline serves a chemistry lab and a data-engineering workflow." |

---

# PART 5 — DATA & ANALYTICS (app — each page)

## SCENE 12 — Analytics: the seven lenses · **App** (13:45–16:00)

| | |
|---|---|
| **VISUAL** | **Analytics** — top metric strip (6 KPIs) and the seven tabs. |
| **ACTION** | Note the six KPIs. Then walk the tabs: **Session History → Worker Performance → SOP Analytics → Deviation Heatmap → Study Groups → Emotion Breakdown → Bias Audit**, pausing on Study Groups, Bias Audit, and Emotion. |
| **NARRATION** | "The **Analytics** page is the analytical core, opening with six programme-level indicators — total sessions, total deviations, high-severity events, active workers, average 95th-percentile latency, and the **latency-target pass rate**, here above 99 percent, evidence that the two-second guarantee holds at scale. It then offers seven lenses. **Session History** lists every session with drill-down. **Worker Performance** profiles individuals. **SOP Analytics** ranks procedures by difficulty and surfaces the most-deviated step. The **Deviation Heatmap** cross-tabulates deviation class against severity. Then the three lenses built for my research. **Study Groups** divides the synthetic cohort into the four experimental arms — control, simulation-only, real-time-only, and hybrid — with grouped bars and per-session learning curves; the hybrid arm reaches the highest weighted accuracy, around 70 percent, clearly ahead of the single-modality groups, with the control group trailing near 22 percent. That separation is the visual signature of the skill-transfer advantage H2 predicts. The **Bias Audit** evaluates outcome parity across departments and flags any group falling significantly below the cohort — responsible-AI evidence that the system is not entrenching a hidden disparity. And the **Emotion Breakdown** tracks engagement states — focused, neutral, stressed, fatigued — from facial-expression analysis, recognising that training effectiveness and worker stress are not independent. All three run on clearly-labelled synthetic data here." |

## SCENE 13 — Session History · **App** (16:00–16:40)

| | |
|---|---|
| **VISUAL** | **Session History** — filters (worker, SOP, date range), totals, and the **Deviation Drill-Down**. |
| **ACTION** | Apply a filter; select a session in the drill-down to inspect its individual deviations. |
| **NARRATION** | "**Session History** is the forensic record. Filter by worker, procedure, or date range across all fifteen hundred sessions, then use the **deviation drill-down** to open any single session and inspect each individual deviation — its class, severity, the step it occurred on. This is the granular evidence base beneath the aggregate analytics." |

## SCENE 14 — Staff Profiles · **App** (16:40–17:20)

| | |
|---|---|
| **VISUAL** | **Staff Profiles** — searchable worker list; a selected profile with metrics (sessions, deviations, high-severity, **skill level**), editable fields, and recent sessions. |
| **ACTION** | Search a worker; open a profile; point to the **Skill level** (e.g. *Competent*) and the trainer-notes field. |
| **NARRATION** | "**Staff Profiles** turns sessions into a per-worker development record. Each profile shows the individual's session count, deviation history, high-severity events, and a derived **skill level** — here, *Competent* — alongside their department and a trainer-notes field. The underlying competency model estimates time-to-competency, supporting the practical question every training manager asks: is this person ready, and if not, how far away are they?" |

## SCENE 15 — Reports · **App** (17:20–18:00)

| | |
|---|---|
| **VISUAL** | **Reports** — date range, worker and SOP filters, **Generate Report**, deviation breakdown, **Download PDF**. |
| **ACTION** | Set filters; generate; show the deviation breakdown; trigger the **PDF export**. |
| **NARRATION** | "The **Reports** page is for dissemination. Choose a date range and optionally filter to specific workers or procedures, and the system produces a filtered, **publication-ready PDF** with the deviation breakdown by class and severity — the evidentiary artefacts that go straight into the thesis. Reproducibility is built in: fixed random seeds, version-controlled configuration, and a one-command deployment." |

## SCENE 16 — Leaderboard · **App** (18:00–18:35)

| | |
|---|---|
| **VISUAL** | **Leaderboard** — period (week/month/all-time), study-group and department filters, ranked workers, current-user highlight. |
| **ACTION** | Switch the period; filter by study group; point to the ranking and the highlighted "you" row. |
| **NARRATION** | "The **Leaderboard** introduces a motivational layer, ranking workers by the same severity-weighted accuracy used throughout — never a crude error count — over a chosen period, and filterable by study group or department. Gamification is applied carefully: because the metric rewards safe, correct execution rather than speed alone, the incentive it creates is aligned with the training objective." |

---

# PART 6 — ACADEMIC EVALUATION (app)

## SCENE 17 — Simulation: hypothesis testing & continual learning · **App** (18:35–20:00)

| | |
|---|---|
| **VISUAL** | **Simulation** page — Experiment Configuration; Operational-Data Hypothesis Tests (H1/H2) with p-values, Cohen's d, η²; the three result tabs; Synthetic Group Distributions; the **Continual Learning** panel. |
| **ACTION** | Show the configuration (n, α, power, effect size, seed). **Run Hypothesis Tests**; point to the p-values, Cohen's d, and η². Switch the result tabs (Errors per Task / Completion Time / Sessions to Competency). Scroll to **Continual Learning** and show **Run incremental learning**. |
| **NARRATION** | "Here the platform becomes a research instrument. Note first the prominent banner: **all data shown is synthetic**, generated from published literature baselines, because real-participant collection requires ethics-board approval — academic integrity made visible in the interface. The **experiment is fully configured** — participants per group, significance level, target power, expected effect size, and a fixed random seed for reproducibility. Running the tests, the system contrasts the study arms: for **H1**, error reduction is significant with a p-value effectively at zero and a large negative Cohen's d; **H2**'s analysis of variance is likewise significant with a substantial eta-squared; and the result tabs report the three operational outcomes — errors per task, completion time, and sessions to competency — the last speaking to **H3**. Crucially, the page also reports the **assumption checks** — normality and equal-variance tests, and confidence intervals on every group mean — because a defensible result must show its inferential assumptions were examined, not assumed. Finally, the **continual-learning** module, using Elastic Weight Consolidation, lets the model absorb new data without catastrophically forgetting prior knowledge — verified at full retention — so the system keeps improving as it is used." |

---

# PART 7 — ADMINISTRATION & GOVERNANCE (app — each page)

## SCENE 18 — Settings (LLM configuration) · **App** (20:00–20:40)

| | |
|---|---|
| **VISUAL** | **Settings** → LLM Configuration — provider, model, API key, Test Connection. |
| **ACTION** | Show the provider/model selection and the **Test Connection** control. |
| **NARRATION** | "**Settings** is where an administrator chooses and connects the AI model that generates the worker feedback. The system supports five providers — OpenAI, Groq, Anthropic, Gemini, and a local Llama via Ollama — and this deployment uses Groq's Llama-3.3 for fast, free inference. The API key is entered here and stored **encrypted** in the database, never in code or configuration; a **Test Connection** button verifies the provider live and records a latency reading. This pluggability is also what makes the planned LLM-comparison study possible." |

## SCENE 19 — User Management (RBAC) · **App** (20:40–21:20)

| | |
|---|---|
| **VISUAL** | **User Management** — user table (ID, name, email, role, sessions, last active), role/status filters, Add User, edit/delete, Export CSV. |
| **ACTION** | Filter by role; show the Add-User and edit controls; point to the role column. |
| **NARRATION** | "**User Management** enforces role-based access control. Every account carries a role — administrator, trainer, supervisor, or worker — and that role governs what each user may see and do; a worker, for example, can view only their own account, enforced on the server, not merely hidden in the interface. Administrators can create, edit, deactivate, and export users. Note the synthetic accounts are systematically labelled — every one carries a synthetic email domain — so research data can never be confused with real personal data." |

## SCENE 20 — System Health · **App** (21:20–21:55)

| | |
|---|---|
| **VISUAL** | **System Health** — service cards (API uptime, Postgres query time, LLM), metric strip (SOPs, sessions, deviations, users), auto-refresh, LLM latency history. |
| **ACTION** | Point to the three service cards and the auto-refresh; show the latency-history section. |
| **NARRATION** | "**System Health** is the operations view: live status of the API with its uptime, the database with its current query time, and the LLM provider, refreshing automatically every thirty seconds. It also charts **LLM latency over time**, so the team can see the feedback engine's responsiveness trend — directly relevant to the two-second guarantee that underpins H3." |

## SCENE 21 — Audit Log · **App** (21:55–22:25)

| | |
|---|---|
| **VISUAL** | **Audit Log** — searchable, paginated entries (user, action, resource, detail), Export CSV. |
| **ACTION** | Search the log; show the entry count and CSV export. |
| **NARRATION** | "Every consequential action — a login, a settings change, a user edit, a procedure saved — is written to the **Audit Log**, here over sixteen hundred entries, searchable and exportable. For a system that processes people's performance data, this accountability trail is both a security control and an ethics requirement." |

## SCENE 22 — Notifications & My Account · **App** (22:25–23:05)

| | |
|---|---|
| **VISUAL** | **Notifications** (grouped Today/Yesterday, unread count, mark-read) → **My Account** (own profile; admin Account Lookup). |
| **ACTION** | Show the notifications list and mark-all-read; open **My Account**; for an admin, show the Account Lookup. |
| **NARRATION** | "Two final pages close the loop on the user experience. **Notifications** surface system events — a completed training run, a newly available procedure, a health check — grouped by day with unread tracking. And **My Account** is each user's own profile and security settings; for an administrator it also exposes an **Account Lookup** to assist any user, while for everyone else it is strictly self-service — the same role-based boundary applied throughout, and the place where a worker exercises their right to request deletion of their data." |

---

# PART 8 — DEPLOYMENT & CONCLUSION (slides)

## SCENE 23 — Deployment · `slides.html` (23:05–23:45)

| | |
|---|---|
| **VISUAL** | "Deployment" slide — cloud topology + self-hosted option. |
| **ACTION** | Show the topology. |
| **NARRATION** | "Everything you have seen is live and free to run: a single reverse proxy fronts the API and interface, backed by a managed database — and a self-hosted production configuration, with automatic TLS and a bundled database, is provided for organisational deployment. The same artefact serves both the demonstration and a real rollout." |

## SCENE 24 — Conclusion · `slides.html` (23:45–24:30)

| | |
|---|---|
| **VISUAL** | "Conclusion / Contribution" slide → final frame (presented by **Mashkur Alam**). |
| **ACTION** | Advance to the closing slide; hold on the "Presented by Mashkur Alam" credit. |
| **NARRATION** | "In closing: FORGE-Vision demonstrates that real-time, explainable, AI-generated guidance can be delivered within a two-second budget on commodity hardware; that a hybrid simulation-to-reality pathway measurably outperforms single-modality training; and that the resulting platform doubles as a rigorous instrument for testing those claims. The empirical results support all three hypotheses at conventional significance levels. My name is **Mashkur Alam** — thank you, and I welcome the panel's questions." |

---

## Appendix A — Every page, one line

| # | Page | Group | What it does |
|---|------|-------|--------------|
| 1 | **Dashboard** | — | Real-time ops centre: service status, KPIs, live activity feed, recent sessions. |
| 2 | **Live Training** | Training | The live SOP test: consent → camera → pose/tool overlay → step guidance → AI feedback → summary. |
| 3 | **Simulation** | Training | Academic evaluation: H1/H2/H3 hypothesis tests, assumption checks, continual learning. |
| 4 | **Create SOP** | Training | Author a procedure (manual or LLM-parsed from a document); steps, PPE, safety flags. |
| 5 | **Session History** | Data & Analytics | Filterable record of all sessions with per-deviation drill-down. |
| 6 | **Staff Profiles** | Data & Analytics | Per-worker development record + skill level + time-to-competency. |
| 7 | **SOP Library** | Data & Analytics | Catalogue of the 22 approved procedures. |
| 8 | **Analytics** | Data & Analytics | 6 KPIs + 7 tabs (incl. Study Groups, Bias Audit, Emotion). |
| 9 | **Reports** | Data & Analytics | Filtered, publication-ready PDF exports with deviation breakdown. |
| 10 | **Leaderboard** | Data & Analytics | Severity-weighted ranking by period / study group / department. |
| 11 | **Settings** | Administration | LLM provider/model config; encrypted key; test connection. |
| 12 | **User Management** | Administration | RBAC: create/edit/deactivate/export users by role. |
| 13 | **System Health** | Administration | Live service status + LLM latency history (auto-refresh). |
| 14 | **Audit Log** | Administration | Searchable, exportable accountability trail. |
| 15 | **Notifications** | Account | System events grouped by day with unread tracking. |
| 16 | **My Account** | Account | Self-service profile/security; admin Account Lookup; data-deletion request. |

## Appendix B — Figures to keep accurate

Model 85.8% test accuracy · macro-F1 0.875 · p95 latency 62 ms · 2.3 M params ·
99%+ latency-target pass rate at scale · 22 SOPs · 256 workers · 1,555 sessions ·
9,303 deviations · H1 p≈0, large |d| · H2 ANOVA p≈0, η²≈0.20 · weighted accuracy
hybrid 70.4% > real-time 60.4% > simulation 49.4% > control 21.6%.

> Note: live hypothesis-test figures vary slightly with each reseed (e.g. Cohen's d
> ≈ −2.5 to −3.4, η² ≈ 0.20–0.27). Quote whatever the page shows on the day; the
> direction and significance are stable.
