"""Login page — matches login-style1.html exactly (two-panel gold/white layout)."""
import base64
import os

import requests
import streamlit as st


def _logo_b64() -> str:
    logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "logo1.jpg")
    try:
        with open(os.path.normpath(logo_path), "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return ""


def render() -> None:
    logo = _logo_b64()
    logo_html = (
        f'<img src="data:image/jpeg;base64,{logo}" alt="FORGE-Vision">'
        if logo else
        '<div style="font-size:3rem;">🏭</div>'
    )

    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Anton&family=Source+Sans+3:wght@300;400;600;700&display=swap');

/* ── Hide all Streamlit chrome ── */
section[data-testid="stSidebar"]    { display: none !important; }
[data-testid="stSidebarNav"]        { display: none !important; }
[data-testid="stToolbar"]           { display: none !important; }
[data-testid="stDecoration"]        { display: none !important; }
[data-testid="stStatusWidget"]      { display: none !important; }
[data-testid="stAppDeployButton"]   { display: none !important; }
header[data-testid="stHeader"]      { display: none !important; }
#MainMenu { display: none !important; }
footer    { display: none !important; }

/* ── Reset all padding/margin so columns fill the viewport ── */
html, body { height: 100%; overflow: hidden; }

[data-testid="stApp"],
[data-testid="stAppViewContainer"] {
    height: 100vh !important;
    overflow: hidden !important;
}

[data-testid="stMain"] {
    padding: 0 !important;
    overflow: hidden !important;
}

[data-testid="stMainBlockContainer"],
.stMainBlockContainer,
.block-container {
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100vw !important;
    min-height: 100vh !important;
}

[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stVerticalBlock"] {
    min-height: 100vh !important;
    padding: 0 !important;
    gap: 0 !important;
}

/* ── Horizontal block: full height, stretch children ── */
[data-testid="stHorizontalBlock"] {
    gap: 0 !important;
    min-height: 100vh !important;
    align-items: stretch !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* ── Left column — Gold panel ── */
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
    background: #FFCC00 !important;
    min-height: 100vh !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 3rem !important;
    position: relative !important;
    overflow: hidden !important;
    flex: 1 1 50% !important;
}

/* ── Right column — White panel ── */
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) {
    background: #FEFFFF !important;
    min-height: 100vh !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 3rem 4rem !important;
    flex: 1 1 50% !important;
    animation: slideIn 0.5s cubic-bezier(0.22,1,0.36,1) both;
}
@keyframes slideIn {
    from { opacity:0; transform: translateX(30px); }
    to   { opacity:1; transform: translateX(0); }
}

/* ── Right column inner content width ── */
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) > div {
    width: 100% !important;
    max-width: 400px !important;
}

/* ── Input fields — match original style ── */
[data-testid="stTextInput"] label p {
    font-family: 'Source Sans 3', sans-serif !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    color: #1a1a1a !important;
}
[data-testid="stTextInput"] input {
    background: #FEFFFF !important;
    color: #1a1a1a !important;
    border: 2px solid #e8e8e8 !important;
    border-radius: 8px !important;
    padding: 0.85rem 1rem !important;
    font-family: 'Source Sans 3', sans-serif !important;
    font-size: 0.97rem !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #FFCC00 !important;
    box-shadow: none !important;
}

/* ── Sign In button — gold, Anton font ── */
.stButton > button {
    width: 100% !important;
    padding: 1rem !important;
    background: #FFCC00 !important;
    color: #1a1a1a !important;
    font-family: 'Anton', sans-serif !important;
    font-size: 1.1rem !important;
    letter-spacing: 0.1em !important;
    border: none !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    transition: background 0.2s !important;
    box-shadow: none !important;
}
.stButton > button:hover { background: #E6B800 !important; }
.stButton > button:active { transform: scale(0.98) !important; }

/* ── Error/info alerts ── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    font-family: 'Source Sans 3', sans-serif !important;
    font-size: 0.88rem !important;
}
</style>
""", unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 1])

    # ── LEFT PANEL ────────────────────────────────────────────────────────────
    with left_col:
        st.markdown(f"""
<div style="text-align:center;position:relative;z-index:1;
            display:flex;flex-direction:column;align-items:center;">

  <!-- Decorative circles -->
  <div style="position:absolute;bottom:-260px;right:-160px;width:400px;height:400px;
              border-radius:50%;background:rgba(0,0,0,0.06);pointer-events:none;"></div>
  <div style="position:absolute;top:-140px;left:-160px;width:280px;height:280px;
              border-radius:50%;background:rgba(255,255,255,0.12);pointer-events:none;"></div>

  <!-- Logo -->
  <div style="width:180px;height:180px;margin:0 auto 2rem;border-radius:20px;
              overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.25);
              background:white;display:flex;align-items:center;justify-content:center;">
    {logo_html}
  </div>

  <!-- Brand -->
  <div style="font-family:'Anton',sans-serif;font-size:3.6rem;letter-spacing:0.04em;
              color:#1a1a1a;line-height:1;margin-bottom:0.5rem;">
    FORGE<br>VISION
  </div>
  <div style="display:block;width:60px;height:5px;background:#1a1a1a;
              margin:1.2rem auto;border-radius:3px;"></div>
  <div style="font-family:'Anton',sans-serif;font-size:1.05rem;letter-spacing:0.18em;
              color:#1a1a1a;opacity:0.75;text-transform:uppercase;">
    AI Employee Training System
  </div>
</div>

<!-- Left footer -->
<div style="position:absolute;bottom:2rem;left:50%;transform:translateX(-50%);
            font-size:0.78rem;color:rgba(0,0,0,0.45);letter-spacing:0.05em;
            white-space:nowrap;font-family:'Source Sans 3',sans-serif;">
  DBA Research Project
</div>
""", unsafe_allow_html=True)

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────
    with right_col:
        # Form header
        st.markdown("""
<div style="margin-bottom:2.5rem;">
  <div style="font-family:'Anton',sans-serif;font-size:2.4rem;
              color:#1a1a1a;letter-spacing:0.03em;">SIGN IN</div>
  <span style="display:block;width:48px;height:4px;background:#FFCC00;
               margin:0.9rem 0 0.7rem;border-radius:2px;"></span>
  <div style="font-size:0.95rem;color:#6b6b6b;font-weight:300;
              font-family:'Source Sans 3',sans-serif;">
    Welcome back. Enter your credentials to continue.
  </div>
</div>
""", unsafe_allow_html=True)

        # Form inputs
        email    = st.text_input("Email Address", placeholder="you@company.com", key="login_email")
        password = st.text_input("Password",      placeholder="••••••••",        key="login_password", type="password")

        # Remember me + Forgot password row
        st.markdown("""
<div style="display:flex;align-items:center;justify-content:space-between;
            margin:0.4rem 0 1.4rem;font-family:'Source Sans 3',sans-serif;">
  <label style="display:flex;align-items:center;gap:0.5rem;font-size:0.88rem;
                color:#6b6b6b;font-weight:400;cursor:pointer;">
    <input type="checkbox" style="width:16px;height:16px;accent-color:#FFCC00;">
    Remember me
  </label>
  <a href="#" style="font-size:0.88rem;color:#1a1a1a;font-weight:600;
                     text-decoration:none;border-bottom:2px solid #FFCC00;padding-bottom:1px;">
    Forgot password?
  </a>
</div>
""", unsafe_allow_html=True)

        if st.button("SIGN IN →", key="login_submit"):
            _do_login(email.strip(), password)

        # Divider + register + GDPR
        st.markdown("""
<div style="text-align:center;margin:1.6rem 0 1.2rem;position:relative;
            font-size:0.78rem;color:#ccc;letter-spacing:0.08em;
            font-family:'Source Sans 3',sans-serif;">
  <span style="background:#FEFFFF;padding:0 0.8rem;position:relative;z-index:1;">OR</span>
  <div style="position:absolute;top:50%;left:0;right:0;height:1px;
              background:#e8e8e8;z-index:0;"></div>
</div>
<div style="text-align:center;font-size:0.9rem;color:#6b6b6b;
            font-family:'Source Sans 3',sans-serif;margin-bottom:0.5rem;">
  Don't have an account?
  <a href="#" style="color:#1a1a1a;font-weight:700;text-decoration:none;
                     border-bottom:2px solid #FFCC00;padding-bottom:1px;">
    Register here
  </a>
</div>
<div style="text-align:center;font-size:0.75rem;color:#bbb;margin-top:2rem;
            letter-spacing:0.04em;font-family:'Source Sans 3',sans-serif;">
  🔒 Secured &nbsp;·&nbsp; GDPR Compliant &nbsp;·&nbsp; AES-256 Encrypted
</div>
""", unsafe_allow_html=True)


def _do_login(email: str, password: str) -> None:
    if not email or not password:
        st.error("Please enter your email and password.")
        return

    api_base = st.session_state.get("api_base_url", "http://localhost:8000")

    try:
        resp = requests.post(
            f"{api_base}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
    except requests.ConnectionError:
        st.error("Cannot reach the API server. Make sure it is running.")
        return
    except requests.Timeout:
        st.error("Request timed out. Please try again.")
        return

    if resp.status_code == 200:
        data = resp.json()
        if data.get("requires_mfa"):
            st.warning("MFA is required for your account. MFA login is not yet supported in this UI.")
            return
        user = data["user"]
        st.session_state["logged_in"]    = True
        st.session_state["access_token"] = data["access_token"]
        st.session_state["user"]         = user
        st.session_state["ui_role"]      = user["role"]
        st.session_state["current_page"] = "dashboard"
        st.rerun()
    elif resp.status_code == 401:
        st.error("Invalid email or password.")
    elif resp.status_code == 429:
        st.error("Too many login attempts. Please wait a moment and try again.")
    else:
        st.error(f"Login failed (HTTP {resp.status_code}). Please try again.")
