"""
My Account — B12.

Self-service profile and password management.

Access model:
  - Worker / Trainer / Supervisor: own account only (no lookup panel)
  - Admin: can look up any account via the Account Lookup panel
"""
from __future__ import annotations

import httpx
import streamlit as st
from src.ui.utils import fmt_date, fmt_datetime


def _api_base() -> str:
    return st.session_state.get("api_base_url", "http://localhost:8000")


def _headers() -> dict:
    token = st.session_state.get("access_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _get(path: str, params: dict | None = None) -> dict | None:
    try:
        with httpx.Client(timeout=6.0) as c:
            r = c.get(f"{_api_base()}{path}", params=params or {}, headers=_headers())
            if r.status_code == 200:
                return r.json()
            return None
    except Exception:
        return None


def _patch(path: str, payload: dict, params: dict | None = None) -> dict | None:
    try:
        with httpx.Client(timeout=6.0) as c:
            r = c.patch(f"{_api_base()}{path}", json=payload, params=params or {}, headers=_headers())
            if r.status_code == 200:
                return r.json()
            st.error(f"API {r.status_code}: {r.text}")
            return None
    except Exception as exc:
        st.error(f"Cannot reach API ({exc})")
        return None


def _post(path: str, payload: dict, params: dict | None = None) -> dict | None:
    try:
        with httpx.Client(timeout=6.0) as c:
            r = c.post(f"{_api_base()}{path}", json=payload, params=params or {}, headers=_headers())
            if r.status_code == 200:
                return r.json()
            st.error(f"API {r.status_code}: {r.text}")
            return None
    except Exception as exc:
        st.error(f"Cannot reach API ({exc})")
        return None


def _render_profile(profile: dict, params: dict) -> None:
    """Render profile card, edit form, password change, and GDPR section."""
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("User ID", profile.get("id"))
        c2.metric("Role", profile.get("role", "—").capitalize())
        c3.metric("Sessions", profile.get("total_sessions", 0))
        c4.metric("Active", "✅" if profile.get("is_active") else "❌")
        st.caption(f"Member since {fmt_date(profile.get('created_at'))}  ·  "
                   f"Last login {fmt_datetime(profile.get('last_login'))}")

    st.divider()

    st.subheader("Edit Profile")
    with st.form("acc_edit"):
        c1, c2 = st.columns(2)
        first_name = c1.text_input("First name", value=profile.get("first_name", ""))
        last_name = c2.text_input("Last name", value=profile.get("last_name", ""))
        email = st.text_input("Email", value=profile.get("email", ""))
        submitted = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
        if submitted:
            body: dict = {}
            if first_name != profile.get("first_name"):
                body["first_name"] = first_name
            if last_name != profile.get("last_name"):
                body["last_name"] = last_name
            if email and email != profile.get("email"):
                body["email"] = email
            if not body:
                st.info("Nothing to change.")
            else:
                resp = _patch("/api/v1/account/me", body, params=params)
                if resp:
                    st.success("Profile updated.")
                    st.rerun()

    st.divider()

    st.subheader("Change Password")
    with st.form("acc_pwd"):
        cur = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        conf = st.text_input("Confirm new password", type="password")
        change = st.form_submit_button("🔑 Change Password", type="primary", use_container_width=True)
        if change:
            if not cur or not new:
                st.warning("Please fill in both password fields.")
            elif new != conf:
                st.error("Passwords do not match.")
            elif len(new) < 8:
                st.error("New password must be at least 8 characters.")
            else:
                resp = _post("/api/v1/account/change-password",
                             {"current_password": cur, "new_password": new},
                             params=params)
                if resp:
                    st.success("Password changed successfully.")

    st.divider()

    st.subheader("Privacy & Data")
    st.info(
        "**GDPR — Your rights.** Under the UK GDPR and Data Protection Act 2018, "
        "you can request access, rectification or erasure of your personal data at any time."
    )

    with st.expander("⚠️ Request Account Deletion", expanded=False):
        st.warning(
            "Requesting deletion will flag your account for removal by an administrator. "
            "All personal data (name, email, session history) will be erased within 30 days "
            "in accordance with the research data retention policy."
        )
        with st.form("acc_delete_request"):
            reason = st.text_area(
                "Reason for deletion (optional)",
                placeholder="e.g. No longer participating in the study",
            )
            confirm_text = st.text_input("Type DELETE to confirm", placeholder="DELETE")
            submit_del = st.form_submit_button(
                "Submit Deletion Request", type="primary", use_container_width=True
            )
            if submit_del:
                if confirm_text.strip().upper() != "DELETE":
                    st.error("Please type DELETE (all caps) to confirm.")
                else:
                    resp = _post(
                        "/api/v1/account/request-deletion",
                        {"reason": reason.strip() or None},
                        params=params,
                    )
                    if resp:
                        st.success(
                            "Deletion request submitted. An administrator will process it "
                            "within 30 days. You will receive a confirmation email."
                        )
                    else:
                        st.success(
                            "Deletion request recorded. An administrator will contact you "
                            "at the email on file within 30 days."
                        )


def render() -> None:
    logged_in_user = st.session_state.get("user", {})
    is_admin = logged_in_user.get("role") == "admin"

    if is_admin:
        # ── Admin: two-column layout with Account Lookup panel ────────────
        col_main, col_lookup = st.columns([3, 1], gap="large")

        with col_lookup:
            with st.container(border=True):
                st.subheader("Account Lookup")
                mode = st.radio("Identify by", ["User ID", "Email"], horizontal=True, key="acc_mode")
                if mode == "User ID":
                    uid = st.number_input("User ID", min_value=1, value=1, step=1, key="acc_uid")
                    params: dict | None = {"user_id": int(uid)}
                else:
                    email_lookup = st.text_input("Email", key="acc_email")
                    params = {"email": email_lookup} if email_lookup else None

                if not params:
                    st.info("Enter an email or User ID to load an account.")
                    return

        profile = _get("/api/v1/account/me", params=params)
        with col_main:
            if profile is None:
                st.warning("Cannot load profile — account not found or API unreachable.")
                return
            _render_profile(profile, params)

    else:
        # ── Worker / Trainer / Supervisor: own account only, full width ───
        own_id = logged_in_user.get("id")
        if not own_id:
            st.warning("Session expired — please log in again.")
            return

        params = {"user_id": own_id}
        profile = _get("/api/v1/account/me", params=params)
        if profile is None:
            st.warning("Cannot load profile — API unreachable.")
            return
        _render_profile(profile, params)
