# Enhancements — Project FORGE-Vision

## Overview

This document proposes enhancements to the base FORGE-Vision specification that would increase the system's academic novelty, practical impact, and real-world deployability. Each enhancement is grounded in literature evidence, classified by feasibility, and mapped to its academic contribution value.

Enhancements are prioritised into three tiers:
- **Tier 1 (Core — Recommended for implementation):** High academic novelty, feasible with available resources
- **Tier 2 (Valuable — Include if time permits):** Significant practical value, moderate complexity
- **Tier 3 (Future Work — Document for thesis):** High innovation, require additional resources or partnerships

---

## Tier 1: Core Enhancements (Recommended for Implementation)

### Enhancement 1: LLM-Powered SOP Parser

**What it is:** An automated system that extracts structured SOP action sequences from unstructured text documents (PDF manuals, Word documents, safety guidelines) using a Large Language Model.

**Problem it solves:** Currently, SOPs would need to be manually encoded into JSON/YAML format for the system. Most organisations have SOPs as text documents (or even physical manuals). Manual encoding is time-consuming and error-prone.

**How it works:**
1. Upload PDF/Word SOP document
2. LLM (GPT-4 / Claude) parses the document: identifies steps, required objects, safety precautions, sequence constraints
3. Outputs structured YAML/JSON SOP definition compatible with FORGE-Vision's Intelligence Layer
4. Human reviewer validates and approves the parsed output before deployment

**Example:**
- Input: *"Step 3: Before connecting any wires, ensure the main power isolator is in the OFF position. Verify with a voltage tester. Do not proceed until voltage reads zero."*
- Output: `{step_id: 3, action: "verify_power_off", required_objects: ["voltage_tester", "power_isolator"], safety_check: true, must_verify_before_next: true}`

**Literature grounding:** LLMs have demonstrated strong performance on structured information extraction from technical text (Provenance-Driven Vulnerability Analysis with Automated Retrieval-Augmented LLMs).

**Academic novelty:** Automated SOP digitalisation for training AI systems — not documented in existing literature.

**Implementation effort:** Medium (1–2 weeks with LLM API)

---

### Enhancement 2: Self-Supervised Pre-Training on Unlabelled Industrial Video

**What it is:** Apply BYOL (Bootstrap Your Own Latent) or SimCLR contrastive self-supervised learning to unlabelled workplace video footage before supervised fine-tuning on labelled SOP sequences.

**Problem it solves:** Labelling industrial training video is expensive and requires domain expertise. Many organisations have hours of existing CCTV/production footage that is unlabelled. Self-supervised pre-training unlocks this data.

**How it works:**
1. Collect unlabelled workplace video (from existing CCTV or production cameras, with consent)
2. Apply BYOL framework: augment each video clip into two views; train encoder to produce similar representations for both views without labels
3. Pre-trained encoder captures industrial workplace visual features (worker appearance, equipment, lighting)
4. Fine-tune the pre-trained encoder on a small labelled SOP-action dataset (as few as 10% labelled)

**Literature grounding:** Sun et al. (2024) demonstrate BYOL contrastive self-supervised HAR achieves 95.64% F1 with 10% labelled data on wearable sensor data. FORGE-Vision extends this to video-based industrial HAR.

**Academic novelty:** First application of video self-supervised learning to industrial employee training AI systems.

**Implementation effort:** High (3–4 weeks); requires GPU resources

---

### Enhancement 3: Multi-Modal Feedback (Voice + Visual + Haptic)

**What it is:** Extend feedback delivery from text-only to include:
- **Voice:** Text-to-Speech (TTS) audio instruction through workshop speakers or earpiece
- **Visual:** Bounding box overlay on screen highlighting the error location
- **Haptic (optional):** Wristband vibration alert for safety-critical errors

**Problem it solves:** Workers in manufacturing environments cannot always read a screen (hands full, looking at equipment, safety helmet with face shield). Audio guidance is more natural and accessible.

**How it works:**
- Text feedback from LLM piped to TTS engine (e.g., Google TTS, ElevenLabs)
- OpenCV draws bounding boxes on the live video feed overlay
- Safety-critical errors (MISSING_PPE, UNSAFE_POSTURE) trigger a separate alert through a BLE-connected wristband

**Literature grounding:** Multi-modal feedback proven more effective than single-modality in training contexts. Haptic feedback in safety training: improved reaction time and compliance.

**Academic novelty:** First multi-modal feedback system (voice + visual + haptic) integrated with a CV-based industrial training system.

**Implementation effort:** Medium (TTS: 1 week; bounding box overlay: 2 days; haptic: requires hardware procurement)

---

## Tier 2: Valuable Enhancements

### Enhancement 4: Augmented Reality (AR) Guidance Overlay

**What it is:** Instead of feedback displayed on a separate screen, overlay corrective instructions directly on the worker's field of view using AR glasses or a phone camera AR app.

**Problem it solves:** Separate-screen feedback requires workers to look away from their task. AR overlay maintains visual focus on the work while delivering guidance.

**Technologies:**
- **HoloLens 2 / Meta Quest Pro** — enterprise AR headsets for industrial use
- **WebAR (AR.js / 8th Wall)** — phone-based AR for lower-cost deployment
- **Vuforia** — industrial AR SDK with object tracking

**How it works:**
1. FORGE-Vision backend processes video and generates feedback
2. AR SDK receives feedback payload: `{text, location_x, location_y, severity}`
3. AR overlay renders text/arrows at the relevant position in the worker's field of view (e.g., pointing to the correct terminal)

**Literature grounding:** AR-assisted training in medical education and manufacturing shows measurably faster skill acquisition vs screen-based instruction.

**Academic novelty:** First AR-integrated AI training system for procedural manufacturing tasks.

**Implementation effort:** High (4–6 weeks); requires AR hardware

---

### Enhancement 5: Continual Learning / Online Learning

**What it is:** The system incrementally improves from new workplace footage without full model retraining, using replay buffers and incremental fine-tuning.

**Problem it solves:** As workplaces change (new equipment, new procedures, new workers), a static model becomes less accurate over time. Continual learning keeps the model current without expensive retraining cycles.

**How it works:**
- New video segments are continuously added to a labelled buffer
- When buffer reaches a threshold, incremental fine-tuning is performed (using Elastic Weight Consolidation to prevent catastrophic forgetting)
- Model performance metrics monitored; rollback to previous version if accuracy drops

**Academic novelty:** Application of continual learning to industrial workplace action recognition models.

**Implementation effort:** High (3–4 weeks)

---

### Enhancement 6: Worker Performance Analytics Dashboard (Advanced)

**What it is:** Beyond basic error logs, provide rich analytics with:
- **Competency heatmaps:** Which SOP steps each worker struggles with most
- **Cohort comparison:** How a worker's performance compares to peers (anonymised)
- **Progress trajectories:** Performance trend over multiple sessions
- **Predicted time-to-competency:** ML model predicting when a worker will reach proficiency based on current trajectory
- **Supervisor alerts:** Automated flagging of workers who may need additional support

**Literature grounding:** Analytics-driven training insights proven to guide effective instructor intervention (AI-based Faculty Performance Prediction Systems — adapted to worker context).

**Academic novelty:** Predictive time-to-competency modelling for manufacturing skill acquisition.

**Implementation effort:** Medium (2–3 weeks with PostgreSQL + Streamlit + scikit-learn)

---

### Enhancement 7: Emotion and Stress Recognition

**What it is:** Add facial expression and physiological signal analysis to detect worker frustration, anxiety, or cognitive overload during training, triggering adaptive feedback responses.

**Problem it solves:** A stressed or frustrated worker needs different support than a confident worker making a simple procedural error. Adaptive feedback based on emotional state improves training outcomes.

**How it works:**
- **Facial Action Units (FAUs)** detected via MediaPipe FaceMesh or DeepFace
- Classify emotional state: calm / engaged / frustrated / confused / anxious
- When frustration/anxiety detected: LLM prompt modified to generate simpler, more supportive instruction
- When confidence detected: LLM can provide abbreviated hints rather than full instructions

**Literature grounding:** Emotional state significantly mediates learning outcomes. Adaptive instruction based on learner affect shown to improve retention and reduce dropout.

**Academic novelty:** Affect-aware adaptive feedback in CV-based industrial training — not documented in existing literature.

**Implementation effort:** Medium-High (3–4 weeks for emotion recognition integration)

---

## Tier 3: Future Work (Document in Thesis, Do Not Implement Now)

### Enhancement 8: Digital Twin Integration

**What it is:** Create a photorealistic 3D digital twin of the actual workplace (using Unity or Unreal Engine) so workers train in a virtual replica of their exact workstation before touching real equipment.

**Academic novelty:** Workplace-specific digital twin + AI-guided training — intersection of Digital Twin, IoT, and AI training literature.

**Why future:** Requires 3D scanning of physical workplace, which needs organisational partnerships and significant engineering effort.

---

### Enhancement 9: Multi-Worker Collaborative Training

**What it is:** Track multiple workers simultaneously and detect inter-worker coordination errors (e.g., unsafe handover, simultaneous access to the same equipment, incorrect team assembly sequences).

**Academic novelty:** Group action recognition + multi-agent coordination error detection for manufacturing team training.

**Why future:** Multi-person HAR remains technically challenging; requires additional dataset and training effort beyond Phase A/B scope.

---

### Enhancement 10: Zero-Shot SOP Generalisation

**What it is:** Train the system to recognise SOP deviations for **entirely new tasks** it has never seen before, using only the SOP text description and a small number of demonstration videos.

**Academic novelty:** Zero-shot procedural compliance detection — would significantly reduce deployment cost for new task introduction.

**Why future:** Requires significant advances in few-shot/zero-shot action recognition, likely beyond current DBA timeline.

---

### Enhancement 11: Federated Learning Across Sites

**What it is:** Multiple factories train FORGE-Vision models independently on their local data and share model updates (not raw data) using federated learning, producing a shared global model without data privacy violations.

**Academic novelty:** Federated learning for industrial training AI — enables knowledge sharing across organisations without GDPR violations.

**Why future:** Requires multi-site organisational partnerships and federated learning infrastructure.

---

## Enhancement Implementation Roadmap

| Priority | Enhancement | Phase | Estimated Effort | Academic Novelty | Status |
|----------|------------|-------|-----------------|-----------------|--------|
| **T1** | LLM-Powered SOP Parser | Phase 1 | Medium (2 weeks) | High | ✅ **Implemented** |
| **T1** | Self-Supervised Pre-Training | Phase 2 | High (4 weeks) | Very High | 📋 Documented (future work) |
| **T1** | Multi-Modal Feedback (Voice) | Phase 3 | Medium (1 week) | Medium | ✅ **Implemented** |
| **T2** | AR Overlay | Phase 3+ | High (6 weeks + hardware) | Very High | 📋 Documented (future work) |
| **T2** | Continual Learning | Phase 4 | High (4 weeks) | High | 📋 Documented (future work) |
| **T2** | Advanced Analytics Dashboard | Phase 4 | Medium (3 weeks) | Medium | ✅ **Implemented** |
| **T2** | Emotion/Stress Recognition | Phase 4 | High (4 weeks) | Very High | ✅ **Implemented** |
| **T3** | Digital Twin | Future | Very High | Very High | 📋 Future work |
| **T3** | Multi-Worker Training | Future | Very High | High | 📋 Future work |
| **T3** | Zero-Shot Generalisation | Future | Very High | Very High | 📋 Future work |
| **T3** | Federated Learning | Future | Very High | High | 📋 Future work |

---

## Implemented Enhancement Details

### Enhancement 1 — LLM-Powered SOP Parser ✅
**File:** `src/simulation/llm_sop_parser.py`
- Accepts raw procedure text and produces structured YAML/JSON SOP compatible with the SOP schema
- Supports OpenAI, Anthropic, Groq, and Ollama providers via the shared LLM provider abstraction
- Validated output through Pydantic schema before acceptance
- Human-review gate enforced (parsed output not auto-deployed without approval)

### Enhancement 3 — Multi-Modal Feedback (TTS Voice) ✅
**File:** `src/realtime/tts_engine.py`
- Offline text-to-speech using `pyttsx3` — no internet required, privacy-preserving
- Configurable voice rate, volume, and enable/disable toggle per session
- Integrated into `SessionManager` — LLM corrective feedback automatically spoken aloud
- Non-blocking: runs in a separate thread to avoid blocking the CV inference loop

### Enhancement 6 — Advanced Analytics Dashboard + Competency Predictor ✅
**Files:** `src/intelligence/competency_predictor.py`, `src/ui/pages/analytics_page.py`
- Exponential smoothing on per-session deviation rates models the learning curve
- Linear extrapolation gives sessions-to-competency estimate; capped at 50
- Trend classification: improving / plateau / regressing
- Full Streamlit analytics dashboard: session history, worker performance charts, SOP breakdown, deviation heatmap
- Persisted to `WorkerProfile.sessions_to_competency_est` in PostgreSQL

### Enhancement 7 — Emotion and Stress Recognition ✅
**File:** `src/cv_pipeline/emotion_detector.py`
- MediaPipe FaceMesh 468-point landmark detection
- Three geometric ratios: Eye Aspect Ratio (EAR, fatigue), Brow Raise Ratio (stress), Mouth Aspect Ratio (surprise)
- Heuristic classifier → AffectiveState: FOCUSED / STRESSED / FATIGUED / NEUTRAL / UNKNOWN
- Graceful degradation: returns UNKNOWN if mediapipe not installed
- GDPR compliant: only numeric ratios stored, no facial images persisted (Rules.md §2)

---

## Why These Enhancements Matter for the DBA Thesis

A DBA thesis requires both **practical contribution** (real-world impact) and **academic contribution** (novel knowledge). The Tier 1 and Tier 2 enhancements each add one or both:

| Enhancement | Practical Contribution | Academic Contribution |
|------------|----------------------|----------------------|
| SOP Parser | Reduces deployment time from weeks to hours | Novel: automated SOP digitalisation for training AI |
| Self-Supervised Pre-Training | Dramatically reduces dataset cost | Novel: first application to industrial training video |
| Multi-Modal Feedback | Improves training effectiveness | Empirical: measures which modalities improve outcomes |
| AR Overlay | Most natural training UX | Novel: first AR + AI training system for manufacturing |
| Continual Learning | System stays current as workplace changes | Novel: online learning for industrial HAR |
| Emotion Recognition | Personalised adaptive instruction | Novel: affect-aware industrial training AI |
