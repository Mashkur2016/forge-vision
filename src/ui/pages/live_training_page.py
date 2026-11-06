"""
Live Training Page — Task 3.5 (Phase 3), cloud WebSocket variant.

Streamlit page for real-time SOP training using the **viewer's browser
webcam**, with AI-generated corrective feedback and step-by-step deviation
logging.

Camera model (cloud-deployable):
  - The browser captures its webcam and streams JPEG frames to the FastAPI
    WebSocket endpoint (/api/v1/ws/live) via the self-contained panel in
    src/ui/ws_camera.py.
  - The server runs each frame through the shared RealtimeFramePipeline
    (CV + ActionRecognizer + SOPDetector) and streams back an annotated frame
    plus any deviation event and LLM corrective text (Groq by default, key
    stored encrypted in the DB).

This WebSocket flow replaced an earlier WebRTC attempt (no working TURN on the
target hosts) so the demo runs fully in the cloud over a single HTTP port. The
server-side camera path (src/realtime/session_manager.py) is unchanged and
still used for edge/local.

Architecture.md Layer 4: Real-Time Worker Guidance — User Interface.
Rules.md §2: GDPR — video frames are processed in server memory, never persisted.
"""
from __future__ import annotations

import time
import uuid
from typing import Optional

import streamlit as st

from src.ui.utils import api_get, api_post, fmt_step_name, fmt_ppe_name, fmt_object_name
from src.ui.ws_camera import ws_camera_panel


# ── SOP loader ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _list_sops() -> list[dict]:
    """Return [{id, name, ...}] from the API, falling back to local data/sops/.

    Cached (5 min): the SOP catalogue rarely changes, and this used to run a
    network fetch on EVERY rerun — including each step action during a live
    session — which made the page lag/blur on every click.
    """
    data = api_get("/api/v1/sops/")
    if isinstance(data, list) and data:
        return data
    # Fallback: scan local files (e.g. when API is offline during dev)
    import glob
    from src.simulation.sop_parser import load_sop
    sops: list[dict] = []
    for path in sorted(glob.glob("data/sops/*.yaml") + glob.glob("data/sops/*.json")):
        try:
            sop = load_sop(path)
            sops.append({"id": sop.id, "name": sop.name})
        except Exception:
            continue
    return sops


def _load_sop_for_session(sop_id: str):
    """Load the SOP object from API, falling back to local files."""
    from src.simulation.sop_schema import SOP
    data = api_get(f"/api/v1/sops/{sop_id}")
    if data and isinstance(data, dict):
        try:
            return SOP.model_validate(data)
        except Exception:
            pass
    # Fallback: scan local files
    import glob as _glob
    from src.simulation.sop_parser import load_sop
    for path in sorted(_glob.glob("data/sops/*.yaml") + _glob.glob("data/sops/*.json")):
        try:
            sop = load_sop(path)
            if sop.id == sop_id:
                return sop
        except Exception:
            continue
    return None


# ── Session state initialisation ───────────────────────────────────────────

def _init_state() -> None:
    defaults: dict = {
        "lt_session_id":       None,
        "lt_running":          False,
        "lt_sop_name":         "",
        "lt_deviations":       [],
        "lt_feedback_history": [],
        "lt_last_feedback":    "",
        "lt_last_severity":    "low",
        "lt_last_step_name":   "",
        "lt_start_time":       None,
        # Step-by-step tracking
        "lt_current_step_idx": 0,
        "lt_step_start_time":  None,
        "lt_step_log":         [],
        "lt_session_complete": False,
        "lt_loaded_sop":       None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ── GDPR consent gate ──────────────────────────────────────────────────────

def _render_consent_banner() -> bool:
    """Render GDPR consent banner. Returns True when consent has been given."""
    if st.session_state.get("lt_consent_given"):
        return True

    st.warning(
        "**Data & Privacy Notice (GDPR)**\n\n"
        "This session will request access to **your browser's camera** and process live "
        "video frames on the server to monitor task execution. Frames are processed "
        "**in-memory only** and are **not stored or transmitted** after the session ends.\n\n"
        "Session metadata (duration, deviation count, SOP ID) is saved to the research "
        "database under research data-governance rules. You can request deletion "
        "of your data at any time via **My Account → Request Account Deletion**.\n\n"
        "Please tick the box below to confirm your consent before starting.",
        icon="🔒",
    )
    consent = st.checkbox(
        "I understand and consent to camera access and session logging for this training session.",
        key="lt_consent_checkbox",
    )
    if consent:
        st.session_state["lt_consent_given"] = True
        st.rerun()
    return False


# ── Deviation → LLM feedback ────────────────────────────────────────────────

def _process_deviations(processor) -> None:
    """
    Drain buffered deviation events from the WebRTC processor and request
    LLM corrective feedback for each via the API.  Runs on the Streamlit
    script thread (safe to touch session_state and call the API).
    """
    for dev in processor.drain_deviations():
        st.session_state["lt_deviations"].append(dev)
        resp = api_post("/api/v1/feedback/from-deviation", dev)
        if resp:
            st.session_state["lt_last_feedback"]  = resp.get("feedback_text", "")
            st.session_state["lt_last_severity"]  = resp.get("severity", "low")
            st.session_state["lt_last_step_name"] = resp.get("step_name", "")
            st.session_state["lt_feedback_history"].append(resp)


def _fallback_feedback(dev: dict) -> str:
    """A short, specific message used if the LLM call fails — never leaves the worker without coaching."""
    name = dev.get("expected_step_name") or "this step"
    if dev.get("deviation_class") == "time_exceeded":
        return (f"The step “{name}” ran over its allotted time. Keep a steady, deliberate pace so "
                f"each step stays within its window without rushing the safety-critical parts.")
    return (f"You skipped the required step “{name}”. Go back and complete it before continuing — "
            f"omitting steps can compromise the procedure's outcome and safety.")


def _record_deviation(step, status: str, reason: str) -> None:
    """
    Record a SKIP or TIMEOUT deviation INSTANTLY (no LLM call) so step navigation
    stays snappy. The real AI coaching is generated in one batch at the session
    summary (`_fill_missing_feedback`).
    """
    name = fmt_step_name(step.name) if step else "this step"
    if status == "skipped":
        dev = {
            "deviation_class": "missing_step",
            "severity":        "high" if (step and getattr(step, "safety_critical", False)) else "medium",
            "what":            f"Step skipped: {name}",
            "why":             reason or "A required SOP step was not performed.",
        }
    else:  # time_exceeded
        dev = {
            "deviation_class": "time_exceeded",
            "severity":        "low",
            "what":            f"Step over time limit: {name}",
            "why":             "The step took longer than its allocated time.",
        }
    dev.update({
        "sop_name":           (st.session_state.get("lt_sop_name")
                               or getattr(st.session_state.get("lt_loaded_sop"), "name", None)
                               or "SOP"),   # required by /feedback/from-deviation
        "timestamp":          time.time(),
        "expected_step_name": name,
        "expected_step_id":   (step.id if step else 0),
        "step_name":          name,
        "model_confidence":   0.0,
        "feedback_text":      None,   # filled in batch at the summary
    })
    st.session_state["lt_deviations"].append(dev)


def _fill_missing_feedback() -> None:
    """At session end, generate real LLM coaching for any deviation that doesn't
    have it yet (manual skips/timeouts). Camera deviations already carry feedback.
    Batched here (with a spinner) so it never blocks live step navigation."""
    pending = [d for d in st.session_state.get("lt_deviations", []) if not d.get("feedback_text")]
    if not pending:
        return
    with st.spinner("Generating AI coaching for this session…"):
        for d in pending:
            try:
                resp = api_post("/api/v1/feedback/from-deviation", d)
            except Exception:
                resp = None
            d["feedback_text"] = (resp or {}).get("feedback_text") or _fallback_feedback(d)


# ── Step advancement ────────────────────────────────────────────────────────

def _advance_step(status: str, deviation_reason: str = "") -> None:
    """Log current step result and move to the next, or complete the session."""
    sop = st.session_state.get("lt_loaded_sop")
    idx = st.session_state.get("lt_current_step_idx", 0)
    step = sop.steps[idx] if sop and idx < len(sop.steps) else None
    started = st.session_state.get("lt_step_start_time") or time.time()
    now = time.time()

    log_entry = {
        "step_id":          step.id if step else idx + 1,
        "step_name":        fmt_step_name(step.name) if step else f"Step {idx + 1}",
        "started_at":       started,
        "completed_at":     now,
        "elapsed_seconds":  round(now - started, 1),
        "status":           status,
        "deviation_reason": deviation_reason,
    }
    st.session_state["lt_step_log"].append(log_entry)

    # Record a deviation instantly (no LLM here — keeps advancement snappy). The
    # AI coaching is generated in one batch at the session summary.
    if status in ("skipped", "time_exceeded"):
        _record_deviation(step, status, deviation_reason)

    next_idx = idx + 1
    if sop and next_idx < len(sop.steps):
        st.session_state["lt_current_step_idx"] = next_idx
        st.session_state["lt_step_start_time"]  = time.time()
    else:
        st.session_state["lt_session_complete"] = True
        _stop_session()


# ── Active step UI (progress + timers + step card) ──────────────────────────

def _render_active_step(sop, step, step_idx: int) -> bool:
    """
    Render progress bar, dual timers, and the current step card.
    Returns True if a rerun is needed (timer expired).
    Never calls st.rerun() internally — caller is responsible.
    The live camera + feedback are rendered by the caller (render()).
    """
    total = len(sop.steps)
    step_num = step_idx + 1

    # ── Progress bar ──────────────────────────────────────────────────────
    st.progress(step_idx / total, text=f"Step {step_num} of {total}")

    # ── Dual timers ───────────────────────────────────────────────────────
    # Rendered as a self-ticking client-side widget so the countdown moves every
    # second WITHOUT a Streamlit rerun (a periodic st.rerun() would recreate the
    # live-camera iframe and kill the WebSocket feed). Display-only; the server
    # still computes `timed_out` below from the step's actual elapsed time.
    now = time.time()
    step_elapsed = now - (st.session_state.get("lt_step_start_time") or now)
    session_elapsed = now - (st.session_state.get("lt_start_time") or now)

    has_limit = bool(step.time_limit_seconds)
    remaining = max(0, (step.time_limit_seconds or 0) - step_elapsed)
    timed_out = has_limit and remaining <= 0

    allocated = sop.estimated_duration_seconds or 0
    alloc_txt = f" / {allocated // 60:02d}:{allocated % 60:02d} allocated" if allocated else ""
    rem_label = "remaining on step" if has_limit else "no step time limit"

    _tpl = """<div style="font-family:Inter,'Segoe UI',sans-serif;display:flex;gap:46px;align-items:baseline;flex-wrap:wrap">
  <div><span id="rem" style="font-size:1.4rem;font-weight:700">&#9201; --:--</span><span style="color:grey;font-size:.85rem"> __REMLABEL__</span></div>
  <div><span id="ela" style="font-size:1.4rem;font-weight:700">&#8987; 00:00</span><span style="color:grey;font-size:.85rem"> elapsed__ALLOC__</span></div>
</div>
<script>
var rem=__REM0__, ela=__SESS0__, hasLimit=__HASLIMIT__, fired=false;
function f(s){s=Math.max(0,s|0);var m=(s/60|0),x=s%60;return (m<10?'0':'')+m+':'+(x<10?'0':'')+x;}
var R=document.getElementById('rem'), E=document.getElementById('ela');
function draw(){ if(hasLimit){R.textContent='\\u23F1 '+f(rem);R.style.color=rem<10?'#e11d1d':(rem<20?'#e67e00':'#1a8a3a');}else{R.textContent='\\u23F1 \\u2014';R.style.color='grey';} E.textContent='\\u231B '+f(ela); }
function adv(){ try{ var b=window.parent.document.querySelector('.st-key-lt_timeout_btn button'); if(b){b.click();} }catch(e){} }
draw(); setInterval(function(){ if(hasLimit){ if(rem>0){rem--;} else if(!fired){fired=true; adv();} } ela++; draw(); },1000);
</script>"""
    _html = (_tpl.replace("__REMLABEL__", rem_label)
                 .replace("__ALLOC__", alloc_txt)
                 .replace("__REM0__", str(int(remaining)))
                 .replace("__SESS0__", str(int(session_elapsed)))
                 .replace("__HASLIMIT__", "true" if has_limit else "false"))
    import streamlit.components.v1 as _components
    _components.html(_html, height=46)

    # Auto-advance when the step's time runs out. The ticking timer above clicks
    # this hidden button the instant it reaches 0, firing a single rerun (the only
    # moment the camera reloads) — instead of continuous polling, which would
    # constantly recreate the live-camera iframe.
    if has_limit:
        st.markdown("<style>div.st-key-lt_timeout_btn{display:none}</style>", unsafe_allow_html=True)
        if st.button("timeout", key="lt_timeout_btn"):
            st.warning("⏰ Step time limit reached — flagging deviation and advancing.")
            _advance_step("time_exceeded", "Time limit exceeded")
            return True

    # Handle timeout after columns are fully rendered
    if timed_out:
        st.warning("⏰ Step time limit reached — flagging deviation and advancing.")
        _advance_step("time_exceeded", "Time limit exceeded")
        return True

    st.divider()

    # ── Step card ─────────────────────────────────────────────────────────
    with st.container(border=True):
        safety_badge = (
            "&nbsp;&nbsp;<span style='background:#dc3545;color:#fff;"
            "padding:2px 8px;border-radius:4px;font-size:0.8rem'>🛑 SAFETY CRITICAL</span>"
            if step.safety_critical else ""
        )
        st.markdown(
            f"<h3 style='margin:0'>📋 Step {step_num} — {fmt_step_name(step.name)}{safety_badge}</h3>",
            unsafe_allow_html=True,
        )
        st.markdown(step.description or "—")

        if step.required_objects:
            st.caption("Required objects: " + ", ".join(f"`{fmt_object_name(o)}`" for o in step.required_objects))
        ppe = list(step.required_ppe or []) + list(sop.required_ppe or [])
        if ppe:
            st.caption("Required PPE: " + ", ".join(f"`{fmt_ppe_name(p)}`" for p in sorted(set(ppe))))

    return False


# ── Session summary ────────────────────────────────────────────────────────

def _persist_live_session() -> None:
    """
    Save the completed browser-webcam (WebSocket) live session to the research
    database via POST /api/v1/session/log, so it shows up in Session History, the
    dashboard activity feed, and the worker's analytics — like a server session.

    Runs once per session (guarded by `lt_persisted`). GDPR: only metadata +
    deviation events are sent — never frames — exactly as the consent notice states.
    """
    if st.session_state.get("lt_persisted"):
        return
    st.session_state["lt_persisted"] = True   # guard first — never double-post

    sop      = st.session_state.get("lt_loaded_sop")
    sop_id   = getattr(sop, "id", None) or st.session_state.get("lt_selected_sop") or "unknown"
    sop_name = st.session_state.get("lt_sop_name") or getattr(sop, "name", None) or "SOP"
    start_t  = st.session_state.get("lt_start_time") or time.time()
    duration = round(time.time() - start_t, 1)

    # Pull in any CAMERA-detected deviations (with their AI feedback) that the
    # server buffered during this session, and merge into lt_deviations (deduped).
    try:
        cam = api_get("/api/v1/ws/live/deviations", {"since": start_t})
        if isinstance(cam, list) and cam:
            seen = {round(d.get("timestamp", 0.0), 1) for d in st.session_state.get("lt_deviations", [])}
            for c in cam:
                if round(c.get("timestamp", 0.0), 1) not in seen:
                    st.session_state["lt_deviations"].append(c)
    except Exception:
        pass

    # Generate the AI coaching for any deviation that doesn't have it yet (manual
    # skips/timeouts) — one batch at session end, so it's persisted and shown.
    _fill_missing_feedback()

    # lt_deviations is the single source of truth: every deviation (manual skip,
    # step timeout, or camera-detected) was recorded LIVE during the session by
    # _record_deviation / camera buffer; _fill_missing_feedback added the AI
    # feedback text. We just normalise the fields for the API here.
    deviations = []
    for d in st.session_state.get("lt_deviations", []):
        deviations.append({
            "timestamp":          d.get("timestamp", 0.0),
            "deviation_class":    d.get("deviation_class") or d.get("error_type") or "deviation",
            "severity":           d.get("severity") or "low",
            "expected_step_name": d.get("expected_step_name") or d.get("step_name") or "",
            "model_confidence":   d.get("model_confidence") or d.get("confidence") or 0.0,
            "what":               d.get("what", ""),
            "why":                d.get("why", ""),
            "feedback_text":      d.get("feedback_text"),
        })

    sid = st.session_state.get("lt_log_sid") or uuid.uuid4().hex[:8]
    st.session_state["lt_log_sid"] = sid
    payload = {
        "session_id":       sid,
        "sop_id":           sop_id,
        "sop_name":         sop_name,
        "started_at":       start_t,
        "duration_seconds": duration,
        "latency_p95_ms":   0.0,
        "deviations":       deviations,
    }
    resp = api_post("/api/v1/session/log", payload)
    st.session_state["lt_persist_ok"] = bool(resp and resp.get("status") in ("saved", "exists"))


def _render_session_summary() -> None:
    """Full summary screen shown after all steps are completed."""
    import pandas as pd

    _persist_live_session()   # record this session to the DB (once)

    sop       = st.session_state.get("lt_loaded_sop")
    step_log  = st.session_state.get("lt_step_log", [])
    start_t   = st.session_state.get("lt_start_time") or time.time()
    total_elapsed = round(time.time() - start_t)
    allocated = (sop.estimated_duration_seconds or 0) if sop else 0

    completed = sum(1 for s in step_log if s["status"] == "completed")
    skipped   = sum(1 for s in step_log if s["status"] == "skipped")
    overrun   = sum(1 for s in step_log if s["status"] == "time_exceeded")
    total     = len(step_log)
    score_pct = round(completed / total * 100) if total else 0

    sop_name = sop.name if sop else "SOP"
    st.success(f"**Session Complete — {sop_name}**")

    if st.session_state.get("lt_persist_ok"):
        st.caption(
            "✅ Saved to the research database — this session now appears in "
            "**Session History**, the **Dashboard** activity feed, and **Analytics** "
            "(metadata + deviation events only; no video stored)."
        )
    elif st.session_state.get("lt_persisted"):
        st.caption("⚠️ Could not save this session to the database (it is still shown below).")

    c1, c2, c3, c4 = st.columns(4)
    delta_str = f"{total_elapsed - allocated:+d}s vs allocated" if allocated else None
    c1.metric("Total Time",   f"{total_elapsed}s",       delta=delta_str, delta_color="inverse")
    c2.metric("Steps Done",   f"{completed}/{total}")
    c3.metric("Skipped",      skipped)
    c4.metric("Score",        f"{score_pct}%")

    st.divider()
    st.subheader("Per-Step Results")

    if step_log:
        df = pd.DataFrame(step_log)[["step_name", "elapsed_seconds", "status", "deviation_reason"]]
        df.columns = ["Step", "Time (s)", "Status", "Notes"]
        status_icons = {"completed": "✅", "skipped": "⏭", "time_exceeded": "⏰"}
        df["Status"] = df["Status"].map(lambda s: f"{status_icons.get(s, '')} {s}")
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ── AI coaching: the real LLM feedback generated for each deviation ──────
    st.divider()
    st.subheader("🧠 AI Coaching & Feedback")
    deviations = st.session_state.get("lt_deviations", [])
    if deviations:
        st.caption(
            f"{len(deviations)} deviation(s) detected — FORGE-Vision generated step-specific "
            "corrective guidance in the moment:"
        )
        for d in deviations:
            _render_feedback_card(
                d.get("feedback_text") or d.get("why") or "",
                d.get("severity", "low"),
                d.get("expected_step_name") or d.get("step_name", ""),
            )
    else:
        st.success(
            "No deviations detected — a clean run. The AI had no corrections to make. ✅"
        )

    st.divider()
    if st.button("Start New Session", type="primary"):
        for key in [k for k in list(st.session_state.keys())
                    if k.startswith("lt_") and k != "lt_consent_given"]:
            del st.session_state[key]
        st.rerun()


# ── Session setup panel (right column, idle state) ─────────────────────────

def _render_session_setup_panel(sop_name_to_id: dict):
    """Prominent session-setup card rendered in the right column of the idle layout."""

    # ── Dark header ───────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="
            background: #111827;
            padding: 1.1rem 1.3rem 1.05rem;
            border-radius: 12px 12px 0 0;
            border-left: 4px solid #FFCC00;
        ">
            <div style="font-size:0.6rem; font-weight:800; letter-spacing:0.18em;
                        text-transform:uppercase; color:#FFCC00; margin-bottom:3px">
                ⚙ Session Setup
            </div>
            <div style="font-size:1.05rem; font-weight:700; color:#ffffff; line-height:1.2">
                Configure &amp; Start Training
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Widget body ───────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "<style>div[data-testid='stVerticalBlock'] div[data-testid='stVerticalBlock']"
            " > div:has(div[data-testid='stVerticalBlockBorderWrapper']) {"
            " border-radius: 0 0 12px 12px !important; border-top: none !important; }</style>",
            unsafe_allow_html=True,
        )

        selected_sop_name = st.selectbox(
            "Training Procedure (SOP)",
            list(sop_name_to_id.keys()),
            key="lt_selected_sop",
            label_visibility="visible",
        )
        selected_sop_id = sop_name_to_id[selected_sop_name]

        st.caption(
            "📷 Your browser camera is used. After starting, click **START** on the "
            "video panel and allow camera access when prompted."
        )

        st.markdown("<div style='margin-top:0.5rem'></div>", unsafe_allow_html=True)

        # ── Start button ──────────────────────────────────────────────────
        st.markdown(
            """
            <style>
            div[data-testid="stBaseButton-primary"][aria-label="lt_start_btn"] button {
                background: linear-gradient(135deg,#FFCC00 0%,#F0C000 100%) !important;
                color: #0f0f0f !important;
                font-weight: 800 !important;
                letter-spacing: 0.06em !important;
                text-transform: uppercase !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "▶  Start Session",
            type="primary",
            use_container_width=True,
            key="lt_start_btn",
        ):
            _start_session(selected_sop_id, selected_sop_name)
            st.rerun()

    return selected_sop_id, selected_sop_name


# ── Live metrics top-bar ───────────────────────────────────────────────────

def _render_live_metrics_bar() -> None:
    """Horizontal 4-card metrics bar rendered above the step content."""
    sop_obj      = st.session_state.get("lt_loaded_sop")
    total_steps  = len(sop_obj.steps) if sop_obj else 0
    step_idx     = st.session_state.get("lt_current_step_idx", 0)
    current_step = step_idx + 1
    start_t      = st.session_state.get("lt_start_time") or time.time()
    elapsed      = int(time.time() - start_t)
    mins, secs   = divmod(elapsed, 60)
    elapsed_str  = f"{mins:02d}:{secs:02d}"
    deviations   = len(st.session_state.get("lt_deviations", []))
    progress_pct = int(step_idx / total_steps * 100) if total_steps else 0

    dev_color = (
        "#16a34a" if deviations == 0
        else "#f59e0b" if deviations <= 2
        else "#dc2626"
    )
    dev_label = (
        "No issues" if deviations == 0
        else f"{deviations} flagged"
    )
    sop_name = sop_obj.name if sop_obj else ""

    st.markdown(
        f"""
        <div class="lt-metrics-grid" style="display:grid;grid-template-columns:auto 1fr 1fr 1fr auto;
                    gap:0.6rem;align-items:stretch;margin-bottom:1rem">

          <!-- Live badge -->
          <div style="background:#111827;border-radius:10px;padding:0.6rem 1rem;
                      border-left:4px solid #FFCC00;display:flex;flex-direction:column;
                      justify-content:center;min-width:120px">
            <div style="font-size:0.5rem;font-weight:900;letter-spacing:0.2em;
                        text-transform:uppercase;color:#FFCC00;margin-bottom:2px">● LIVE</div>
            <div style="font-size:0.72rem;font-weight:600;color:#D1D5DB;
                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                        max-width:160px" title="{sop_name}">{sop_name}</div>
          </div>

          <!-- Duration -->
          <div style="background:#1F2937;border-radius:10px;padding:0.6rem 1rem;
                      border-left:4px solid #FFCC00">
            <div style="font-size:0.5rem;font-weight:800;letter-spacing:0.15em;
                        text-transform:uppercase;color:#9CA3AF;margin-bottom:2px">⏱ Duration</div>
            <div style="font-size:1.6rem;font-weight:800;color:#FFFFFF;
                        font-variant-numeric:tabular-nums">{elapsed_str}</div>
          </div>

          <!-- Current Step -->
          <div style="background:#1F2937;border-radius:10px;padding:0.6rem 1rem;
                      border-left:4px solid #3B82F6">
            <div style="font-size:0.5rem;font-weight:800;letter-spacing:0.15em;
                        text-transform:uppercase;color:#9CA3AF;margin-bottom:2px">📋 Step</div>
            <div style="font-size:1.6rem;font-weight:800;color:#FFFFFF;line-height:1">
              {current_step}<span style="font-size:0.9rem;font-weight:500;color:#6B7280"> / {total_steps}</span>
            </div>
            <div style="background:#374151;border-radius:4px;height:4px;margin-top:0.4rem">
              <div style="background:#3B82F6;border-radius:4px;height:4px;
                          width:{progress_pct}%"></div>
            </div>
          </div>

          <!-- Deviations -->
          <div style="background:#1F2937;border-radius:10px;padding:0.6rem 1rem;
                      border-left:4px solid {dev_color}">
            <div style="font-size:0.5rem;font-weight:800;letter-spacing:0.15em;
                        text-transform:uppercase;color:#9CA3AF;margin-bottom:2px">⚠ Deviations</div>
            <div style="font-size:1.6rem;font-weight:800;color:{dev_color}">{deviations}</div>
            <div style="font-size:0.65rem;color:#9CA3AF">{dev_label}</div>
          </div>

          <div id="lt-stop-placeholder"></div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Main render function ───────────────────────────────────────────────────

def render() -> None:
    _init_state()

    # ── GDPR consent gate ─────────────────────────────────────────────────
    if not _render_consent_banner():
        return

    # ── Resolve SOP list + pre-selection ──────────────────────────────────
    sops = _list_sops()
    if not sops:
        st.warning("No SOPs available. Create one via **SOP Builder** or add a `.yaml` file to `data/sops/`.")
        return

    sop_name_to_id = {s["name"]: s["id"] for s in sops}

    if "lt_sop_preselect_done" not in st.session_state:
        _hint = st.session_state.get("active_sop_name", "")
        if _hint and _hint in sop_name_to_id:
            st.session_state["lt_selected_sop"] = _hint
        st.session_state["lt_sop_preselect_done"] = True

    selected_sop_name = st.session_state.get("lt_selected_sop", list(sop_name_to_id.keys())[0])
    if selected_sop_name not in sop_name_to_id:
        selected_sop_name = list(sop_name_to_id.keys())[0]
    selected_sop_id = sop_name_to_id[selected_sop_name]

    # ── Sidebar status ─────────────────────────────────────────────────────
    with st.sidebar:
        if st.session_state["lt_running"]:
            st.caption("● Session running")

    # ── Session summary ────────────────────────────────────────────────────
    if st.session_state.get("lt_session_complete"):
        _render_session_summary()
        return

    # ── Idle state: two-column layout ──────────────────────────────────────
    if not st.session_state["lt_running"] and st.session_state["lt_session_id"] is None:

        col_sop, col_setup = st.columns([3, 2], gap="large")

        with col_setup:
            _render_session_setup_panel(sop_name_to_id)

        with col_sop:
            if st.session_state.get("active_sop_name"):
                st.success(
                    f"🎯 **Training Ready** — *{st.session_state['active_sop_name']}* "
                    "pre-loaded from Setup Wizard. Click **▶ Start Session** to begin."
                )
            _active_sop_id = sop_name_to_id.get(
                st.session_state.get("lt_selected_sop", selected_sop_name),
                selected_sop_id,
            )
            _show_sop_steps_preview(_active_sop_id)
            _show_last_session_summary()

        return

    # ── Active session ─────────────────────────────────────────────────────
    _render_live_metrics_bar()

    if st.button("■ Stop Session", type="secondary", key="lt_stop_topbar"):
        _stop_session()
        st.rerun()

    st.divider()

    sop = st.session_state.get("lt_loaded_sop")
    if not sop:
        st.error("SOP failed to load for this session.")
        return

    idx  = st.session_state.get("lt_current_step_idx", 0)
    step = sop.steps[idx] if idx < len(sop.steps) else None
    if step is None:
        st.info("All steps processed. Finalising session…")
        return

    # ── Two-column layout: SOP + controls (left) · live camera (right) ─────
    col_sop, col_cam = st.columns([3, 2], gap="large")

    with col_sop:
        timed_out = _render_active_step(sop, step, idx)
        if timed_out:
            st.rerun()

        # ── Step actions ──────────────────────────────────────────────────
        st.write("")
        confirmed = True
        if step.safety_critical:
            confirmed = st.checkbox(
                "I confirm this safety-critical step was completed correctly.",
                key=f"lt_safety_confirm_{idx}",
            )
        act_col, skip_col = st.columns([2, 1], gap="small")
        with act_col:
            if st.button(
                "✓ Mark Step Complete",
                key=f"lt_mark_complete_{idx}",
                type="primary",
                use_container_width=True,
                disabled=not confirmed,
            ):
                _advance_step("completed")
                st.rerun()
        with skip_col:
            with st.expander("⚠ Skip"):
                skip_reason = st.text_input(
                    "Reason for skipping",
                    key=f"lt_skip_reason_{idx}",
                    placeholder="e.g. equipment unavailable",
                )
                if st.button(
                    "Confirm Skip",
                    key=f"lt_skip_confirm_{idx}",
                    disabled=not skip_reason.strip(),
                ):
                    _advance_step("skipped", skip_reason.strip())
                    st.rerun()

    with col_cam:
        st.markdown(
            "<div style='font-weight:800;letter-spacing:.04em;font-size:1.05rem;"
            "margin-bottom:.2rem'>🎥 LIVE CAMERA</div>"
            "<div style='color:#6b7280;font-size:.82rem;margin-bottom:.5rem'>"
            "Click START and allow access — pose, objects &amp; AI feedback appear live.</div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            ws_camera_panel(
                token=st.session_state.get("access_token", ""),
                sop_id=sop.id,
                height=470,
            )

    # NOTE: no periodic st.rerun() here — the live camera runs in a persistent
    # browser component (WebSocket). Re-running would recreate its iframe and
    # drop the camera/WS each tick. Step timers update on the next user action.


# ── Session lifecycle helpers ──────────────────────────────────────────────

def _start_session(sop_id: str, sop_name: str) -> None:
    """Begin a WebRTC training session (no server-side camera/WebSocket)."""
    import uuid

    st.session_state["lt_session_id"]       = str(uuid.uuid4())[:8]
    st.session_state["lt_sop_name"]         = sop_name
    st.session_state["lt_running"]          = True
    st.session_state["lt_deviations"]       = []
    st.session_state["lt_feedback_history"] = []
    st.session_state["lt_last_feedback"]    = ""
    st.session_state["lt_last_severity"]    = "low"
    st.session_state["lt_last_step_name"]   = ""
    st.session_state["lt_start_time"]       = time.time()

    # Step tracking
    sop = _load_sop_for_session(sop_id)
    st.session_state["lt_loaded_sop"]       = sop
    st.session_state["lt_current_step_idx"] = 0
    st.session_state["lt_step_start_time"]  = time.time()
    st.session_state["lt_step_log"]         = []
    st.session_state["lt_session_complete"] = False


def _stop_session() -> None:
    """
    End the current session.  The browser WebRTC stream is stopped by the user
    via the video panel's STOP control; here we just clear running state so the
    summary (or idle) screen takes over.

    NOTE: DB persistence of WebRTC sessions is deferred (Step 4b) — the
    server-side path persists via /session/{id}/stop, but WebRTC sessions have
    no server session object. The local summary screen still reports fully.
    """
    st.session_state["lt_running"]          = False
    st.session_state["lt_session_id"]       = None
    st.session_state["lt_current_step_idx"] = 0
    st.session_state["lt_step_start_time"]  = None


# ── Pre-session helpers ────────────────────────────────────────────────────

def _show_sop_steps_preview(sop_id: str) -> None:
    """Show SOP metadata and expandable steps before a session starts."""
    from src.simulation.sop_schema import SOP
    data = api_get(f"/api/v1/sops/{sop_id}")
    sop = None
    if data and isinstance(data, dict):
        try:
            sop = SOP.model_validate(data)
        except Exception:
            pass
    if sop is None:
        # Fallback: scan local files
        import glob as _glob
        from src.simulation.sop_parser import load_sop
        for path in sorted(_glob.glob("data/sops/*.yaml") + _glob.glob("data/sops/*.json")):
            try:
                s = load_sop(path)
                if s.id == sop_id:
                    sop = s
                    break
            except Exception:
                continue
    if sop is None:
        st.info("Select an SOP in the setup panel, then click **Start Session** to begin.")
        return

    st.subheader(f"📋 {sop.name}")

    dur_min = int((sop.estimated_duration_seconds or 0) / 60)
    dur_str = f"{dur_min} min" if dur_min else "—"
    ppe_str = ", ".join(fmt_ppe_name(p) for p in sop.required_ppe) if sop.required_ppe else "None required"
    st.markdown(
        f"""
        <div class="lt-sop-grid" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.75rem;margin-bottom:1.2rem">
          <div style="background:#F8FAFC;border:1.5px solid #E2E8F0;border-radius:10px;
                      padding:0.9rem 1rem;border-top:3px solid #FFCC00">
            <div style="font-size:0.62rem;font-weight:800;letter-spacing:0.12em;
                        text-transform:uppercase;color:#64748B;margin-bottom:0.35rem">📝 Steps</div>
            <div style="font-size:1.7rem;font-weight:800;color:#111827">{sop.step_count or 0}</div>
          </div>
          <div style="background:#F8FAFC;border:1.5px solid #E2E8F0;border-radius:10px;
                      padding:0.9rem 1rem;border-top:3px solid #FFCC00">
            <div style="font-size:0.62rem;font-weight:800;letter-spacing:0.12em;
                        text-transform:uppercase;color:#64748B;margin-bottom:0.35rem">⏱ Duration</div>
            <div style="font-size:1.7rem;font-weight:800;color:#111827">{dur_str}</div>
          </div>
          <div style="background:#F8FAFC;border:1.5px solid #E2E8F0;border-radius:10px;
                      padding:0.9rem 1rem;border-top:3px solid #FFCC00">
            <div style="font-size:0.62rem;font-weight:800;letter-spacing:0.12em;
                        text-transform:uppercase;color:#64748B;margin-bottom:0.35rem">🏷 Category</div>
            <div style="font-size:0.95rem;font-weight:700;color:#111827;line-height:1.35;
                        word-break:break-word">{sop.category or "—"}</div>
          </div>
        </div>
        <div style="background:#F8FAFC;border:1.5px solid #E2E8F0;border-radius:10px;
                    padding:0.75rem 1rem;margin-bottom:1rem;display:flex;align-items:center;gap:0.5rem">
          <span style="font-size:0.62rem;font-weight:800;letter-spacing:0.12em;
                       text-transform:uppercase;color:#64748B">🦺 PPE Required:</span>
          <span style="font-size:0.88rem;font-weight:600;color:#111827">{ppe_str}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("#### Step-by-step procedure")
    for i, step in enumerate(sop.steps or []):
        flag = " 🛑" if getattr(step, "safety_critical", False) else ""
        with st.expander(f"Step {i + 1}: {fmt_step_name(step.name)}{flag}", expanded=(i == 0)):
            st.markdown(step.description or "—")
            objs = getattr(step, "required_objects", None)
            if objs:
                st.caption("Required objects: " + ", ".join(f"`{fmt_object_name(o)}`" for o in objs))
    st.info("Review the steps above, then click **Start Session** in the setup panel.")


def _show_last_session_summary() -> None:
    """Show deviation table from the last completed session if available."""
    deviations = st.session_state.get("lt_deviations", [])
    if not deviations:
        return
    st.subheader("Last Session — Deviation Log")
    import pandas as pd
    df = pd.DataFrame(deviations)
    if "timestamp" in df.columns:
        df["time"] = pd.to_datetime(df["timestamp"], unit="s").dt.strftime("%H:%M:%S")
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── UI sub-components ──────────────────────────────────────────────────────

def _render_feedback_card(
    feedback: str,
    severity: str,
    step_name: str,
) -> None:
    """Render the AI feedback card with severity-coloured border."""
    color_map = {"high": "#dc3545", "medium": "#fd7e14", "low": "#198754"}
    icon_map  = {"high": "🔴", "medium": "🟡", "low": "🟢"}

    if not feedback:
        st.info("No deviation detected. Keep following the SOP procedure.")
        return

    color = color_map.get(severity, "#0d6efd")
    icon  = icon_map.get(severity, "")

    card_html = f"""
    <div style="
        padding: 1rem;
        border-left: 5px solid {color};
        background: #f8f9fa;
        border-radius: 4px;
        margin-bottom: 1rem;
        font-family: sans-serif;
    ">
        <div style="font-weight:600; margin-bottom:.4rem;">
            {icon} Severity: <span style="color:{color}">{severity.upper()}</span>
            {f"&nbsp;&middot;&nbsp;Step: <em>{step_name}</em>" if step_name else ""}
        </div>
        <div style="font-size:1rem; line-height:1.5;">{feedback}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
