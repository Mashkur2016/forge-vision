"""
Help & Documentation — B17.

Tabbed help page covering getting-started, API reference, SOP format,
troubleshooting and project metadata.
"""
from __future__ import annotations

import streamlit as st


def render() -> None:

    tabs = st.tabs([
        "🚀 Getting Started",
        "🔌 API Reference",
        "📋 SOP Guide",
        "🛠 Troubleshooting",
        "ℹ️ About",
        "🔒 Data & Privacy",
    ])

    # ── Getting Started ───────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("First-time setup")
        st.markdown("""
1. **Configure an LLM provider.** Open **⚙️ Settings** and choose a provider
   (Groq and Gemini are free). Paste your API key and click **Test Connection**,
   then **Save Settings**.
2. **Browse the SOP Library.** Go to **📋 SOP Library** to see the procedures
   already installed. Use **🔨 SOP Builder** to create a new one.
3. **Start a Live Training session.** Open **🎬 Live Training**, pick a SOP and
   camera source, and click **Start Session**. Feedback appears on the right.
4. **Run a Simulation.** For offline evaluation use **🎮 Simulation** — load
   synthetic scenarios and measure accuracy without a camera.
5. **Check Analytics.** **📊 Analytics** shows per-worker trends, heatmaps and
   competency estimates.
6. **Generate a Report.** **📄 Reports** produces CSV / summary documents for
   supervisors and the DBA thesis.
7. **Track progress.** Workers can open **📈 My Progress** and
   **🏆 Leaderboard** to see their own standings.
8. **Admin housekeeping.** Admins manage users in **👥 User Management**, view
   **🖥️ System Health** and inspect the **📜 Audit Log**.
""")

    # ── API Reference ─────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Key endpoints")
        st.markdown("""
| Method | Path | Purpose |
|-------|------|---------|
| `POST` | `/api/v1/auth/login` | Authenticate (returns JWT) |
| `GET`  | `/api/v1/analytics/summary` | System-wide stats |
| `GET`  | `/api/v1/analytics/sessions` | Paginated session list |
| `GET`  | `/api/v1/analytics/worker/{id}` | Worker performance |
| `GET`  | `/api/v1/analytics/sop/{id}` | Per-SOP analytics |
| `GET`  | `/api/v1/sops/` | List all SOPs |
| `POST` | `/api/v1/sops/` | Create new SOP |
| `GET`  | `/api/v1/workers` | List workers |
| `POST` | `/api/v1/workers/{id}/profile` | Upsert profile |
| `POST` | `/session/start` | Begin live training |
| `POST` | `/session/{id}/stop` | End session |
| `WS`   | `/session/ws/{id}` | Live frame/event stream |
| `GET`  | `/api/v1/leaderboard/` | Ranked workers |
| `GET`  | `/api/v1/reports/session-summary` | Filtered summary |
| `GET`  | `/api/v1/reports/export/csv` | CSV export |
| `GET`  | `/api/v1/health/detailed` | Detailed health |
| `GET`  | `/api/v1/audit/` | Audit log |

The full interactive schema is available at **`/docs`** on the FastAPI server
when running in development mode.
""")

    # ── SOP Guide ─────────────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Standard Operating Procedure (SOP) YAML format")
        st.markdown("""
An SOP is a structured description of a task that the system can monitor.
SOPs live under **`data/sops/`** as YAML files (JSON also accepted).

**Required fields**
- `id` — lowercase machine-readable identifier (unique)
- `name` — human-readable title
- `steps` — ordered list (ids start at 1, sequential)

**Optional fields**
- `version`, `category`, `department`, `estimated_duration_seconds`
- `required_ppe` — PPE enforced throughout the procedure

**Each step supports**
- `description` — shown to the worker
- `required_objects` — CV labels that must be detected
- `required_pose` — expected pose label
- `must_follow` — list of step ids that must be completed first
- `time_limit_seconds` — maximum time allowed
- `safety_critical` — if true, triggers supervisor alert on deviation
- `required_ppe` — PPE enforced for this step only
""")
        st.code("""sop:
  id: "motor_wiring_v1"
  name: "Servo Motor Wiring Procedure"
  version: "1.0"
  category: "Electrical"
  department: "Assembly Line A"
  estimated_duration_seconds: 900
  required_ppe:
    - insulated_gloves
    - safety_glasses
  steps:
    - id: 1
      name: "power_off"
      description: "Switch off the main power isolator and lock out the supply"
      required_objects: [power_isolator, lockout_tag]
      required_pose: "right_hand_reaching_isolator"
      time_limit_seconds: 30
      safety_critical: true
      required_ppe: [insulated_gloves]
    - id: 2
      name: "verify_zero_voltage"
      description: "Test with a voltage tester — confirm zero volts"
      required_objects: [voltage_tester]
      must_follow: [1]
      time_limit_seconds: 30
      safety_critical: true
""", language="yaml")

    # ── Troubleshooting ───────────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Common issues")
        with st.expander("Camera not detected / black frames"):
            st.markdown("""
- Ensure no other application is using the camera.
- Try a different **Camera Source** index (0, 1, 2) or an RTSP URL.
- On Linux hosts inside Docker, mount `/dev/video0` into the container.
- Check that OpenCV is installed with `cv2.VideoCapture(0)` privileges.
""")
        with st.expander("LLM not responding / timeout"):
            st.markdown("""
- Open **⚙️ Settings** and click **Test Connection**. If it fails:
  - For **Groq / OpenAI / Anthropic / Gemini / xAI** — re-paste the API key
    and confirm it isn't rate-limited or revoked.
  - For **Ollama** — ensure the Ollama server is running (`ollama serve`)
    and that the **Base URL** matches (on Windows Docker: `http://host.docker.internal:11434`).
- Check **🖥️ System Health** for LLM status.
""")
        with st.expander("SOP not appearing in the list"):
            st.markdown("""
- Verify the file lives in `data/sops/` with a `.yaml` or `.json` extension.
- The file must validate against the schema (step ids start at 1, sequential).
- Use **📋 SOP Library** — any parse errors are logged; check backend logs.
""")
        with st.expander("Backend 'Cannot reach API' warnings"):
            st.markdown("""
- Confirm Docker is running: `docker compose ps`.
- The API should be reachable at `http://localhost:8000/health`.
- Check the **API Base URL** — it is stored in session state as
  `api_base_url` and defaults to `http://localhost:8000`.
""")
        with st.expander("Session does not persist after Stop"):
            st.markdown("""
- The session log is only written when **Stop Session** is clicked (Phase 4
  spec). Refreshing or killing the browser tab skips the save step.
- Check the **📊 Analytics → Session History** tab — if it's missing, look
  at backend logs for a `TrainingSessionLog` save error.
""")

    # ── About ─────────────────────────────────────────────────────────────
    with tabs[4]:
        st.subheader("About FORGE-Vision")
        st.markdown("""
**FORGE-Vision** is a hybrid Computer Vision + Generative AI system for
real-time and simulation-based employee training, developed as part of a
**Doctor of Business Administration (DBA)** research project.

**Version:** 0.1 (prototype — Phase 5 / Evaluation & Validation)

**Researcher:** Prof. Dr. Karim Mohammed Rezaul
""")
        st.markdown("#### Research hypotheses")
        st.markdown("""
- **H1** — Employees trained using FORGE-Vision will achieve a statistically
  significant reduction in task error rates compared to traditional training
  (p < 0.05).
- **H2** — The hybrid (simulation → real-time) approach will produce better
  skill transfer than simulation-only or real-time-only methods.
- **H3** — AI-generated real-time feedback will significantly reduce task
  completion time compared to post-hoc feedback.
""")
        st.markdown("#### Stack")
        st.markdown("""
- **CV** — OpenCV, MediaPipe Holistic, YOLOv8, SlowFast / CNN+LSTM
- **LLM** — OpenAI / Groq / Anthropic / Gemini / Ollama via unified provider
- **Backend** — FastAPI + SQLAlchemy (async) + PostgreSQL
- **UI** — Streamlit (prototype)  ·  React optional (future)
- **Infra** — Docker Compose, NVIDIA CUDA, optional Jetson edge
""")

    # ── Data & Privacy ────────────────────────────────────────────────────
    with tabs[5]:
        st.subheader("Data & Privacy — GDPR Compliance")
        st.markdown(
            "FORGE-Vision is operated under research governance and "
            "complies with the **UK GDPR** and **Data Protection Act 2018**."
        )

        st.markdown("#### Your rights")
        st.markdown("""
| Right | How to exercise |
|-------|----------------|
| **Access** | Contact your study administrator or email the researcher |
| **Rectification** | Edit your name/email via **👤 My Account** |
| **Erasure** | Submit a request via **👤 My Account → Request Account Deletion** |
| **Restriction** | Contact researcher — processing will be paused pending review |
| **Portability** | Session data export available via **📄 Reports** |
| **Object** | Contact the researcher; you may withdraw from the study at any time |
""")

        st.markdown("#### Data retention schedule")
        st.markdown("""
| Data type | Retention period | Storage location | Notes |
|-----------|-----------------|-----------------|-------|
| Live video frames | **Not stored** — processed in-memory only | — | Discarded immediately after inference |
| Session metadata (duration, SOP, deviation count) | 5 years from study end | Encrypted PostgreSQL (university servers) | Required for thesis reproducibility |
| Worker profiles (name, department, role) | Study duration + 1 year | Encrypted PostgreSQL | Deleted on request |
| Emotion / stress signals | Aggregated only; no individual record | PostgreSQL | Facial images never stored |
| Authentication tokens | 24-hour TTL | Server memory only | Not persisted to disk |
| Audit logs | 2 years | PostgreSQL | Access logs for GDPR accountability |
""")

        st.markdown("#### Contact")
        st.markdown("""
**Data Controller:** Prof. Dr. Karim Mohammed Rezaul
**Researcher / Primary Contact:** Prof. Dr. Karim Mohammed Rezaul
**DPO:** Data Protection Officer — contact via your study administrator
**ICO Registration:** Registered with the Information Commissioner's Office.
""")
