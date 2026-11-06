"""
FORGE-Vision Settings Page — LLM Provider Configuration.
Professional redesign with card-based provider selection and clean layout.
"""
import importlib

import streamlit as st
from src.ui.utils import api_delete, api_get, api_post


# ── CSS ───────────────────────────────────────────────────────────────────

_CSS = """
<style>
/* ── Page header ── */
.settings-header {
    padding: 1.5rem 0 0.5rem 0;
    border-bottom: 2px solid #e2e8f0;
    margin-bottom: 1.5rem;
}
.settings-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1a202c;
    margin: 0;
    letter-spacing: -0.02em;
}
.settings-subtitle {
    font-size: 0.9rem;
    color: #718096;
    margin-top: 0.25rem;
}

/* ── Section labels ── */
.section-label {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #a0aec0;
    margin-bottom: 0.75rem;
    margin-top: 1.5rem;
}

/* ── Provider cards ── */
.provider-card {
    border: 2px solid #e2e8f0;
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.15s ease;
    background: #ffffff;
    min-height: 90px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.35rem;
}
.provider-card:hover {
    border-color: #667eea;
    box-shadow: 0 4px 12px rgba(102,126,234,0.15);
}
.provider-card.active {
    border-color: #667eea;
    background: linear-gradient(135deg, #f0f4ff 0%, #e8ecff 100%);
    box-shadow: 0 4px 16px rgba(102,126,234,0.2);
}
.provider-icon { font-size: 1.5rem; }
.provider-name { font-size: 0.8rem; font-weight: 600; color: #2d3748; }
.provider-badge {
    font-size: 0.65rem;
    padding: 0.1rem 0.45rem;
    border-radius: 20px;
    font-weight: 600;
}
.badge-free { background: #c6f6d5; color: #276749; }
.badge-paid { background: #e2e8f0; color: #4a5568; }
.badge-local { background: #bee3f8; color: #2c5282; }

/* ── Config card ── */
.config-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin: 0.75rem 0;
}

/* ── Active config banner ── */
.active-banner {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    color: white;
    margin-bottom: 1.5rem;
}
.active-banner-title {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    opacity: 0.8;
    margin-bottom: 0.5rem;
}
.active-banner-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
}
.active-banner-provider {
    font-size: 1.1rem;
    font-weight: 700;
}
.active-banner-model {
    font-family: monospace;
    font-size: 0.85rem;
    background: rgba(255,255,255,0.2);
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
}
.active-banner-status-ok {
    background: rgba(72,187,120,0.3);
    border: 1px solid rgba(72,187,120,0.5);
    color: #f0fff4;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 600;
}
.active-banner-status-warn {
    background: rgba(237,137,54,0.3);
    border: 1px solid rgba(237,137,54,0.5);
    color: #fffaf0;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 600;
}

/* ── Saved config cards ── */
.saved-card {
    border: 1.5px solid #e2e8f0;
    border-radius: 10px;
    padding: 0.9rem 1rem;
    background: #ffffff;
    position: relative;
}
.saved-card.is-active {
    border-color: #667eea;
    background: #f0f4ff;
}
.saved-card-provider { font-size: 0.75rem; font-weight: 700; color: #4a5568; }
.saved-card-model { font-family: monospace; font-size: 0.8rem; color: #2d3748; margin: 0.2rem 0; }
.saved-card-tag {
    display: inline-block;
    font-size: 0.63rem;
    font-weight: 700;
    padding: 0.1rem 0.4rem;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.tag-active { background: #ebf4ff; color: #3182ce; }
.tag-tested { background: #c6f6d5; color: #276749; }
.tag-untested { background: #fefcbf; color: #975a16; }

/* ── Key input area ── */
.key-hint {
    font-size: 0.78rem;
    color: #718096;
    margin-top: 0.3rem;
    padding: 0.5rem 0.75rem;
    background: #f7fafc;
    border-radius: 6px;
    border-left: 3px solid #667eea;
}

/* ── Action bar ── */
.action-bar {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin: 1rem 0;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

/* ── Cost table ── */
.cost-row-free { color: #276749; font-weight: 600; }
</style>
"""


# ── API helpers ───────────────────────────────────────────────────────────

def _api_get(path: str) -> dict | None:
    return api_get(path)


def _api_post(path: str, body: dict) -> dict | None:
    return api_post(path, body, timeout=30.0)


def _api_delete(path: str) -> bool:
    return api_delete(path)


# ── Provider metadata ─────────────────────────────────────────────────────

_PROVIDER_META = {
    "groq":      {"icon": "⚡", "short": "Groq",      "badge": "free",  "badge_label": "Free"},
    "gemini":    {"icon": "🌟", "short": "Gemini",     "badge": "free",  "badge_label": "Free"},
    "openai":    {"icon": "🤖", "short": "OpenAI",     "badge": "paid",  "badge_label": "Paid"},
    "anthropic": {"icon": "🧠", "short": "Claude",     "badge": "paid",  "badge_label": "Paid"},
    "xai":       {"icon": "✦",  "short": "xAI Grok",  "badge": "paid",  "badge_label": "Paid"},
    "ollama":    {"icon": "🏠", "short": "Ollama",     "badge": "local", "badge_label": "Local"},
}

_KEY_LINKS = {
    "xai":       "https://console.x.ai/",
    "openai":    "https://platform.openai.com/api-keys",
    "groq":      "https://console.groq.com/keys",
    "anthropic": "https://console.anthropic.com/settings/keys",
    "gemini":    "https://aistudio.google.com/app/apikey",
}


# ── Page ──────────────────────────────────────────────────────────────────

def render():
    import src.intelligence.llm_providers as _llm_mod
    importlib.reload(_llm_mod)
    PROVIDER_LABELS = _llm_mod.PROVIDER_LABELS
    PROVIDER_MODELS = _llm_mod.PROVIDER_MODELS

    st.markdown(_CSS, unsafe_allow_html=True)

    # ── Header ─────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="settings-header">
        <p class="settings-title">⚙️ LLM Configuration</p>
        <p class="settings-subtitle">Choose and connect the AI model that generates real-time training feedback for workers.</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Load data ──────────────────────────────────────────────────────────
    current    = _api_get("/api/v1/settings")
    all_configs = _api_get("/api/v1/settings/all") or []

    # ── Active config banner ───────────────────────────────────────────────
    if current:
        meta        = _PROVIDER_META.get(current["provider"], {"icon": "🤖", "short": current["provider"]})
        status_html = (
            '<span class="active-banner-status-ok">✅ Tested &amp; Connected</span>'
            if current["tested_ok"] else
            '<span class="active-banner-status-warn">⚠️ Not Yet Tested</span>'
        )
        last_updated = current.get("updated_at", "")[:16].replace("T", " ") + " UTC" if current.get("updated_at") else ""
        st.markdown(f"""
        <div class="active-banner">
            <div class="active-banner-title">Active Configuration</div>
            <div class="active-banner-row">
                <span class="active-banner-provider">{meta['icon']} {PROVIDER_LABELS.get(current['provider'], current['provider'])}</span>
                <span class="active-banner-model">{current['model_name']}</span>
                {status_html}
            </div>
            <div style="margin-top:0.5rem; font-size:0.75rem; opacity:0.7;">Last updated: {last_updated}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Saved configurations quick-switch ──────────────────────────────────
    if len(all_configs) > 1:
        st.markdown('<p class="section-label">Saved Configurations</p>', unsafe_allow_html=True)

        cols = st.columns(min(len(all_configs), 4))
        for i, cfg in enumerate(all_configs):
            with cols[i % 4]:
                meta        = _PROVIDER_META.get(cfg["provider"], {"icon": "🤖", "short": cfg["provider"]})
                is_active   = cfg["is_active"]
                card_class  = "saved-card is-active" if is_active else "saved-card"
                active_tag  = '<span class="saved-card-tag tag-active">● Active</span> ' if is_active else ""
                tested_tag  = '<span class="saved-card-tag tag-tested">✓ Tested</span>' if cfg["tested_ok"] else '<span class="saved-card-tag tag-untested">⚠ Untested</span>'
                provider_lbl = PROVIDER_LABELS.get(cfg["provider"], cfg["provider"])

                st.markdown(f"""
                <div class="{card_class}">
                    <div class="saved-card-provider">{meta['icon']} {provider_lbl}</div>
                    <div class="saved-card-model">{cfg['model_name']}</div>
                    <div style="margin-top:0.4rem;">{active_tag}{tested_tag}</div>
                </div>
                """, unsafe_allow_html=True)

                if not is_active:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Activate", key=f"switch_{cfg['id']}", use_container_width=True, type="primary"):
                            if _api_post(f"/api/v1/settings/{cfg['id']}/activate", {}):
                                st.rerun()
                    with c2:
                        if st.button("Delete", key=f"del_{cfg['id']}", use_container_width=True):
                            if _api_delete(f"/api/v1/settings/{cfg['id']}"):
                                st.rerun()
                else:
                    if st.button("Remove", key=f"del_{cfg['id']}", use_container_width=True):
                        if _api_delete(f"/api/v1/settings/{cfg['id']}"):
                            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

    # ── Provider picker ────────────────────────────────────────────────────
    st.markdown('<p class="section-label">Select Provider</p>', unsafe_allow_html=True)

    provider_options = list(PROVIDER_LABELS.keys())
    saved_provider   = current.get("provider") if current else None

    # Track selected provider in session state
    if "selected_provider" not in st.session_state:
        st.session_state["selected_provider"] = saved_provider or provider_options[0]
    if st.session_state["selected_provider"] not in provider_options:
        st.session_state["selected_provider"] = provider_options[0]

    # Render provider cards as clickable buttons
    card_cols = st.columns(len(provider_options))
    for i, p in enumerate(provider_options):
        meta  = _PROVIDER_META.get(p, {"icon": "🤖", "short": p, "badge": "paid", "badge_label": "Paid"})
        is_sel = st.session_state["selected_provider"] == p
        badge_class = f"badge-{meta['badge']}"
        border = "2px solid #667eea" if is_sel else "2px solid #e2e8f0"
        bg     = "linear-gradient(135deg,#f0f4ff,#e8ecff)" if is_sel else "#ffffff"

        with card_cols[i]:
            st.markdown(f"""
            <div style="border:{border};border-radius:12px;padding:0.85rem 0.5rem;
                        text-align:center;background:{bg};
                        box-shadow:{'0 4px 16px rgba(102,126,234,0.18)' if is_sel else 'none'};
                        margin-bottom:0.25rem;">
                <div style="font-size:1.4rem;">{meta['icon']}</div>
                <div style="font-size:0.78rem;font-weight:700;color:#2d3748;margin:0.2rem 0;">{meta['short']}</div>
                <span style="font-size:0.63rem;padding:0.1rem 0.45rem;border-radius:20px;font-weight:700;"
                      class="{badge_class}">{meta['badge_label']}</span>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Select" if not is_sel else "✓ Selected",
                         key=f"pick_{p}",
                         use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                st.session_state["selected_provider"] = p
                st.rerun()

    provider = st.session_state["selected_provider"]

    # ── Configuration form ─────────────────────────────────────────────────
    st.markdown('<p class="section-label">Configure</p>', unsafe_allow_html=True)

    api_key_input   = None
    ollama_url_input = None
    model_input     = None

    with st.container():
        st.markdown('<div class="config-card">', unsafe_allow_html=True)

        if provider != "ollama":
            model_options = [m[0] for m in PROVIDER_MODELS[provider]]
            model_labels  = {m[0]: m[1] for m in PROVIDER_MODELS[provider]}

            saved_model       = current.get("model_name") if current and current.get("provider") == provider else None
            default_model_idx = model_options.index(saved_model) if saved_model in model_options else 0

            col_model, col_badge = st.columns([3, 1])
            with col_model:
                model_input = st.selectbox(
                    "Model",
                    options=model_options,
                    format_func=lambda m: model_labels[m],
                    index=default_model_idx,
                    key="model_select_ext",
                )
            with col_badge:
                st.markdown("<br>", unsafe_allow_html=True)
                label = model_labels.get(model_input, "")
                if "Free" in label:
                    st.success("Free Tier")
                elif "cheap" in label.lower() or "mini" in label.lower():
                    st.info("Low Cost")
                else:
                    st.warning("Paid")

            # API Key row
            st.markdown("<br>", unsafe_allow_html=True)
            show_key  = st.session_state.get("show_key", False)
            key_col, vis_col = st.columns([6, 1])
            with key_col:
                api_key_input = st.text_input(
                    "API Key",
                    type="default" if show_key else "password",
                    placeholder="Paste your API key here  (leave blank to reuse saved key)",
                    value="",
                    key="api_key_input",
                )
            with vis_col:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("👁" if not show_key else "🙈", key="toggle_key", help="Show / hide key"):
                    st.session_state["show_key"] = not show_key
                    st.rerun()

            # Saved key hint
            saved_cfg_for_provider = next(
                (c for c in all_configs if c["provider"] == provider and c.get("api_key_masked")), None
            )
            if saved_cfg_for_provider and not api_key_input:
                st.markdown(
                    f'<div class="key-hint">🔐 Using saved key: <code>{saved_cfg_for_provider["api_key_masked"]}</code>'
                    f'  —  leave blank to reuse, or paste a new key to replace it</div>',
                    unsafe_allow_html=True,
                )
            elif provider in _KEY_LINKS:
                st.markdown(
                    f'<div class="key-hint">🔑 Get your free API key → '
                    f'<a href="{_KEY_LINKS[provider]}" target="_blank">{_KEY_LINKS[provider]}</a></div>',
                    unsafe_allow_html=True,
                )

        else:
            # Ollama form
            col_url, col_btn = st.columns([3, 1])
            with col_url:
                ollama_url_input = st.text_input(
                    "Ollama Base URL",
                    value=(current or {}).get("ollama_base_url") or "http://host.docker.internal:11434",
                    key="ollama_url_input",
                )
            with col_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                fetch_clicked = st.button("🔄 Fetch Models", key="fetch_models", use_container_width=True)

            if fetch_clicked:
                with st.spinner("Connecting to Ollama..."):
                    result = _api_get(f"/api/v1/settings/ollama-models?base_url={ollama_url_input}")
                    if result:
                        st.session_state["ollama_models"] = result["models"]
                        st.success(f"Found {len(result['models'])} installed model(s)")

            ollama_models = st.session_state.get("ollama_models", [])

            if ollama_models:
                search = st.text_input(
                    "Filter models",
                    placeholder="Type to search — llama, deepseek, qwen...",
                    key="ollama_model_search",
                )
                filtered = [m for m in ollama_models if search.lower() in m.lower()] if search else ollama_models
                if not filtered:
                    st.warning(f"No models match '{search}'")
                    filtered = ollama_models

                saved_ollama_m   = (current or {}).get("model_name") if (current or {}).get("provider") == "ollama" else None
                saved_ollama_idx = filtered.index(saved_ollama_m) if saved_ollama_m in filtered else 0

                model_input = st.selectbox(
                    f"Model  ({len(filtered)} of {len(ollama_models)} installed)",
                    options=filtered,
                    index=saved_ollama_idx,
                    key="model_select_ollama",
                )
            else:
                model_input = st.text_input(
                    "Model Name",
                    value=(current or {}).get("model_name") if (current or {}).get("provider") == "ollama" else "llama3.1:8b",
                    placeholder="e.g. llama3.1:8b",
                    key="model_manual_ollama",
                )
                st.caption("Click **Fetch Models** above, or type manually: `llama3.1:8b` · `deepseek-r1:latest` · `phi3:mini`")

            st.markdown(
                '<div class="key-hint">🏠 <strong>100% local</strong> — no API key needed, '
                'no data leaves your machine. GDPR-safe for real worker sessions.</div>',
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

    # ── Action buttons ─────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    has_saved_key = any(
        cfg.get("provider") == provider and cfg.get("api_key_masked")
        for cfg in all_configs
    )

    btn_c1, btn_c2, btn_c3 = st.columns([1.2, 1.2, 2])
    with btn_c1:
        test_clicked = st.button("🔌  Test Connection", type="secondary", use_container_width=True, key="test_btn")
    with btn_c2:
        save_clicked = st.button("💾  Save Settings", type="primary", use_container_width=True, key="save_btn")
    with btn_c3:
        if current:
            tested = current.get("tested_ok", False)
            prov   = PROVIDER_LABELS.get(current["provider"], current["provider"])
            if tested:
                st.success(f"✅  {prov}  ·  {current['model_name']}  is active & connected")
            else:
                st.warning(f"⚠️  {prov}  ·  {current['model_name']}  — run Test Connection")

    # ── Handle Test ────────────────────────────────────────────────────────
    if test_clicked:
        if not model_input:
            st.warning("Please select or enter a model name.")
        elif provider != "ollama" and not api_key_input and not has_saved_key:
            st.warning("Please enter an API key to test.")
        else:
            with st.spinner("Testing connection..."):
                result = _api_post("/api/v1/settings/test", {
                    "provider": provider,
                    "model_name": model_input,
                    "api_key": api_key_input if api_key_input else None,
                    "ollama_base_url": ollama_url_input,
                })
            if result:
                if result["success"]:
                    latency = result.get("latency_ms")
                    lat_str = f"  ·  {latency:.0f} ms" if latency else ""
                    st.success(f"✅  {result['message']}{lat_str}")
                    st.session_state["last_test_ok"] = True
                    st.rerun()
                else:
                    st.error(f"❌  {result['message']}")
                    st.session_state["last_test_ok"] = False

    # ── Handle Save ────────────────────────────────────────────────────────
    if save_clicked:
        if not model_input:
            st.warning("Please select or enter a model name.")
        elif provider != "ollama" and not api_key_input and not has_saved_key:
            st.warning("Please enter an API key before saving.")
        else:
            body = {
                "provider": provider,
                "model_name": model_input,
                "ollama_base_url": ollama_url_input if provider == "ollama" else None,
                "api_key": api_key_input if api_key_input else None,
            }
            with st.spinner("Saving..."):
                result = _api_post("/api/v1/settings", body)
            if result:
                st.success("✅  Settings saved — this provider will be used for all feedback generation.")
                st.session_state.pop("ollama_models", None)
                st.rerun()

    # ── Cost & provider guide ──────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("💰  Provider Comparison — Cost & Quality Guide"):
        st.markdown("""
| Provider | Cost (10 sessions) | Cost / month | Speed | Best for |
|---|---|---|---|---|
| ⚡ **Groq** | **Free** | **Free** | ⚡⚡⚡ Fastest | Research & demos |
| 🌟 **Gemini Flash** | **Free** | **Free** | ⚡⚡ Fast | Research & demos |
| 🤖 **GPT-4o Mini** | ~£0.01 | ~£0.11 | ⚡⚡ Fast | Production (affordable) |
| 🧠 **Claude Haiku** | ~£0.02 | ~£0.20 | ⚡⚡ Fast | High-quality feedback |
| 🤖 **GPT-4o** | ~£0.22 | ~£2.19 | ⚡ Moderate | Best quality |
| 🏠 **Ollama** | **£0** | **~£0** | ⚡⚡ Fast | GDPR / offline / production |

> **DBA Research:** Use **Groq** (free, fast) · **Production with real workers:** Use **Ollama** (GDPR-safe, on-premise)
        """)

    # ── Demo: Template vs LLM feedback ──────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🧪 Feedback Demo — Template vs LLM")
    st.caption(
        "The CV/ML pipeline decides *what* the deviation is; the LLM only rewrites the "
        "rule-based template into supportive, personalised guidance. Compare them below."
    )
    sops = _api_get("/api/v1/sops/") or []
    if not sops:
        st.info("No SOPs available to run the demo.")
    else:
        dcol, scol = st.columns(2)
        with dcol:
            dev_class = st.selectbox(
                "Deviation type",
                ["MISSING_STEP", "WRONG_ORDER", "INCORRECT_EXECUTION", "MISSING_PPE", "UNSAFE_POSTURE"],
                key="fbdemo_dev",
            )
        with scol:
            sop_by_name = {s["name"]: s for s in sops if isinstance(s, dict) and s.get("name")}
            sop_name = st.selectbox("SOP", list(sop_by_name.keys()), key="fbdemo_sop")

        sop = sop_by_name.get(sop_name, {})
        steps = sop.get("steps") or []
        step = steps[0] if steps else {}

        if st.button("Generate comparison", key="fbdemo_run", type="primary"):
            res = _api_post("/api/v1/feedback/demo", {
                "sop_name": sop_name,
                "deviation_class": dev_class,
                "expected_step_name": step.get("name", ""),
                "expected_step_id": step.get("id", 1),
                "model_confidence": 0.85,
            })
            st.session_state["fbdemo_res"] = res or {}

        res = st.session_state.get("fbdemo_res")
        if res:
            tcol, lcol = st.columns(2)
            with tcol:
                st.markdown("**📋 Rule-based template**")
                st.info(res.get("template_feedback", "—"))
            with lcol:
                prov = res.get("provider") or "no provider"
                mdl = res.get("model") or ""
                st.markdown(f"**🤖 LLM — {prov} {mdl}**".rstrip())
                if res.get("llm_feedback"):
                    st.success(res["llm_feedback"])
                else:
                    st.warning(
                        f"LLM unavailable ({res.get('llm_error') or 'no provider configured'}). "
                        "Configure a provider above — the system falls back to the template."
                    )
