"""
User Management — admin only.

List, filter, create, edit and delete users.
"""
from __future__ import annotations

import csv
import io

import streamlit as st
from src.ui.utils import (
    _api_base, _headers,
    api_get, api_patch, api_post, api_delete,
    fmt_date, fmt_datetime,
)


_ROLE_COLOURS = {
    "admin":      ("#FEE2E2", "#991B1B"),
    "manager":    ("#DBEAFE", "#1E3A8A"),
    "trainer":    ("#DCFCE7", "#166534"),
    "staff":      ("#FEF3C7", "#92400E"),
}


def _role_badge(role: str) -> str:
    bg, fg = _ROLE_COLOURS.get(role, ("#E2E8F0", "#334155"))
    return (f'<span style="background:{bg};color:{fg};'
            f'padding:0.15rem 0.55rem;border-radius:20px;font-size:0.72rem;'
            f'font-weight:700;text-transform:uppercase;">{role}</span>')


def render() -> None:

    # ── Header row ─────────────────────────────────────────────────────────
    h1, h2 = st.columns([5, 2])
    h1.subheader("User Management")
    with h2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Add New User", type="primary", use_container_width=True, key="au_add_btn"):
            st.session_state["au_show_add"] = not st.session_state.get("au_show_add", False)
            st.session_state.pop("au_edit_id", None)
            st.session_state.pop("au_delete_confirm_id", None)

    # ── Add User panel ─────────────────────────────────────────────────────
    if st.session_state.get("au_show_add", False):
        with st.container(border=True):
            au_tab, inv_tab = st.tabs(["➕ Create User", "📧 Invite by Email"])

            with au_tab:
                st.caption("Creates an account immediately — the user can log in right away via the React app (localhost:5173).")
                with st.form("au_create_user"):
                    cc1, cc2 = st.columns(2)
                    cu_first = cc1.text_input("First name *")
                    cu_last  = cc2.text_input("Last name *")
                    cu_email = st.text_input("Email *")
                    cc3, cc4 = st.columns(2)
                    cu_dept = cc3.text_input("Department (optional)", placeholder="e.g. Faculty of Science")
                    cu_role = cc4.selectbox("Role *", ["staff", "trainer", "manager", "admin"])
                    cp1, cp2 = st.columns(2)
                    cu_pw  = cp1.text_input("Password *", type="password")
                    cu_pw2 = cp2.text_input("Confirm Password *", type="password")
                    col_s, col_c = st.columns(2)
                    submitted = col_s.form_submit_button("Create Account", type="primary", use_container_width=True)
                    cancelled = col_c.form_submit_button("Cancel", use_container_width=True)

                    if cancelled:
                        st.session_state.pop("au_show_add", None)
                        st.rerun()

                    if submitted:
                        if not all([cu_first, cu_last, cu_email, cu_pw]):
                            st.error("First name, last name, email and password are required.")
                        elif cu_pw != cu_pw2:
                            st.error("Passwords do not match.")
                        elif len(cu_pw) < 8:
                            st.error("Password must be at least 8 characters.")
                        else:
                            try:
                                import httpx as _hx
                                with _hx.Client(timeout=10.0) as c:
                                    body = {
                                        "first_name": cu_first.strip(),
                                        "last_name":  cu_last.strip(),
                                        "email":      cu_email.strip().lower(),
                                        "password":   cu_pw,
                                        "department": cu_dept.strip() or None,
                                        "gdpr_consent": True,
                                    }
                                    r = c.post(
                                        f"{_api_base()}/api/v1/auth/register",
                                        json=body,
                                        headers=_headers(),
                                    )
                                    if r.status_code in (200, 201):
                                        user_data = r.json()
                                        if cu_role != "staff":
                                            uid = user_data.get("user_id") or user_data.get("id")
                                            if uid:
                                                c.patch(
                                                    f"{_api_base()}/api/v1/admin/users/{uid}",
                                                    json={"role": cu_role, "is_active": True},
                                                    headers=_headers(),
                                                )
                                        st.success(f"Account created for **{cu_email}**. Role: {cu_role}.")
                                        st.session_state.pop("au_show_add", None)
                                        st.rerun()
                                    elif r.status_code == 409:
                                        st.error("An account with that email already exists.")
                                    else:
                                        st.error(f"Registration failed ({r.status_code}): {r.text}")
                            except Exception as exc:
                                st.error(f"Cannot reach API ({exc})")

            with inv_tab:
                st.caption("Sends an invite link — user self-registers via the React app.")
                with st.form("au_invite"):
                    ic1, ic2 = st.columns([3, 2])
                    inv_email = ic1.text_input("Email")
                    inv_role = ic2.selectbox("Role", ["staff", "trainer", "manager", "admin"])
                    send = st.form_submit_button("Send Invite", type="primary", use_container_width=True)
                    if send and inv_email:
                        resp = api_post("/api/v1/admin/users/invite", {"email": inv_email, "role": inv_role})
                        if resp:
                            st.success(resp.get("message", "Invite sent."))

        st.divider()

    # ── Filters ────────────────────────────────────────────────────────────
    f1, f2, f3 = st.columns([3, 2, 2])
    search        = f1.text_input("Search (name or email)", key="au_search")
    role_filter   = f2.selectbox("Role",   ["all", "staff", "trainer", "manager", "admin"], key="au_role")
    status_filter = f3.selectbox("Status", ["all", "active", "inactive"], key="au_status")

    st.divider()

    # ── Load users ─────────────────────────────────────────────────────────
    users = api_get("/api/v1/admin/users/")
    if users is None:
        st.warning("Cannot reach API — is Docker running?")
        return
    if not isinstance(users, list):
        st.info("No users.")
        return

    # Apply filters
    if search:
        s = search.lower()
        users = [u for u in users
                 if s in (u.get("username") or "").lower()
                 or s in (u.get("email") or "").lower()]
    if role_filter != "all":
        users = [u for u in users if u.get("role") == role_filter]
    if status_filter != "all":
        want = status_filter == "active"
        users = [u for u in users if bool(u.get("is_active")) == want]

    st.caption(f"**{len(users)}** user(s)")

    # ── Delete confirmation banner ─────────────────────────────────────────
    del_id = st.session_state.get("au_delete_confirm_id")
    if del_id:
        del_target = next((u for u in users if u["id"] == del_id), None)
        if del_target:
            name = del_target.get("username") or del_target.get("email")
            st.warning(f"⚠️  Permanently delete **{name}** (#{del_id})? This cannot be undone.")
            dc1, dc2, _ = st.columns([1.5, 1.5, 4])
            if dc1.button("✅ Yes, Delete", type="primary", use_container_width=True, key="au_del_confirm"):
                if api_delete(f"/api/v1/admin/users/{del_id}"):
                    st.success(f"User #{del_id} deleted.")
                    st.session_state.pop("au_delete_confirm_id", None)
                    st.rerun()
                else:
                    st.error("Delete failed — you cannot delete your own account, or check API logs.")
            if dc2.button("Cancel", use_container_width=True, key="au_del_cancel"):
                st.session_state.pop("au_delete_confirm_id", None)
                st.rerun()

    # ── Table (HTML header + Streamlit rows) ──────────────────────────────
    # Wrapped in a container tagged with `.au-scroll-anchor`; on mobile the
    # global CSS turns this container into a single horizontal-scroll region so
    # the 7 columns stay aligned instead of each row exploding into 7 stacked
    # cells. The `au-thead` class lets the header reflow to match.
    header = (
        '<div class="au-thead" style="display:grid;grid-template-columns:60px 2.5fr 2.5fr 1.5fr 1fr 1.5fr 1fr;'
        'padding:0.5rem;background:#F1F5F9;border-radius:6px;font-weight:700;font-size:0.8rem;">'
        '<div>ID</div><div>Name</div><div>Email</div><div>Role</div>'
        '<div>Sessions</div><div>Last Active</div><div>Actions</div></div>'
    )
    with st.container():
        st.markdown('<span class="au-scroll-anchor"></span>', unsafe_allow_html=True)
        st.markdown(header, unsafe_allow_html=True)

        for u in users:
            c1, c2, c3, c4, c5, c6, c7 = st.columns([0.6, 2.5, 2.5, 1.5, 1, 1.5, 1.0])
            c1.write(f"#{u.get('id')}")
            c2.write(u.get("username") or "—")
            c3.write(u.get("email") or "—")
            c4.markdown(_role_badge(u.get("role", "")), unsafe_allow_html=True)
            c5.write(u.get("session_count", 0))
            c6.write(fmt_date(u.get("last_session_at")))
            with c7:
                btn1, btn2 = st.columns(2)
                if btn1.button("✏️", key=f"au_edit_{u['id']}", use_container_width=True, help="Edit user"):
                    st.session_state["au_edit_id"] = u["id"]
                    st.session_state.pop("au_delete_confirm_id", None)
                    st.session_state.pop("au_show_add", None)
                if btn2.button("🗑️", key=f"au_del_{u['id']}", use_container_width=True, help="Delete user"):
                    st.session_state["au_delete_confirm_id"] = u["id"]
                    st.session_state.pop("au_edit_id", None)
                    st.session_state.pop("au_show_add", None)

    # ── Edit form ─────────────────────────────────────────────────────────
    edit_id = st.session_state.get("au_edit_id")
    if edit_id:
        target = next((u for u in users if u["id"] == edit_id), None)
        if target:
            with st.expander(f"Edit user #{edit_id} — {target.get('username')}", expanded=True):
                with st.form(f"au_edit_form_{edit_id}"):
                    ec1, ec2 = st.columns(2)
                    new_first = ec1.text_input("First Name", value=target.get("first_name") or "")
                    new_last  = ec2.text_input("Last Name",  value=target.get("last_name") or "")
                    new_email_disp = st.text_input("Email (read-only)", value=target.get("email") or "", disabled=True)
                    ec3, ec4, ec5 = st.columns(3)
                    new_dept = ec3.text_input("Department", value=target.get("department") or "")
                    new_role = ec4.selectbox(
                        "Role",
                        ["staff", "trainer", "manager", "admin"],
                        index=["staff", "trainer", "manager", "admin"].index(target.get("role", "staff")),
                    )
                    new_active = ec5.checkbox("Account active", value=bool(target.get("is_active", True)))
                    col_save, col_cancel = st.columns(2)
                    save   = col_save.form_submit_button("💾 Save", type="primary", use_container_width=True)
                    cancel = col_cancel.form_submit_button("Cancel", use_container_width=True)

                    if save:
                        payload: dict = {
                            "role": new_role,
                            "is_active": new_active,
                            "department": new_dept.strip() or None,
                        }
                        if new_first.strip():
                            payload["first_name"] = new_first.strip()
                        if new_last.strip():
                            payload["last_name"] = new_last.strip()
                        resp = api_patch(f"/api/v1/admin/users/{edit_id}", payload)
                        if resp:
                            st.success("User updated.")
                            st.session_state.pop("au_edit_id", None)
                            st.rerun()
                        else:
                            st.error("Update failed — check API logs.")
                    elif cancel:
                        st.session_state.pop("au_edit_id", None)
                        st.rerun()

    st.divider()

    # ── CSV export ─────────────────────────────────────────────────────────
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "username", "email", "role", "is_active", "session_count", "last_session_at"])
    for u in users:
        writer.writerow([
            u.get("id"), u.get("username"), u.get("email"),
            u.get("role"), u.get("is_active"),
            u.get("session_count"), u.get("last_session_at"),
        ])
    st.download_button(
        "⬇ Export Users CSV",
        data=buf.getvalue(),
        file_name="users.csv",
        mime="text/csv",
        use_container_width=True,
    )
