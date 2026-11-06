# LLM Strategy — Zero-Cost, Ollama-First

## Research Principle

FORGE-Vision is a DBA research project with a zero-budget LLM policy:

- **All development, training, and production runs on local Ollama** — zero cost, full data privacy, GDPR-compliant, no internet dependency
- **No paid LLM APIs will be used** at any point in the project
- **Free-tier external providers** (Groq, Gemini) are used only for the Phase 5 academic comparison study, and require no credit card

The system architecture is already provider-agnostic (`src/intelligence/llm_providers.py`) and already defaults to Ollama (`src/config.py: LLM_PROVIDER = "ollama"`). No code changes are needed to operate at zero cost.

---

## 1. Local Ollama Setup

### Install and Start Ollama

```bash
# Download from https://ollama.com — installs as a background service
# Verify it is running:
ollama list
```

### Recommended Models for 6–8 GB VRAM

| Model | VRAM Required | Quality | Speed | When to Use |
|-------|--------------|---------|-------|-------------|
| `llama3.1:8b` | ~5 GB | Good | ~1–2s/response | **Default — recommended for all phases** |
| `llama3.1:8b-instruct-q4_K_M` | ~4.5 GB | Good (minor trade-off) | ~0.8s/response | If VRAM is tight |
| `phi3:mini` | ~3 GB | Adequate | ~0.3s/response | Fastest option; good for real-time feedback |
| `mistral:7b` | ~5 GB | Good | ~1s/response | Alternative to llama3.1:8b |

**NOT feasible on 6–8 GB VRAM:** 13B models, 70B models (require 10–40+ GB VRAM).

### Pull Models

```bash
ollama pull llama3.1:8b           # recommended default
ollama pull phi3:mini             # lightweight alternative for real-time use
ollama pull mistral:7b            # optional alternative
```

### Configuration

No `.env` changes needed — the defaults are already correct:

```bash
# config/.env (defaults — already set in src/config.py)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 2. Why Ollama Throughout All Phases

| Factor | Ollama (Local) |
|--------|---------------|
| Cost | Zero (hardware already owned) |
| GDPR compliance | Full — worker data never leaves the machine |
| Internet dependency | None — works completely offline |
| Rate limits | None — limited only by GPU speed |
| Model version pinning | Exact reproducibility for thesis |
| Fine-tuning on SOP data | Free (using Unsloth / PEFT) |
| Latency | 0.3–2s depending on model and GPU |
| Academic transparency | Model weights publicly auditable |

---

## 3. Phase 5 Comparison Study — Free-Tier External Providers Only

Phase 5 task 5.7 requires a comparison of LLM feedback quality for the DBA thesis. This is
conducted using **free-tier providers only** — no credit card, no cost.

### Free-Tier Providers for Comparison

| Provider | Free Model | Rate Limit | How to Get Key |
|----------|-----------|------------|---------------|
| **Groq** | `llama-3.3-70b-versatile` | 30 req/min | groq.com — sign up, free, no card |
| **Gemini** | `gemini-2.0-flash` | 10 req/min | aistudio.google.com — Google account only |

Both providers are already fully implemented in `src/intelligence/llm_providers.py`.

### Comparison Study Design (Task 5.7)

The study sends identical error prompts to all three systems and has participants rate the feedback:

```
Prompt structure (same for all providers):
  "Worker missed the PPE step before starting the motor wiring task.
   SOP step 2 requires: insulated gloves + safety glasses.
   Worker history: 3 sessions, 2 prior PPE violations.
   Generate a single corrective instruction (max 2 sentences)."
```

**Evaluation dimensions (rated by participants, 1–5 scale):**
1. Relevance — does the feedback address the actual error?
2. Specificity — does it name the correct SOP step and missing item?
3. Actionability — can the worker act on it immediately?
4. Clarity — is the language clear and unambiguous?

**Providers compared:**
- Ollama `llama3.1:8b` (local, 6–8 GB GPU)
- Groq `llama-3.3-70b-versatile` (free tier) — larger model, cloud
- Gemini `gemini-2.0-flash` (free tier) — different architecture, cloud

This comparison contributes to the thesis as a resource efficiency vs feedback quality analysis:
local small model vs large cloud model at zero cost.

### Free-Tier `.env` Configuration (Phase 5 only)

```bash
# Groq free tier
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=your_free_groq_key_here     # from groq.com — no card needed

# Gemini free tier
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.0-flash
GEMINI_API_KEY=your_free_gemini_key_here  # from aistudio.google.com — Google account only
```

Switch back to Ollama for all non-comparison work:

```bash
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
```

---

## 4. Provider Architecture

The system is provider-agnostic by design. Switching providers requires only a one-line `.env`
change — no code modifications:

```
LLM_PROVIDER=ollama    → uses src/intelligence/llm_providers.py OllamaProvider
LLM_PROVIDER=groq      → uses GroqProvider (free tier: 30 req/min)
LLM_PROVIDER=gemini    → uses GeminiProvider (free tier: 10 req/min)
```

The active provider can also be changed at runtime through the Streamlit Settings UI (Phase 0
implementation), which stores the selection in PostgreSQL and allows hot-switching without
restarting the server.

`OLLAMA_BASE_URL` is configurable — if Ollama is running on a different machine on the network
(e.g., a dedicated workstation), set this to that machine's IP address.

---

## 5. Strategy Summary by Phase

| Phase | LLM Provider | Reason |
|-------|-------------|--------|
| Phase 0 — Documentation | None needed | No LLM calls |
| Phase 1 — Simulation | Ollama `llama3.1:8b` | Test feedback generation locally |
| Phase 2 — CV Training | Ollama `llama3.1:8b` | Validate error-to-feedback pipeline |
| Phase 3 — Real-Time Prototype | Ollama `llama3.1:8b` or `phi3:mini` | Live latency; phi3:mini fastest |
| Phase 4 — Full Integration | Ollama `llama3.1:8b` | Production — privacy, zero cost |
| Phase 5 — Academic Evaluation | Ollama + Groq free + Gemini free | Comparison study for task 5.7 only |
