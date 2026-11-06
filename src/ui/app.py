"""
FORGE-Vision — Main Streamlit Application.

Role-aware navigation: the sidebar shows different items for each role
(worker / trainer / supervisor / admin). The role selector is in the
top-right corner of every page; the sidebar is navigation-only.
"""
import sys
import os

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import requests as _requests
import streamlit as st
import streamlit.components.v1 as _components

from src.config import settings as app_settings

# ── Page config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FORGE-Vision",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="auto",  # expanded on desktop, collapsed on mobile
)

if "api_base_url" not in st.session_state:
    st.session_state["api_base_url"] = app_settings.API_BASE_URL

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# ── Global CSS — injected immediately so it applies to ALL pages ──────────
# Must be before the auth gate so SESSION EXPIRED / SIGNED OUT pages also
# get the CSS that hides Streamlit's auto-discovered sidebar nav.
st.markdown("""
<style>
/* ── Hide Streamlit chrome ── */
[data-testid="stSidebarNav"]      { display: none !important; }
[data-testid="stToolbar"]         { display: none !important; }
[data-testid="stDecoration"]      { display: none !important; }
[data-testid="stStatusWidget"]    { display: none !important; }
[data-testid="stAppDeployButton"] { display: none !important; }
header[data-testid="stHeader"]    { display: none !important; }
#MainMenu { display: none !important; }
footer    { display: none !important; }

/* ── Remove main content top padding ── */
[data-testid="stMainBlockContainer"],
.stMainBlockContainer,
.block-container {
    padding-top: 1rem !important;
    margin-top: 0 !important;
    background: #FEFFFF;
}

/* ── Sidebar chrome — kill every built-in header/gap ── */
[data-testid="stSidebarHeader"],
[data-testid="stSidebarHeader"] * {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    overflow: hidden !important;
}
section[data-testid="stSidebar"] > div:first-child,
section[data-testid="stSidebar"] > div {
    padding-top: 0 !important;
    margin-top:  0 !important;
}
[data-testid="stSidebarContent"],
.stSidebarContent,
[data-testid="stSidebarUserContent"],
.stSidebarUserContent {
    padding-top: 0 !important;
    margin-top:  0 !important;
}

/* ── Sidebar background ── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] > div > div,
[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {
    background: #FFFFFF !important;
    border-right: 1px solid #E5E7EB !important;
}

/* ══════════════════════════════════════════════════
   TREE NAVIGATION — nav items inside expanders
   ══════════════════════════════════════════════════ */

/* Nav item buttons */
section[data-testid="stSidebar"] .stButton > button {
    background:      transparent !important;
    border:          none !important;
    border-left:     3px solid transparent !important;
    border-radius:   0 6px 6px 0 !important;
    color:           #374151 !important;
    text-align:      left !important;
    justify-content: flex-start !important;
    padding:         0.48rem 0.8rem 0.48rem 0.75rem !important;
    font-size:       0.85rem !important;
    font-weight:     500 !important;
    width:           100% !important;
    transition:      background 0.15s ease, border-color 0.15s ease, color 0.15s ease !important;
    box-shadow:      none !important;
    letter-spacing:  0.01em !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background:        rgba(160,130,0,0.10) !important;
    border-left-color: #C4A000 !important;
    color:             #7A6200 !important;
}
section[data-testid="stSidebar"] .stButton > button:hover [data-testid="stIconMaterial"] {
    color: #7A6200 !important;
}
/* Active nav item */
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
    background:  rgba(212,178,0,0.13) !important;
    border-left: 3px solid #D4B200 !important;
    color:       #A68900 !important;
    font-weight: 700 !important;
}
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] [data-testid="stIconMaterial"] {
    color: #A68900 !important;
}
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"]:hover {
    background: rgba(212,178,0,0.20) !important;
}

/* ── Expander: strip default chrome ── */
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    border:     none !important;
    box-shadow: none !important;
    background: transparent !important;
    margin:     0 !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] > details,
section[data-testid="stSidebar"] [data-testid="stExpander"] > div {
    border:     none !important;
    box-shadow: none !important;
    background: transparent !important;
}

/* ── Group header (summary / expander toggle) ── */
section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    padding:       0.42rem 0.6rem 0.42rem 0.9rem !important;
    border-radius: 6px !important;
    background:    transparent !important;
    border:        none !important;
    margin:        0.1rem 0.3rem 0 0.3rem !important;
    transition:    background 0.15s ease !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
    background: rgba(212,178,0,0.08) !important;
    cursor:     pointer !important;
}
/* Group label text */
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p {
    font-size:      0.8rem !important;
    font-weight:    800 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.13em !important;
    color:          #9CA3AF !important;
    margin:         0 !important;
    line-height:    1.2 !important;
}
/* Open group label — gold tint */
section[data-testid="stSidebar"] [data-testid="stExpander"] details[open] > summary p {
    color: #A68900 !important;
}
/* Hide default arrow — we'll let Streamlit's built-in arrow show */
section[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
    width:  12px !important;
    height: 12px !important;
    color:  #C4C7CC !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] details[open] > summary svg {
    color: #D4B200 !important;
}

/* ── Expander content: left-border tree line ── */
section[data-testid="stSidebar"] [data-testid="stExpander"] details > div,
section[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    padding:     0.15rem 0.3rem 0.3rem 0 !important;
    margin-left: 1.05rem !important;
    border-left: 2px solid rgba(212,178,0,0.25) !important;
}

/* ── Slide-in animation when group opens ── */
@keyframes navItemIn {
    from { opacity: 0; transform: translateX(-10px); }
    to   { opacity: 1; transform: translateX(0); }
}
section[data-testid="stSidebar"] [data-testid="stExpander"] details[open] > div > div,
section[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] > div {
    animation: navItemIn 0.22s cubic-bezier(0.22, 1, 0.36, 1) both;
}

/* ── Section divider label ── */
.nav-section-label {
    font-size:      0.62rem;
    font-weight:    800;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color:          #CBD5E1;
    padding:        0.6rem 1rem 0.2rem;
    display:        block;
}

/* ── Global primary button: gold (non-sidebar) ──
   Streamlit ≥1.34 dropped the `baseButton-primary` testid in favour of a
   `kind="primary"` attribute, so we match both to stay version-proof. */
.stButton > button[data-testid="baseButton-primary"],
.stButton > button[data-testid="stBaseButton-primary"],
.stButton > button[kind="primary"] {
    background:    #D4B200 !important;
    color:         #111827 !important;
    border:        none !important;
    font-weight:   700 !important;
    border-radius: 6px !important;
}
.stButton > button[data-testid="baseButton-primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover,
.stButton > button[kind="primary"]:hover {
    background: #BCA000 !important;
}
/* Sidebar active nav item (kind-attribute fallback for the rules above) */
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background:  rgba(212,178,0,0.13) !important;
    border-left: 3px solid #D4B200 !important;
    color:       #A68900 !important;
    font-weight: 700 !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] [data-testid="stIconMaterial"] {
    color: #A68900 !important;
}
/* Metric value stays dark (theme-independent) */
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
    color: #0F172A !important;
}

/* ── Top bar separator ── */
.forge-topbar {
    border-bottom: 2px solid #D4B200;
    padding-bottom: 0.7rem;
    margin-bottom:  1.4rem;
    display: flex;
    align-items: center;
}

/* ── Topbar row: vertically centre all controls (role dropdown · profile ──
   badge · Help · Sign Out) so the "View as" selectbox lines up with the
   profile badge instead of sitting a little low. ── */
[data-testid="stHorizontalBlock"]:has(.forge-topbar-anchor) {
    align-items: center !important;
}

/* ── Sidebar footer ── */
.sidebar-footer {
    position:    fixed;
    bottom:      0;
    left:        0;
    width:       21rem;
    padding:     0.6rem 1.2rem;
    border-top:  1px solid #E5E7EB;
    background:  #F9FAFB;
    font-size:   0.7rem;
    color:       #9CA3AF;
    letter-spacing: 0.05em;
    z-index:     999;
}

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background:    #FFFFFF;
    border:        1px solid #E8E8E8;
    border-radius: 8px;
    padding:       0.75rem 1rem !important;
}

/* ── Dataframe header ── */
[data-testid="stDataFrame"] thead tr th {
    background: #111827 !important;
    color: #D4B200 !important;
    font-weight: 700 !important;
}

/* ── Selectbox & input focus: gold ring ── */
[data-testid="stSelectbox"] > div[data-focused="true"] > div,
[data-testid="stTextInput"]  input:focus {
    border-color: #D4B200 !important;
    box-shadow: 0 0 0 2px rgba(212,178,0,0.2) !important;
}

/* ── Tab active: gold underline ── */
button[data-baseweb="tab"][aria-selected="true"] {
    color:        #111827 !important;
    border-bottom-color: #D4B200 !important;
    font-weight:  700 !important;
}

/* ── Sidebar image (logo) ── */
section[data-testid="stSidebar"] [data-testid="stImage"] {
    padding: 0.9rem 1rem 0.7rem;
    background: #FFFFFF;
}

/* Collapse the zero-height helper iframe (the mobile-menu injector) so it
   adds no vertical gap. Real components (e.g. the live camera) keep height. */
[data-testid="stElementContainer"]:has(iframe[height="0"]) {
    display: none !important;
}

/* Collapse the invisible SOP-builder reorder marker so it doesn't shift the
   ↑ button. The element stays in the DOM so :has() can still target the row. */
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdownContainer"] .sb-reorder-anchor) {
    display: none !important;
}

/* ── Mobile slide-in menu controls (hidden on desktop; shown ≤820px) ── */
#forge-menu-toggle {
    display: none;
    position: fixed; top: 0.55rem; right: 0.6rem; z-index: 1003;
    width: 44px; height: 44px;
    align-items: center; justify-content: center;
    border: none; border-radius: 10px;
    background: #1a1a1a; color: #FFCC00;
    font-size: 1.45rem; line-height: 1;
    box-shadow: 0 3px 12px rgba(0,0,0,0.28); cursor: pointer;
}
#forge-menu-toggle:active { transform: scale(0.94); }
#forge-menu-backdrop {
    display: none; position: fixed; inset: 0; z-index: 1001;
    background: rgba(0,0,0,0.45);
    opacity: 0; pointer-events: none; transition: opacity 0.25s ease;
}
body[data-forge-menu="open"] #forge-menu-backdrop { opacity: 1; pointer-events: auto; }

/* ══════════════════════════════════════════════════════════════════════
   MOBILE RESPONSIVE  (≤ 820px)
   Streamlit columns do not stack on small screens by default, so we force
   it here. The topbar is exempted (via the .forge-topbar-anchor marker) so
   its controls wrap into a compact row instead of five full-width blocks.
   ══════════════════════════════════════════════════════════════════════ */
@media (max-width: 820px) {

    /* Tighter content gutters */
    [data-testid="stMainBlockContainer"],
    .stMainBlockContainer,
    .block-container {
        padding-left:  0.8rem !important;
        padding-right: 0.8rem !important;
    }

    /* Stack every column row vertically */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 0.5rem !important;
    }
    [data-testid="stColumn"],
    [data-testid="column"] {
        flex:      1 1 100% !important;
        min-width: 100% !important;
        width:     100% !important;
    }

    /* ── Topbar exception ── keep controls on one wrapping row ── */
    [data-testid="stHorizontalBlock"]:has(.forge-topbar-anchor) {
        align-items: center !important;
        gap: 0.4rem !important;
    }
    [data-testid="stHorizontalBlock"]:has(.forge-topbar-anchor) [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"]:has(.forge-topbar-anchor) [data-testid="column"] {
        flex:      1 1 auto !important;
        min-width: auto !important;
        width:     auto !important;
    }
    /* Title takes the full first line; controls wrap beneath it */
    [data-testid="stHorizontalBlock"]:has(.forge-topbar-anchor) [data-testid="stColumn"]:first-child,
    [data-testid="stHorizontalBlock"]:has(.forge-topbar-anchor) [data-testid="column"]:first-child {
        flex:      1 1 100% !important;
        min-width: 100% !important;
    }
    .forge-topbar { margin-bottom: 0.8rem !important; }
    .forge-topbar p { font-size: 1.5rem !important; }

    /* Drop non-essential topbar controls on mobile (View-as + profile badge)
       so the title + Help/Sign Out lay out cleanly with no overlap. */
    [data-testid="stColumn"]:has(.tb-role-anchor),
    [data-testid="stColumn"]:has(.tb-profile) { display: none !important; }
    /* Compact the remaining topbar buttons (Help / Sign Out) */
    [data-testid="stHorizontalBlock"]:has(.forge-topbar-anchor) .stButton button {
        padding: 0.45rem 0.6rem !important;
        font-size: 0.9rem !important;
        min-height: 0 !important;
    }

    /* Keep the sidebar hamburger reachable on mobile (nav lives in sidebar) */
    [data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        z-index: 1000 !important;
    }

    /* Compact metric cards */
    [data-testid="stMetric"] { padding: 0.6rem 0.8rem !important; }

    /* Wide tables scroll horizontally rather than squashing */
    [data-testid="stDataFrame"] { overflow-x: auto !important; }

    /* Live Training fixed CSS grids → reflow on mobile */
    .lt-metrics-grid { grid-template-columns: 1fr 1fr !important; }
    .lt-sop-grid     { grid-template-columns: 1fr !important; }

    /* SOP Builder: keep the ↑ ↓ ✖ reorder buttons inline (don't stack). The
       marker sits in the button row, so both the row and the step-header row
       that contain it stay side-by-side instead of stacking full-width. */
    [data-testid="stHorizontalBlock"]:has(.sb-reorder-anchor) {
        flex-wrap: nowrap !important;
        gap: 0.3rem !important;
    }

    /* Admin Users 7-column table → one horizontal-scroll region (columns stay
       aligned & side-by-side instead of exploding into 7 stacked cells). */
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .au-scroll-anchor) {
        overflow-x: auto !important;
    }
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .au-scroll-anchor) > [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        min-width: 680px !important;
    }
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .au-scroll-anchor) [data-testid="stColumn"] {
        flex: 1 1 0 !important;
        min-width: 0 !important;
        width: auto !important;
    }
    .au-thead {
        min-width: 680px !important;
        grid-template-columns: repeat(7, 1fr) !important;
    }

    /* ── Sidebar becomes an off-canvas drawer (only when our JS is ready;
          otherwise Streamlit's native mobile sidebar is the fallback) ──── */
    body.forge-js-menu section[data-testid="stSidebar"] {
        position: fixed !important;
        top: 0 !important; left: 0 !important;
        height: 100vh !important;
        width: 82vw !important; max-width: 320px !important; min-width: 0 !important;
        transform: translateX(-103%) !important;
        transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1) !important;
        visibility: visible !important;
        z-index: 1002 !important;
        box-shadow: 0 0 40px rgba(0,0,0,0.35) !important;
    }
    body.forge-js-menu[data-forge-menu="open"] section[data-testid="stSidebar"] {
        transform: translateX(0) !important;
    }
    /* Main content fills the width (the drawer is out of flow) */
    body.forge-js-menu [data-testid="stMain"],
    body.forge-js-menu section.main,
    body.forge-js-menu [data-testid="stMainBlockContainer"] {
        margin-left: 0 !important;
    }
    /* Leave headroom for the floating toggle */
    body.forge-js-menu [data-testid="stMainBlockContainer"],
    body.forge-js-menu .block-container {
        padding-top: 3.4rem !important;
    }
    /* Footer matches the drawer width */
    body.forge-js-menu .sidebar-footer { width: 82vw !important; max-width: 320px !important; }

    /* Hide Streamlit's own sidebar controls — we provide our own toggle */
    body.forge-js-menu [data-testid="stSidebarCollapsedControl"],
    body.forge-js-menu [data-testid="stSidebarCollapseButton"] { display: none !important; }

    /* Show our floating toggle + backdrop */
    #forge-menu-toggle   { display: flex !important; }
    #forge-menu-backdrop { display: block !important; }
}

/* Very small phones — trim further */
@media (max-width: 480px) {
    .forge-topbar p { font-size: 1.3rem !important; }
    [data-testid="stMainBlockContainer"],
    .block-container { padding-left: 0.6rem !important; padding-right: 0.6rem !important; }
}
</style>
""", unsafe_allow_html=True)


# ── Auth page helpers ─────────────────────────────────────────────────────

def _redirect_to_react_login() -> None:
    """Session-expired page shown when token validation fails."""
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
            <div style="text-align:center;padding:3rem 0 1.5rem;">
                <div style="font-size:3rem;margin-bottom:0.8rem;">🔒</div>
                <h2 style="font-size:1.4rem;font-weight:800;color:#1a1a1a;
                            white-space:nowrap;letter-spacing:0.04em;margin:0 0 0.3rem;">
                    SESSION EXPIRED
                </h2>
                <div style="width:36px;height:4px;background:#FFCC00;border-radius:2px;
                            margin:0.7rem auto 1rem;"></div>
                <p style="color:#6b7280;font-size:0.88rem;line-height:1.6;margin:0 0 1.5rem;">
                    Your session has expired or you are not authenticated.<br>
                    Please sign in again to continue.
                </p>
            </div>
        """, unsafe_allow_html=True)
        _render_signin_button()
    st.stop()


def _standalone_login_enabled() -> bool:
    """True when the UI runs without the React frontend (e.g. the Hugging Face
    Space single container) and must present its own login form instead of
    redirecting to the React app."""
    return os.getenv("UI_STANDALONE_LOGIN", "").strip().lower() in ("1", "true", "yes")


def _render_signin_button() -> None:
    """Render a 'SIGN IN' control appropriate to the deployment mode.

    Standalone (e.g. the Hugging Face Space): a button that returns to the in-app
    native login on the next rerun — never an external link. React mode: a link to
    the React login, configurable via the ``REACT_LOGIN_URL`` env var and only
    defaulting to the local dev server for local development."""
    if _standalone_login_enabled():
        if st.button("SIGN IN →", use_container_width=True, type="primary"):
            st.rerun()
    else:
        url = os.getenv("REACT_LOGIN_URL", "https://localhost:5173/login")
        st.link_button("SIGN IN →", url, use_container_width=True)


def _apply_login(data: dict) -> bool:
    """Store tokens from an AuthResponse and mark the session logged in."""
    token = data.get("access_token", "")
    user = _validate_and_get_user(token)
    if not user:
        return False
    st.session_state["logged_in"] = True
    st.session_state["access_token"] = token
    st.session_state["user"] = user
    return True


def _format_detail(payload: object, fallback: str = "Invalid email or password") -> str:
    """Flatten a FastAPI error body into a single human-readable line.

    422 validation errors return ``detail`` as a *list* of dicts; passing that
    list straight to ``st.error`` renders an empty (text-less) box. Flatten it
    to "field: message" text so the user can actually read why login failed.
    """
    try:
        detail = payload.get("detail", fallback)  # type: ignore[attr-defined]
    except AttributeError:
        return fallback
    if isinstance(detail, str):
        return detail or fallback
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict):
                loc = item.get("loc") or []
                field = str(loc[-1]) if loc else ""
                msg = item.get("msg", "")
                parts.append(f"{field}: {msg}".strip(": ").strip())
            else:
                parts.append(str(item))
        return " · ".join(p for p in parts if p) or fallback
    return str(detail) or fallback


# ── "How it works" video (login page) ─────────────────────────────────────
# The video is hosted in the Hugging Face Space repo (Git LFS) and streamed from there, so it is not
# baked into the container image. Override with INTRO_VIDEO_URL (e.g. a local file server in development).
_INTRO_VIDEO_URL = os.getenv(
    "INTRO_VIDEO_URL",
    "https://huggingface.co/spaces/MashkurA/forge-vision/resolve/main/media/forge-vision-how-it-works.mp4",
)
_INTRO_VIDEO_TITLE = "FORGE-Vision: How It Works"
_INTRO_VIDEO_SUBTITLE = "A full system walkthrough"
_INTRO_VIDEO_DESC = (
    "A guided tour of FORGE-Vision, a hybrid computer vision and generative AI system that watches a task, "
    "checks it against the Standard Operating Procedure, and coaches the worker in real time. "
    "About 23 minutes, narrated: the research context, the live training session, analytics, evaluation "
    "and administration. All data shown is synthetic."
)


def _video_modal_injector() -> None:
    """Inject a pop-up video player into the parent page and wire any `[data-fv-video]` link to it.

    Streamlit's markdown can't run scripts, so (like the mobile menu) this uses a zero-height same-origin
    iframe that reaches `window.parent.document`. The video is only fetched when the pop-up is first opened
    (preload="none"), pauses on close, and the link falls back to opening the file in a new tab if JS fails.
    """
    import json

    cfg = json.dumps({
        "url": _INTRO_VIDEO_URL,
        "title": _INTRO_VIDEO_TITLE,
        "subtitle": _INTRO_VIDEO_SUBTITLE,
        "desc": _INTRO_VIDEO_DESC,
    }).replace("</", "<\\/")
    _components.html(
        """
        <script>
        (function () {
          try {
            var doc = window.parent.document;
            if (!doc || doc.getElementById('fv-video-modal')) return;
            var CFG = __CFG__;

            var css = doc.createElement('style');
            css.id = 'fv-video-style';
            css.textContent =
              '#fv-video-modal{position:fixed;inset:0;z-index:1000000;display:none;align-items:center;' +
              'justify-content:center;background:rgba(10,10,10,.82);padding:16px;box-sizing:border-box;}' +
              '#fv-video-modal.fv-open{display:flex;}' +
              '#fv-video-modal .fv-box{width:min(1000px,100%);max-height:100%;overflow:auto;background:#111;' +
              'border-radius:14px;box-shadow:0 30px 80px rgba(0,0,0,.6);border:1px solid rgba(255,204,0,.35);}' +
              '#fv-video-modal .fv-head{display:flex;align-items:flex-start;justify-content:space-between;' +
              'gap:12px;padding:14px 18px 10px;}' +
              '#fv-video-modal .fv-title{font-family:Anton,sans-serif;font-size:1.35rem;letter-spacing:.05em;' +
              'color:#FFCC00;line-height:1.1;margin:0;}' +
              '#fv-video-modal .fv-sub{font-size:.8rem;color:#bdbdbd;margin-top:3px;letter-spacing:.04em;}' +
              '#fv-video-modal .fv-close{flex:none;border:0;background:#FFCC00;color:#1a1a1a;width:34px;height:34px;' +
              'border-radius:50%;font-size:1.1rem;font-weight:700;cursor:pointer;line-height:1;}' +
              '#fv-video-modal .fv-close:hover{background:#E6B800;}' +
              '#fv-video-modal video{display:block;width:100%;aspect-ratio:16/9;background:#000;}' +
              '#fv-video-modal .fv-desc{padding:12px 18px 16px;font-size:.88rem;line-height:1.5;color:#d6d6d6;}' +
              '#fv-video-modal .fv-err{display:none;padding:10px 18px;font-size:.85rem;color:#ffb4a8;}' +
              '#fv-video-modal .fv-err a{color:#FFCC00;}' +
              '@media (max-width:820px){#fv-video-modal{padding:8px;}#fv-video-modal .fv-title{font-size:1.1rem;}}';
            doc.head.appendChild(css);

            var modal = doc.createElement('div');
            modal.id = 'fv-video-modal';
            modal.setAttribute('role', 'dialog');
            modal.setAttribute('aria-modal', 'true');
            modal.setAttribute('aria-labelledby', 'fv-video-title');

            var box = doc.createElement('div'); box.className = 'fv-box';
            var head = doc.createElement('div'); head.className = 'fv-head';
            var hl = doc.createElement('div');
            var h = doc.createElement('h2'); h.id = 'fv-video-title'; h.className = 'fv-title'; h.textContent = CFG.title;
            var sub = doc.createElement('div'); sub.className = 'fv-sub'; sub.textContent = CFG.subtitle;
            hl.appendChild(h); hl.appendChild(sub);
            var close = doc.createElement('button');
            close.type = 'button'; close.className = 'fv-close'; close.setAttribute('aria-label', 'Close video');
            close.textContent = '\\u2715';
            head.appendChild(hl); head.appendChild(close);

            var video = doc.createElement('video');
            video.controls = true; video.preload = 'none'; video.setAttribute('playsinline', '');
            var err = doc.createElement('div'); err.className = 'fv-err';
            err.appendChild(doc.createTextNode('The video could not be loaded. '));
            var direct = doc.createElement('a');
            direct.href = CFG.url; direct.target = '_blank'; direct.rel = 'noopener'; direct.textContent = 'Open it directly.';
            err.appendChild(direct);
            video.addEventListener('error', function () { err.style.display = 'block'; });

            var desc = doc.createElement('div'); desc.className = 'fv-desc'; desc.textContent = CFG.desc;

            box.appendChild(head); box.appendChild(video); box.appendChild(err); box.appendChild(desc);
            modal.appendChild(box);
            doc.body.appendChild(modal);

            var prevOverflow = '';
            function openModal() {
              if (!video.getAttribute('src')) video.src = CFG.url;
              err.style.display = 'none';
              prevOverflow = doc.body.style.overflow;
              doc.body.style.overflow = 'hidden';
              modal.classList.add('fv-open');
              var p = video.play(); if (p && p.catch) p.catch(function () {});
              close.focus();
            }
            function closeModal() {
              video.pause();
              modal.classList.remove('fv-open');
              doc.body.style.overflow = prevOverflow;
            }
            close.addEventListener('click', closeModal);
            modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
            doc.addEventListener('keydown', function (e) {
              if (e.key === 'Escape' && modal.classList.contains('fv-open')) closeModal();
            });
            // Delegated: works even though Streamlit re-renders the login markup.
            doc.addEventListener('click', function (e) {
              var t = e.target && e.target.closest ? e.target.closest('[data-fv-video]') : null;
              if (t) { e.preventDefault(); openModal(); }
            }, true);
          } catch (ex) { /* DOM not ready / cross-origin: the link falls back to opening the file */ }
        })();
        </script>
        """.replace("__CFG__", cfg),
        height=0,
    )


def _native_login_page() -> None:
    """Native Streamlit email/password login for standalone deployments.

    Calls the same `/api/v1/auth/login` the React app uses, so credentials and
    the encrypted token flow are identical. Handles the MFA (pre-auth) second
    step for admin/manager accounts that have TOTP enabled.
    """
    base = app_settings.API_BASE_URL
    from src.ui._login_assets import LOGO_B64

    # ── Replicate the React split-screen login (AuthLayout + Login.tsx) ─────
    st.markdown("""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Anton&family=Source+Sans+3:wght@300;400;600;700&display=swap');
      /* Login is full-bleed two-panel: hide the (empty) sidebar so there is no
         third column. Scoped to the login render only — the dashboard keeps its
         sidebar because this CSS is not injected once logged in. */
      [data-testid="stSidebar"],
      [data-testid="stSidebarCollapsedControl"],
      [data-testid="collapsedControl"] { display: none !important; }
      [data-testid="stMainBlockContainer"], .stMainBlockContainer, .block-container {
          padding: 0 !important; max-width: 100% !important;
      }
      [data-testid="stForm"] {
          background: transparent !important; border: none !important;
          padding: 0 !important; box-shadow: none !important;
      }
      [data-testid="stForm"] input {
          border: 2px solid #e8e8e8 !important; border-radius: 8px !important;
          height: 3rem; background: #FEFFFF !important; font-size: .97rem; color: #1a1a1a;
      }
      [data-testid="stForm"] input:focus { border-color: #FFCC00 !important; box-shadow: none !important; }
      [data-testid="stForm"] label p {
          text-transform: uppercase; font-weight: 700 !important; font-size: .74rem !important;
          letter-spacing: .1em; color: #1a1a1a !important;
      }
      [data-testid="stForm"] button {
          background: #FFCC00 !important; color: #1a1a1a !important; border: none !important;
          font-family: 'Anton', sans-serif !important; letter-spacing: .1em;
          font-size: 1.1rem !important; border-radius: 8px !important; padding: .85rem !important;
      }
      [data-testid="stForm"] button:hover { background: #E6B800 !important; }

      /* Close the stray gap above the gold panel: the invisible style-only blocks stacked above the two
         columns each add one flex row-gap (1rem), pushing the panel down ~32px. Login render only. */
      /* Targets the vertical block that holds the two-column row (works across Streamlit versions: the
         block is a direct child of stMainBlockContainer on newer releases but sits behind extra wrapper
         layers on the pinned 1.39). */
      [data-testid="stVerticalBlock"]:has(> [data-testid="stHorizontalBlock"] .forge-login-hero),
      [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap: 0 !important; }

      /* Space between the password box and its show/hide (eye) button, which otherwise touch */
      [data-testid="stForm"] [data-baseweb="base-input"] button { margin-left: .7rem !important; }
      /* …and let the eye button end flush with the email box above (Streamlit adds 14px right padding) */
      [data-testid="stForm"] [data-baseweb="input"] { padding-right: 0 !important; }
      [data-testid="stForm"] [data-baseweb="base-input"] input { flex: 1 1 auto !important; min-width: 0 !important; }

      /* "Watch the video — How it works" link in the gold hero panel */
      .forge-login-hero a.fv-video-link {
          display: inline-flex; align-items: center; gap: .55rem; margin-top: 1.6rem;
          padding: .65rem 1.25rem; border-radius: 999px; background: #1a1a1a; color: #FFCC00 !important;
          font-weight: 700; font-size: .9rem; letter-spacing: .04em; text-decoration: none !important;
          box-shadow: 0 8px 22px rgba(0,0,0,.25); transition: transform .15s ease, box-shadow .15s ease;
      }
      .forge-login-hero a.fv-video-link:hover { transform: translateY(-1px); box-shadow: 0 12px 28px rgba(0,0,0,.32); }
      .forge-login-hero a.fv-video-link .fv-play {
          display: inline-flex; align-items: center; justify-content: center; width: 1.5rem; height: 1.5rem;
          border-radius: 50%; background: #FFCC00; color: #1a1a1a; font-size: .7rem; padding-left: 2px;
      }
      /* the zero-height script iframe must not leave a gap */
      [data-testid="stElementContainer"]:has(iframe[height="0"]) { display: none !important; }

      /* ── Mobile login (≤ 820px) ──────────────────────────────────────────
         The two-panel split stacks (global rule); shrink the gold hero to a
         compact banner so the form is reachable without scrolling past a
         full-height panel. */
      @media (max-width: 820px) {
        .forge-login-hero {
            min-height: 30vh !important;
            padding: 1.8rem 1rem !important;
        }
        .forge-login-hero .hero-logo {
            width: 92px !important; height: 92px !important;
            margin-bottom: 0.9rem !important;
        }
        .forge-login-hero .hero-title { font-size: 2.1rem !important; }
        .forge-login-hero .hero-sub   { font-size: 0.72rem !important; }
        .forge-login-hero .hero-tag,
        .forge-login-hero .hero-footer { display: none !important; }
        [data-testid="stForm"] { padding: 0 0.4rem !important; }
        /* No sidebar/hamburger on the login screen */
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }
      }
    </style>
    """, unsafe_allow_html=True)

    left, right = st.columns([1, 1], gap="small", vertical_alignment="center")

    # ── LEFT: gold branded panel ──────────────────────────────────────────
    with left:
        st.markdown(
            """
            <div class="forge-login-hero" style="background:#FFCC00;min-height:100vh;display:flex;flex-direction:column;
                        align-items:center;justify-content:center;position:relative;overflow:hidden;">
              <div style="position:absolute;bottom:-120px;right:-120px;width:400px;height:400px;
                          border-radius:50%;background:rgba(0,0,0,0.06);"></div>
              <div style="position:absolute;top:-80px;left:-80px;width:280px;height:280px;
                          border-radius:50%;background:rgba(255,255,255,0.12);"></div>
              <div style="position:relative;z-index:1;text-align:center;">
                <div class="hero-logo" style="width:170px;height:170px;margin:0 auto 1.8rem;border-radius:20px;
                            overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.25);background:#fff;
                            display:flex;align-items:center;justify-content:center;">
                  <img src="data:image/jpeg;base64,__LOGO__" style="width:100%;height:100%;object-fit:contain;"/>
                </div>
                <div class="hero-title" style="font-family:'Anton',sans-serif;font-size:3.4rem;letter-spacing:0.04em;
                            color:#1a1a1a;line-height:1;margin-bottom:0.5rem;">FORGE<br>VISION</div>
                <div style="width:60px;height:5px;background:#1a1a1a;margin:1.1rem auto;border-radius:3px;"></div>
                <div class="hero-sub" style="font-family:'Anton',sans-serif;font-size:1rem;letter-spacing:0.18em;
                            color:#1a1a1a;opacity:.75;text-transform:uppercase;">AI Employee Training System</div>
                <div class="hero-tag" style="margin-top:1rem;font-size:0.78rem;font-style:italic;color:rgba(0,0,0,0.55);
                            letter-spacing:0.06em;">Research. Innovation. Transformation.</div>
                <a class="fv-video-link" data-fv-video href="__VIDEO_URL__" target="_blank" rel="noopener"
                   aria-label="Watch the video: how FORGE-Vision works">
                  <span class="fv-play" aria-hidden="true">&#9654;</span>Watch the video &mdash; How it works
                </a>
              </div>
              <div class="hero-footer" style="position:absolute;bottom:1.5rem;font-size:0.78rem;color:rgba(0,0,0,0.45);
                          letter-spacing:0.05em;">Research Project</div>
            </div>
            """.replace("__LOGO__", LOGO_B64).replace("__VIDEO_URL__", _INTRO_VIDEO_URL),
            unsafe_allow_html=True,
        )
        _video_modal_injector()

    # ── RIGHT: form (centered, max ~400px) ────────────────────────────────
    with right:
        _padl, form_col, _padr = st.columns([1, 8, 1])
        with form_col:
            pre_auth = st.session_state.get("_pre_auth_token")
            if pre_auth:
                st.markdown(
                    "<div style='padding:3rem 0 1.3rem;'>"
                    "<div style=\"font-family:'Anton',sans-serif;font-size:2.4rem;color:#1a1a1a;"
                    "letter-spacing:0.03em;\">VERIFY</div>"
                    "<div style='width:48px;height:4px;background:#FFCC00;margin:0.9rem 0 0.7rem;border-radius:2px;'></div>"
                    "<div style='font-size:0.95rem;color:#6b6b6b;font-weight:300;'>"
                    "Enter the 6-digit code from your authenticator app.</div></div>",
                    unsafe_allow_html=True,
                )
                with st.form("forge_mfa"):
                    code = st.text_input("Authentication code", max_chars=6)
                    ok = st.form_submit_button("VERIFY →", use_container_width=True)
                if ok:
                    try:
                        r = _requests.post(
                            f"{base}/api/v1/auth/verify-mfa",
                            json={"pre_auth_token": pre_auth, "totp_code": code},
                            timeout=10,
                        )
                    except Exception as exc:
                        st.error(f"Cannot reach the server: {exc}")
                        st.stop()
                    if r.status_code == 200 and _apply_login(r.json()):
                        del st.session_state["_pre_auth_token"]
                        st.rerun()
                    st.error("Invalid or expired code.")
                st.stop()

            st.markdown(
                "<div style='padding:3rem 0 1.3rem;'>"
                "<div style=\"font-family:'Anton',sans-serif;font-size:2.4rem;color:#1a1a1a;"
                "letter-spacing:0.03em;\">SIGN IN</div>"
                "<div style='width:48px;height:4px;background:#FFCC00;margin:0.9rem 0 0.7rem;border-radius:2px;'></div>"
                "<div style='font-size:0.95rem;color:#6b6b6b;font-weight:300;'>"
                "Welcome back. Enter your credentials to continue.</div></div>",
                unsafe_allow_html=True,
            )

            with st.form("forge_login"):
                email = st.text_input("Email Address", placeholder="you@company.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                ok = st.form_submit_button("SIGN IN →", use_container_width=True)
            if ok:
                # Normalise the email — mobile keyboards auto-capitalise and may
                # append a trailing space, which would otherwise 401/422.
                email = (email or "").strip().lower()
                password = password or ""
                if not email or not password:
                    st.error("Please enter both your email and password.")
                    st.stop()
                try:
                    r = _requests.post(
                        f"{base}/api/v1/auth/login",
                        json={"email": email, "password": password},
                        timeout=10,
                    )
                except Exception as exc:
                    st.error(f"Cannot reach the server: {exc}")
                    st.stop()
                if r.status_code == 200:
                    data = r.json()
                    if data.get("pre_auth_token"):
                        st.session_state["_pre_auth_token"] = data["pre_auth_token"]
                        st.rerun()
                    elif _apply_login(data):
                        st.rerun()
                    else:
                        st.error("Login succeeded but token validation failed.")
                else:
                    try:
                        detail = _format_detail(r.json())
                    except Exception:
                        detail = "Invalid email or password"
                    st.error(detail)

            st.markdown(
                "<p style='text-align:center;font-size:0.75rem;color:#bbb;margin-top:1.6rem;"
                "letter-spacing:0.04em;'>🔒 Secured · GDPR Compliant · AES-256 Encrypted</p>",
                unsafe_allow_html=True,
            )
    st.stop()


def _login_fallback() -> None:
    """Show the right unauthenticated screen for the deployment mode."""
    if _standalone_login_enabled():
        _native_login_page()
    else:
        _redirect_to_react_login()


def _sign_out_page() -> None:
    """Signed-out confirmation page shown after an intentional logout."""
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
            <div style="text-align:center;padding:3rem 0 1.5rem;">
                <div style="font-size:3rem;margin-bottom:0.8rem;">✅</div>
                <h2 style="font-size:1.4rem;font-weight:800;color:#1a1a1a;
                            white-space:nowrap;letter-spacing:0.04em;margin:0 0 0.3rem;">
                    SIGNED OUT
                </h2>
                <div style="width:36px;height:4px;background:#FFCC00;border-radius:2px;
                            margin:0.7rem auto 1rem;"></div>
                <p style="color:#6b7280;font-size:0.88rem;line-height:1.6;margin:0 0 1.5rem;">
                    You have been signed out successfully.<br>
                    Click below to sign in again.
                </p>
            </div>
        """, unsafe_allow_html=True)
        _render_signin_button()
    st.stop()


def _validate_and_get_user(token: str) -> dict | None:
    """Call /api/v1/auth/me to validate an access token; return user dict or None."""
    try:
        r = _requests.get(
            f"{app_settings.API_BASE_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=3,
        )
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


# ── Early-exit: intentional sign-out (must be before sidebar renders) ────
# The Sign Out button sets this flag and calls st.rerun(). On the rerun the
# flag is caught here — before the sidebar or topbar are drawn — so the
# SIGNED OUT page fills the screen cleanly with no nav chrome.
if st.session_state.get("_sign_out"):
    del st.session_state["_sign_out"]
    _sign_out_page()

# ── Auth gate: accept token from React or redirect to React login ─────────
if not st.session_state["logged_in"]:
    _token    = st.query_params.get("token", "")
    _sop_id   = st.query_params.get("sop_id", "")
    _sop_name = st.query_params.get("sop_name", "")
    if _token:
        _user = _validate_and_get_user(_token)
        if _user:
            st.session_state["logged_in"]    = True
            st.session_state["access_token"] = _token
            st.session_state["user"]         = _user
            if _sop_id:
                # Wizard handed off a specific SOP — go straight to Live Training
                st.session_state["active_sop_id"]   = _sop_id
                st.session_state["active_sop_name"] = _sop_name
                st.session_state["current_page"]    = "live_training"
            st.query_params.clear()
            st.rerun()
        else:
            _login_fallback()
    else:
        _login_fallback()

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "dashboard"

if "ui_role" not in st.session_state:
    st.session_state["ui_role"] = st.session_state.get("user", {}).get("role", "admin")

# ── Role-aware grouped navigation ─────────────────────────────────────────
# Each group: id, label, icon (emoji), items: [(material_icon, label, page_id)]
NAV_GROUPS: dict[str, list[dict]] = {
    "staff": [
        {
            "id": "training", "label": "My Training", "icon": "📈",
            "items": [
                (":material/trending_up:",  "My Progress", "my_progress"),
                (":material/leaderboard:",  "Leaderboard", "leaderboard"),
            ],
        },
        {
            "id": "account", "label": "Account", "icon": "👤",
            "items": [
                (":material/notifications:", "Notifications", "notifications"),
                (":material/person:",        "My Account",    "account"),
            ],
        },
    ],
    "trainer": [
        {
            "id": "training", "label": "Training", "icon": "🎬",
            "items": [
                (":material/videocam:",  "Live Training", "live_training"),
                (":material/science:",   "Simulation",    "evaluation"),
                (":material/add_circle:", "Create SOP",    "sop_builder"),
            ],
        },
        {
            "id": "data", "label": "Data & Reports", "icon": "📊",
            "items": [
                (":material/folder_open:", "Session History",  "session_history"),
                (":material/groups:",      "Staff Profiles",   "worker_profiles"),
                (":material/library_books:", "SOP Library",     "sop_library"),
                (":material/leaderboard:", "Leaderboard",      "leaderboard"),
            ],
        },
        {
            "id": "account", "label": "Account", "icon": "👤",
            "items": [
                (":material/notifications:", "Notifications", "notifications"),
                (":material/person:",        "My Account",    "account"),
            ],
        },
    ],
    "manager": [
        {
            "id": "data", "label": "Data & Reports", "icon": "📊",
            "items": [
                (":material/folder_open:", "Session History",  "session_history"),
                (":material/groups:",      "Staff Profiles",   "worker_profiles"),
                (":material/library_books:", "SOP Library",     "sop_library"),
                (":material/analytics:",   "Analytics",        "analytics"),
                (":material/description:", "Reports",          "report_generator"),
                (":material/leaderboard:", "Leaderboard",      "leaderboard"),
            ],
        },
        {
            "id": "account", "label": "Account", "icon": "👤",
            "items": [
                (":material/notifications:", "Notifications", "notifications"),
                (":material/person:",        "My Account",    "account"),
            ],
        },
    ],
    "admin": [
        {
            "id": "training", "label": "Training", "icon": "🎬",
            "items": [
                (":material/videocam:", "Live Training", "live_training"),
                (":material/science:",  "Simulation",    "evaluation"),
                (":material/add_circle:", "Create SOP",  "sop_builder"),
            ],
        },
        {
            "id": "data", "label": "Data & Analytics", "icon": "📊",
            "items": [
                (":material/folder_open:", "Session History",  "session_history"),
                (":material/groups:",      "Staff Profiles",   "worker_profiles"),
                (":material/library_books:", "SOP Library",     "sop_library"),
                (":material/analytics:",   "Analytics",        "analytics"),
                (":material/description:", "Reports",          "report_generator"),
                (":material/leaderboard:", "Leaderboard",      "leaderboard"),
            ],
        },
        {
            "id": "admin_ops", "label": "Administration", "icon": "⚙️",
            "items": [
                (":material/settings:",        "Settings",        "settings"),
                (":material/manage_accounts:", "User Management", "admin_users"),
                (":material/monitor_heart:",   "System Health",   "admin_health"),
                (":material/fact_check:",      "Audit Log",       "admin_audit"),
            ],
        },
        {
            "id": "account", "label": "Account", "icon": "👤",
            "items": [
                (":material/notifications:", "Notifications", "notifications"),
                (":material/person:",        "My Account",    "account"),
            ],
        },
    ],
}


def _all_pages_for_role(role: str) -> set[str]:
    """Flat set of all page IDs accessible by role (includes dashboard + help)."""
    pages = {"dashboard", "help"}
    for grp in NAV_GROUPS.get(role, []):
        for _, _, pid in grp["items"]:
            pages.add(pid)
    return pages


# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    _logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo2.jpg")
    st.image(_logo_path, width=200)
    st.markdown(
        '<hr style="margin:0 0 0.4rem;border:none;border-top:2px solid #D4B200;">',
        unsafe_allow_html=True,
    )

    _role      = st.session_state["ui_role"]
    _cur_page  = st.session_state["current_page"]

    # ── Dashboard — always at top, outside any group ──────────────────────
    _dash_active = _cur_page == "dashboard"
    if st.button(
        "Dashboard",
        key="nav_dashboard",
        icon=":material/home:",
        use_container_width=True,
        type="primary" if _dash_active else "secondary",
    ):
        st.session_state["current_page"] = "dashboard"
        st.rerun()

    st.markdown(
        '<hr style="margin:0.35rem 0.8rem;border:none;border-top:1px solid #F0F0F0;">',
        unsafe_allow_html=True,
    )

    # ── Grouped tree navigation ───────────────────────────────────────────
    for _grp in NAV_GROUPS.get(_role, []):
        _grp_has_active = any(pid == _cur_page for _, _, pid in _grp["items"])

        with st.expander(
            f"{_grp['icon']}  {_grp['label']}",
            expanded=_grp_has_active,
        ):
            for _icon, _label, _pid in _grp["items"]:
                _is_active = _cur_page == _pid
                if st.button(
                    _label,
                    key=f"nav_{_pid}",
                    icon=_icon,
                    use_container_width=True,
                    type="primary" if _is_active else "secondary",
                ):
                    st.session_state["current_page"] = _pid
                    st.rerun()

    # Footer
    st.markdown(
        '<div class="sidebar-footer">v0.1 &nbsp;·&nbsp; FORGE-Vision Research</div>',
        unsafe_allow_html=True,
    )

# ── Page title map ────────────────────────────────────────────────────────
PAGE_TITLES = {
    "dashboard":       "Dashboard",
    "live_training":   "Live Training",
    "evaluation":      "Simulation",
    "sop_builder":     "Create SOP",
    "sop_library":     "SOP Library",
    "session_history": "Session History",
    "worker_profiles": "Staff Profiles",
    "analytics":       "Analytics",
    "report_generator":"Reports",
    "settings":        "LLM Configuration",
    "leaderboard":     "Leaderboard",
    "admin_users":     "User Management",
    "admin_health":    "System Health",
    "admin_audit":     "Audit Log",
    "my_progress":     "My Progress",
    "notifications":   "Notifications",
    "account":         "My Account",
    "help":            "Help & Documentation",
}


def _render_topbar() -> None:
    """Top bar: page title (left) | View as | Profile badge | Sign Out (right)."""
    role      = st.session_state["ui_role"]
    page_name = PAGE_TITLES.get(st.session_state["current_page"], "—")
    role_labels = {
        "staff":   "Staff Member",
        "trainer": "Trainer",
        "manager": "Manager",
        "admin":   "Admin",
    }

    st.markdown('<div class="forge-topbar">', unsafe_allow_html=True)
    actual_role = st.session_state.get("user", {}).get("role", "staff")

    if actual_role == "admin":
        col_title, col_role, col_profile, col_help, col_logout = st.columns([3.2, 1.6, 1.1, 0.7, 0.7])
    else:
        col_title, col_profile, col_help, col_logout = st.columns([3.2, 1.1, 0.7, 0.7])
        col_role = None

    with col_title:
        st.markdown(
            f'<span class="forge-topbar-anchor"></span>'
            f'<p style="margin:0;font-size:2.1rem;font-weight:800;'
            f'color:#111827;line-height:1.15;letter-spacing:-0.01em;">'
            f'{page_name}</p>',
            unsafe_allow_html=True,
        )

    if col_role is not None:
        with col_role:
            st.markdown('<span class="tb-role-anchor"></span>', unsafe_allow_html=True)
            new_role = st.selectbox(
                "View as",
                options=["staff", "trainer", "manager", "admin"],
                index=["staff", "trainer", "manager", "admin"].index(role),
                key="ui_role_select",
                label_visibility="collapsed",
                format_func=lambda r: r.capitalize(),
            )
            if new_role != role:
                st.session_state["ui_role"] = new_role
                allowed_ids = _all_pages_for_role(new_role)
                if st.session_state["current_page"] not in allowed_ids:
                    st.session_state["current_page"] = "dashboard"
                st.rerun()

    with col_profile:
        st.markdown(
            f'<div class="tb-profile" style="display:flex;align-items:center;gap:0.45rem;">'
            f'<div style="width:26px;height:26px;border-radius:50%;background:#FFCC00;'
            f'display:flex;align-items:center;justify-content:center;'
            f'font-size:0.75rem;flex-shrink:0;">👤</div>'
            f'<span style="font-size:0.82rem;font-weight:600;color:#1a1a1a;white-space:nowrap;">'
            f'{role_labels[actual_role]}</span></div>',
            unsafe_allow_html=True,
        )

    with col_help:
        if st.button("Help", use_container_width=True, key="topbar_help"):
            st.session_state["current_page"] = "help"
            st.rerun()

    with col_logout:
        if st.button("Sign Out", use_container_width=True, key="topbar_signout"):
            # Call logout endpoint to clear the refresh-token cookie
            try:
                _requests.post(
                    f"{app_settings.API_BASE_URL}/api/v1/auth/logout",
                    timeout=3,
                )
            except Exception:
                pass
            # Clear all session state
            for _k in ["logged_in", "access_token", "user", "current_page", "ui_role"]:
                st.session_state.pop(_k, None)
            # Set flag and rerun — the early-exit block at the top of the script
            # will catch this flag BEFORE the sidebar renders, so the SIGNED OUT
            # page is shown cleanly without any nav chrome.
            st.session_state["_sign_out"] = True
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ── Enforce page access based on actual user role ────────────────────────
_actual_role = st.session_state.get("user", {}).get("role", "staff")
if st.session_state["current_page"] not in _all_pages_for_role(_actual_role):
    st.session_state["current_page"] = "dashboard"
    st.session_state["ui_role"] = _actual_role
    st.rerun()

# ── Mobile slide-in menu: inject a top-right toggle + backdrop ───────────
# Streamlit can't collapse the sidebar programmatically, so we manage a
# drawer ourselves: a fixed hamburger toggles `data-forge-menu` on the parent
# <body> (CSS drives the slide-in), and tapping any nav item closes it. Runs
# in a same-origin srcdoc iframe; creation is guarded so reruns don't dupe it.
_components.html(
    """
    <script>
    (function () {
      try {
        var doc = window.parent.document;
        if (!doc || doc.getElementById('forge-menu-toggle')) return;
        var body = doc.body;
        var OPEN = '\\u2715', BARS = '\\u2630';   // ✕  ☰

        // Mark JS-ready so the CSS drawer activates; if this script never runs
        // the app falls back to Streamlit's native mobile sidebar.
        body.classList.add('forge-js-menu');

        var btn = doc.createElement('button');
        btn.id = 'forge-menu-toggle';
        btn.type = 'button';
        btn.setAttribute('aria-label', 'Toggle navigation menu');
        btn.innerHTML = BARS;
        btn.addEventListener('click', function (e) {
          e.preventDefault(); e.stopPropagation();
          if (body.getAttribute('data-forge-menu') === 'open') {
            body.removeAttribute('data-forge-menu'); btn.innerHTML = BARS;
          } else {
            body.setAttribute('data-forge-menu', 'open'); btn.innerHTML = OPEN;
          }
        });
        body.appendChild(btn);

        var bd = doc.createElement('div');
        bd.id = 'forge-menu-backdrop';
        bd.addEventListener('click', function () {
          body.removeAttribute('data-forge-menu'); btn.innerHTML = BARS;
        });
        body.appendChild(bd);

        // Close the drawer when a nav item (any sidebar button) is tapped.
        doc.addEventListener('click', function (e) {
          var t = e.target;
          if (t && t.closest && t.closest('section[data-testid="stSidebar"] button')) {
            body.removeAttribute('data-forge-menu'); btn.innerHTML = BARS;
          }
        }, true);
      } catch (err) { /* DOM not ready / cross-origin — ignore */ }
    })();
    </script>
    """,
    height=0,
)

# ── Top bar (rendered on every page) ─────────────────────────────────────
_render_topbar()

# ── Page routing ──────────────────────────────────────────────────────────
_page = st.session_state["current_page"]

if _page == "dashboard":
    from src.ui.pages.dashboard_page import render
    render()
elif _page == "live_training":
    from src.ui.pages.live_training_page import render
    render()
elif _page == "sop_builder":
    from src.ui.pages.sop_builder_page import render
    render()
elif _page == "sop_library":
    from src.ui.pages.sop_library_page import render
    render()
elif _page == "analytics":
    from src.ui.pages.analytics_page import render
    render()
elif _page == "evaluation":
    from src.ui.pages.evaluation_page import render
    render()
elif _page == "settings":
    from src.ui.pages.settings_page import render
    render()
elif _page == "my_progress":
    from src.ui.pages.my_progress_page import render
    render()
elif _page == "session_history":
    from src.ui.pages.session_history_page import render
    render()
elif _page == "worker_profiles":
    from src.ui.pages.worker_profiles_page import render
    render()
elif _page == "report_generator":
    from src.ui.pages.report_generator_page import render
    render()
elif _page == "leaderboard":
    from src.ui.pages.leaderboard_page import render
    render()
elif _page == "account":
    from src.ui.pages.account_page import render
    render()
elif _page == "notifications":
    from src.ui.pages.notifications_page import render
    render()
elif _page == "admin_users":
    from src.ui.pages.admin_users_page import render
    render()
elif _page == "admin_health":
    from src.ui.pages.admin_health_page import render
    render()
elif _page == "admin_audit":
    from src.ui.pages.admin_audit_page import render
    render()
elif _page == "help":
    from src.ui.pages.help_page import render
    render()
else:
    st.session_state["current_page"] = "dashboard"
    st.rerun()
