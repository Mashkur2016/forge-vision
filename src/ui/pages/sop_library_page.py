"""
SOP Library — B4.

Card-grid browser for all Standard Operating Procedure definitions stored
under data/sops/. Click a card to reveal full step detail.
"""
from __future__ import annotations

import streamlit as st
from src.ui.utils import api_delete, api_get, fmt_step_name, fmt_ppe_name, fmt_object_name


def _get(path: str) -> list | dict | None:
    return api_get(path)


def _delete(path: str) -> bool:
    return api_delete(path)


def render() -> None:
    top_l, top_r = st.columns([3, 1])
    with top_l:
        search = st.text_input("Search by name, category or department", key="sop_lib_search")
    with top_r:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ New SOP", type="primary", use_container_width=True, key="sop_lib_new"):
            st.session_state["current_page"] = "sop_builder"
            st.rerun()

    st.divider()

    sops = _get("/api/v1/sops/")
    if sops is None:
        st.warning("Cannot reach API — is Docker running?")
        return
    if not isinstance(sops, list):
        st.info("No SOPs found.")
        return

    # Filter
    if search:
        s = search.lower()
        sops = [
            x for x in sops
            if s in str(x.get("name", "")).lower()
            or s in str(x.get("category") or "").lower()
            or s in str(x.get("department") or "").lower()
            or s in str(x.get("id", "")).lower()
        ]

    if not sops:
        st.info("No SOPs match your search.")
        return

    # ── Card grid ─────────────────────────────────────────────────────────
    st.caption(f"Showing **{len(sops)}** SOPs")
    cols = st.columns(3)
    for i, sop in enumerate(sops):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"### {sop.get('name', sop.get('id'))}")
                st.caption(f"`{sop.get('id')}` · v{sop.get('version', '1.0')}")
                st.markdown(f"**Category:** {sop.get('category') or '—'}")
                st.markdown(f"**Department:** {sop.get('department') or '—'}")
                c1, c2 = st.columns(2)
                c1.metric("Steps", sop.get("step_count", 0))
                dur = sop.get("estimated_duration_seconds") or 0
                c2.metric("Duration", f"{int(dur/60)} min" if dur else "—")

                is_admin = st.session_state.get("ui_role") == "admin"
                btn_cols = st.columns([2, 1]) if is_admin else [st.container()]
                with btn_cols[0]:
                    if st.button("View Details", key=f"view_{sop.get('id')}_{i}", use_container_width=True):
                        st.session_state["sop_lib_selected"] = sop.get("id")
                if is_admin:
                    with btn_cols[1]:
                        if st.button("🗑", key=f"del_{sop.get('id')}_{i}", use_container_width=True,
                                     help="Delete this SOP (admin only)"):
                            sop_id = sop.get("id")
                            if _delete(f"/api/v1/sops/{sop_id}"):
                                st.success(f"SOP `{sop_id}` deleted.")
                                if st.session_state.get("sop_lib_selected") == sop_id:
                                    st.session_state.pop("sop_lib_selected", None)
                                st.rerun()
                            else:
                                st.error("Delete failed — is the API running?")

    # ── Detail pane ───────────────────────────────────────────────────────
    sel = st.session_state.get("sop_lib_selected")
    if sel:
        st.divider()
        st.subheader(f"📄 Details — {sel}")
        detail = _get(f"/api/v1/sops/{sel}")
        if not detail:
            st.error("Could not load SOP detail.")
            return

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("ID", detail.get("id"))
        m2.metric("Version", detail.get("version"))
        m3.metric("Steps", len(detail.get("steps", [])))
        m4.metric("Est. Duration", f"{int((detail.get('estimated_duration_seconds') or 0)/60)} min")

        ppe = detail.get("required_ppe") or []
        if ppe:
            st.markdown("**Required PPE (SOP-wide):** " + ", ".join(f"`{fmt_ppe_name(p)}`" for p in ppe))

        st.markdown("#### Step-by-step")
        for step in detail.get("steps", []):
            flag = " 🛑 *Safety Critical*" if step.get("safety_critical") else ""
            with st.expander(f"Step {step.get('id')}: {fmt_step_name(step.get('name', ''))}{flag}"):
                st.markdown(f"**Description:** {step.get('description', '')}")
                if step.get("required_objects"):
                    st.markdown("**Required objects:** " + ", ".join(f"`{fmt_object_name(o)}`" for o in step["required_objects"]))
                if step.get("required_pose"):
                    st.markdown(f"**Required pose:** `{step['required_pose']}`")
                if step.get("must_follow"):
                    st.markdown(f"**Must follow:** steps {', '.join(str(i) for i in step['must_follow'])}")
                if step.get("time_limit_seconds"):
                    st.markdown(f"**Time limit:** {step['time_limit_seconds']}s")
                if step.get("required_ppe"):
                    st.markdown("**PPE for this step:** " + ", ".join(f"`{fmt_ppe_name(p)}`" for p in step["required_ppe"]))
