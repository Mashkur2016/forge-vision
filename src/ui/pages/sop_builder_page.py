"""
SOP Builder — B5.

Create new SOP definitions either manually (form-based) or by uploading
a document for LLM parsing.
"""
from __future__ import annotations

import streamlit as st
import yaml
from src.ui.utils import api_post


def _post(path: str, payload: dict) -> dict | None:
    return api_post(path, payload)


def _init_state() -> None:
    if "sb_steps" not in st.session_state:
        st.session_state["sb_steps"] = []
    if "sb_meta" not in st.session_state:
        st.session_state["sb_meta"] = {
            "id": "", "name": "", "version": "1.0",
            "category": "", "department": "",
            "estimated_duration_seconds": 600,
            "required_ppe": "",
        }


def _empty_step() -> dict:
    return {
        "name": "",
        "description": "",
        "required_objects": "",
        "required_pose": "",
        "time_limit_seconds": 60,
        "safety_critical": False,
        "required_ppe": "",
    }


def _render_create_mode() -> None:
    _init_state()
    meta = st.session_state["sb_meta"]

    # ── Header form ────────────────────────────────────────────────────────
    st.subheader("SOP Metadata")
    c1, c2 = st.columns(2)
    meta["id"] = c1.text_input("SOP ID (lowercase, underscores)", value=meta.get("id", ""),
                                help="e.g. motor_wiring_v2")
    meta["name"] = c2.text_input("SOP Name", value=meta.get("name", ""),
                                  help="Human-readable title")
    c3, c4, c5 = st.columns(3)
    meta["version"] = c3.text_input("Version", value=meta.get("version", "1.0"))
    meta["category"] = c4.text_input("Category", value=meta.get("category", ""))
    meta["department"] = c5.text_input("Department", value=meta.get("department", ""))
    meta["estimated_duration_seconds"] = st.number_input(
        "Estimated Duration (seconds)",
        min_value=30, max_value=7200,
        value=int(meta.get("estimated_duration_seconds") or 600),
    )
    meta["required_ppe"] = st.text_input(
        "Required PPE (comma-separated)", value=meta.get("required_ppe", ""),
        help="e.g. safety_glasses, insulated_gloves",
    )

    st.divider()

    # ── Steps ──────────────────────────────────────────────────────────────
    st.subheader("Steps")
    steps: list[dict] = st.session_state["sb_steps"]

    if not steps:
        st.info("No steps yet — click **Add Step** to start building the procedure.")

    for i, step in enumerate(steps):
        with st.container(border=True):
            hcol1, hcol2 = st.columns([4, 1])
            hcol1.markdown(f"**Step {i + 1}**")
            # Action buttons row (kept inline on mobile via .sb-reorder-anchor)
            bcol1, bcol2, bcol3 = hcol2.columns(3)
            bcol1.markdown('<span class="sb-reorder-anchor"></span>', unsafe_allow_html=True)
            if bcol1.button("↑", key=f"sb_up_{i}", disabled=(i == 0), help="Move up"):
                steps[i - 1], steps[i] = steps[i], steps[i - 1]
                st.rerun()
            if bcol2.button("↓", key=f"sb_dn_{i}", disabled=(i == len(steps) - 1), help="Move down"):
                steps[i + 1], steps[i] = steps[i], steps[i + 1]
                st.rerun()
            if bcol3.button("✖", key=f"sb_rm_{i}", help="Delete step"):
                steps.pop(i)
                st.rerun()

            step["name"] = st.text_input("Name", value=step.get("name", ""), key=f"sb_name_{i}")
            step["description"] = st.text_area("Description", value=step.get("description", ""),
                                                key=f"sb_desc_{i}", height=80)
            c1, c2 = st.columns(2)
            step["required_objects"] = c1.text_input("Required Objects (comma-separated)",
                                                      value=step.get("required_objects", ""),
                                                      key=f"sb_obj_{i}")
            step["required_pose"] = c2.text_input("Required Pose",
                                                   value=step.get("required_pose", ""),
                                                   key=f"sb_pose_{i}")
            c3, c4, c5 = st.columns([1, 1, 2])
            step["time_limit_seconds"] = c3.number_input("Time limit (s)",
                                                         min_value=1, max_value=3600,
                                                         value=int(step.get("time_limit_seconds") or 60),
                                                         key=f"sb_tl_{i}")
            step["safety_critical"] = c4.checkbox("Safety-critical",
                                                   value=bool(step.get("safety_critical")),
                                                   key=f"sb_safe_{i}")
            step["required_ppe"] = c5.text_input("PPE for this step (comma-separated)",
                                                  value=step.get("required_ppe", ""),
                                                  key=f"sb_ppe_{i}")

    if st.button("➕ Add Step", use_container_width=True):
        steps.append(_empty_step())
        st.rerun()

    st.divider()

    # ── Build dict for preview / save ─────────────────────────────────────
    def _csv_to_list(v: str) -> list[str]:
        return [x.strip() for x in (v or "").split(",") if x.strip()]

    sop_dict = {
        "id": meta.get("id") or "",
        "name": meta.get("name") or "",
        "version": meta.get("version") or "1.0",
        "category": meta.get("category") or None,
        "department": meta.get("department") or None,
        "estimated_duration_seconds": int(meta.get("estimated_duration_seconds") or 600),
        "required_ppe": _csv_to_list(meta.get("required_ppe", "")),
        "steps": [
            {
                "id": i + 1,
                "name": s.get("name", ""),
                "description": s.get("description", ""),
                "required_objects": _csv_to_list(s.get("required_objects", "")),
                "required_pose": s.get("required_pose") or None,
                "must_follow": [i] if i > 0 else [],   # chain sequentially by default
                "time_limit_seconds": int(s.get("time_limit_seconds") or 60),
                "safety_critical": bool(s.get("safety_critical")),
                "required_ppe": _csv_to_list(s.get("required_ppe", "")),
            }
            for i, s in enumerate(steps)
        ],
    }

    # ── Preview + Save ────────────────────────────────────────────────────
    pc1, pc2 = st.columns(2)
    with pc1:
        if st.button("👁 Preview YAML", use_container_width=True):
            st.session_state["sb_preview"] = yaml.dump({"sop": sop_dict}, allow_unicode=True, sort_keys=False)
    with pc2:
        if st.button("💾 Save SOP", type="primary", use_container_width=True):
            if not sop_dict["id"] or not sop_dict["name"]:
                st.error("SOP ID and Name are required.")
            elif not sop_dict["steps"]:
                st.error("At least one step is required.")
            else:
                result = _post("/api/v1/sops/", sop_dict)
                if result and result.get("ok"):
                    st.success(f"SOP '{sop_dict['id']}' saved successfully!")
                    # Clear local state so the next build starts fresh
                    st.session_state["sb_steps"] = []
                    st.session_state.pop("sb_preview", None)

    if st.session_state.get("sb_preview"):
        with st.expander("YAML Preview", expanded=True):
            st.code(st.session_state["sb_preview"], language="yaml")


def _parse_txt_to_steps(text: str) -> list[dict]:
    """Best-effort parse of a plain-text SOP description into steps.

    Rules (applied in order):
    - Lines starting with a digit + '.' or ')' are treated as step headers.
    - Remaining non-blank lines are appended to the previous step's description.
    - If no numbered lines are found, each non-blank line becomes one step.
    """
    import re
    step_pattern = re.compile(r"^\s*(\d+)[.)]\s+(.+)")
    steps: list[dict] = []
    current: dict | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = step_pattern.match(raw)
        if m:
            if current:
                steps.append(current)
            current = {**_empty_step(), "name": m.group(2)[:80], "description": m.group(2)}
        elif current:
            current["description"] = (current["description"] + " " + line).strip()
        else:
            current = {**_empty_step(), "name": line[:80], "description": line}

    if current:
        steps.append(current)

    # Fallback: if nothing parsed, split on blank lines
    if not steps and text.strip():
        for line in text.splitlines():
            if line.strip():
                steps.append({**_empty_step(), "name": line.strip()[:80], "description": line.strip()})

    return steps


def _render_upload_mode() -> None:
    st.subheader("Upload SOP Document")
    st.caption(
        "Upload a **.txt** description (parsed locally) or a PDF/Word file "
        "(sent to the LLM parser endpoint — requires LLM configured in Settings)."
    )

    f = st.file_uploader("Choose a file", type=["txt", "pdf", "doc", "docx"], key="sb_upload")
    if not f:
        return

    st.info(f"Selected: **{f.name}** ({round(len(f.getvalue()) / 1024, 1)} KB)")

    if st.button("Parse & Populate Steps", type="primary"):
        _init_state()

        if f.name.lower().endswith(".txt"):
            # Client-side text parsing — no API call, no 404 risk
            text = f.getvalue().decode("utf-8", errors="replace")
            parsed = _parse_txt_to_steps(text)
            if not parsed:
                st.warning("Could not extract any steps from the file. Check the format.")
                return
            st.session_state["sb_steps"] = parsed
            st.success(f"Parsed **{len(parsed)}** step(s) from text — review below and switch to **Create New** mode to edit and save.")
            st.rerun()
        else:
            # Try the optional LLM SOP parser endpoint
            try:
                with httpx.Client(timeout=60.0) as c:
                    files = {"file": (f.name, f.getvalue(), f.type)}
                    r = c.post(f"{_api_base()}/api/v1/llm-sop-parser/parse", files=files)
                    if r.status_code == 200:
                        st.success("Parsed successfully — review and save below.")
                        st.json(r.json())
                        return
                    if r.status_code == 404:
                        st.warning(
                            "LLM parser endpoint not enabled. "
                            "Configure an LLM in Settings and restart the backend, "
                            "or upload a **.txt** file for offline parsing."
                        )
                        return
                    st.error(f"Parser returned {r.status_code}: {r.text}")
            except Exception as exc:
                st.warning(f"LLM parser not reachable — upload a .txt file for offline parsing. ({exc})")


def render() -> None:
    mode = st.radio(
        "Mode",
        options=["Create New", "Upload Document"],
        horizontal=True,
        key="sb_mode",
    )
    st.divider()

    if mode == "Create New":
        _render_create_mode()
    else:
        _render_upload_mode()
