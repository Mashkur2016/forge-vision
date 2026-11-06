"""
Audit Log — B16 (admin).

Paginated view of the API audit log with search and CSV export.
"""
from __future__ import annotations

import httpx
import streamlit as st
from src.ui.utils import _api_base, _headers, api_get, fmt_datetime


def _get(path: str, params: dict | None = None):
    try:
        with httpx.Client(timeout=6.0) as c:
            r = c.get(f"{_api_base()}{path}", params=params or {}, headers=_headers())
            if r.status_code == 200:
                return r
            return None
    except Exception:
        return None


def render() -> None:

    f1, f2, f3 = st.columns([4, 1, 1])
    search = f1.text_input("Search (user, action, resource, detail)", key="au_search")
    page_size = f2.selectbox("Rows", [25, 50, 100, 200], index=1, key="au_ps")
    if "au_page" not in st.session_state:
        st.session_state["au_page"] = 1

    params = {"page": st.session_state["au_page"], "page_size": page_size}
    if search.strip():
        params["search"] = search.strip()

    r = _get("/api/v1/audit/", params=params)
    if r is None:
        st.warning("Cannot reach API — is Docker running?")
        return
    data = r.json()

    items = data.get("items", [])
    total = data.get("total", 0)
    total_pages = max((total - 1) // page_size + 1, 1)

    # Pagination buttons
    p1, p2, p3 = st.columns([1, 3, 1])
    with p1:
        if st.button("◀ Previous", disabled=st.session_state["au_page"] <= 1):
            st.session_state["au_page"] -= 1
            st.rerun()
    with p2:
        st.caption(f"Page {st.session_state['au_page']} of {total_pages}  ·  {total} entries total")
    with p3:
        if st.button("Next ▶", disabled=st.session_state["au_page"] >= total_pages):
            st.session_state["au_page"] += 1
            st.rerun()

    st.divider()

    # Table
    if not items:
        st.info("No audit entries match the filter.")
    else:
        try:
            import pandas as pd
            rows = [{
                "ID": it.get("id"),
                "Timestamp": fmt_datetime(it.get("timestamp")),
                "User": it.get("user"),
                "Action": it.get("action"),
                "Resource": it.get("resource"),
                "Detail": it.get("detail"),
                "IP": it.get("ip"),
            } for it in items]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        except ImportError:
            for it in items:
                st.write(it)

    st.divider()

    # CSV export
    try:
        import httpx as _httpx
        resp = _httpx.get(f"{_api_base()}/api/v1/audit/export", timeout=10.0, headers=_headers())
        if resp.status_code == 200:
            st.download_button(
                "⬇ Export Full Audit Log (CSV)",
                data=resp.content,
                file_name="audit_log.csv",
                mime="text/csv",
                use_container_width=True,
            )
    except Exception:
        st.caption("Export unavailable.")
