# CLAUDE.md — Project FORGE-Vision

## Project Identity

**Project Name:** FORGE-Vision — A Hybrid Computer Vision and Generative AI System for Real-Time and Simulation-Based Employee Training  
**Research Context:** DBA (Doctor of Business Administration)  
**Researcher:** Prof. Dr. Karim Mohammed Rezaul  
**Domain:** AI-based Training for Employees  
**Academic Level:** DBA — all work must meet doctoral research standards

---

## Project Overview

FORGE-Vision is a hybrid AI system that:
1. **Phase A (Simulation):** Trains and validates AI models using synthetic/simulated video scenarios
2. **Phase B (Real-Time):** Deploys the trained system with live camera feeds for real workplace training

The system monitors workers executing tasks, detects deviations from Standard Operating Procedures (SOPs), and delivers instant, personalised AI-generated corrective guidance.

---

## Technology Stack

### Computer Vision Pipeline
- **OpenCV** — video preprocessing, frame extraction, image augmentation
- **MediaPipe Holistic / BlazePose** — real-time pose estimation (33 body landmarks)
- **YOLOv8 / YOLOv9** — object detection (tools, PPE, workspace elements)
- **SlowFast / ViT / CNN+LSTM** — action recognition and temporal sequence modelling

### Deep Learning Framework
- **PyTorch** (primary) — model training, fine-tuning, inference
- **HuggingFace Transformers** — Vision Transformers, LLMs
- **TorchVision** — video datasets, transforms

### Generative AI / LLM
- **OpenAI GPT-4 / Claude API / LLaMA (local)** — real-time feedback generation
- LLM receives structured context: `{detected_error, current_step, SOP_step, worker_history}` → generates corrective instruction

### Backend & API
- **FastAPI** — REST API for CV pipeline and LLM integration
- **Uvicorn** — ASGI server
- **Pydantic** — data validation and schemas

### Frontend / UI
- **Streamlit** — analytics dashboard and simulation viewer
- **React (optional)** — mobile/web real-time interface
- **WebAR / HoloLens SDK** — AR overlay (enhancement phase)

### Simulation Tools
- **Unity / Unreal Engine** — 3D workplace simulation for Phase A
- **OpenCV augmentation pipelines** — video augmentation (flip, rotate, noise, brightness)
- **Synthetic Data Vault (SDV) / custom scripts** — tabular performance data generation

### Data & Storage
- **PostgreSQL** — structured data (worker profiles, SOP definitions, performance logs)
- **AWS S3 / Azure Blob** — video storage
- **MLflow** — experiment tracking, model versioning
- **DVC** — data version control

### Infrastructure
- **Docker / Docker Compose** — containerised deployment
- **NVIDIA CUDA** — GPU acceleration for training
- **Edge device (NVIDIA Jetson / Raspberry Pi 5)** — edge inference for Phase B

---

## How to Approach Work on This Project

### Before Writing Any Code
1. Read the relevant existing file(s) first — never modify blindly
2. Understand which phase (A: simulation or B: real-time) the change belongs to
3. Check if an existing utility, model, or function already handles the requirement

### Code Quality Rules
- Follow `Rules.md` for all technical, ethical, and academic standards
- No speculative features — implement only what is required by the current phase
- No hardcoded credentials, API keys, or file paths — use `.env` and `config.yaml`
- Model weights are **never** committed to git — store in `models/` directory (gitignored)

### Simulation-First Principle
- All CV models must be validated on simulated data **before** deployment with live cameras
- Phase A must be complete and documented before Phase B begins
- Simulation scenarios must cover: correct execution, missing steps, wrong sequence, unsafe behaviour, rare/critical failures

### Research Rigour
- Every experiment must be reproducible: fix random seeds, log configs, version datasets
- Comparisons must be made against a baseline (traditional training method)
- Results documented in structured format for DBA thesis chapters

---

## Key Constraints

| Constraint | Details |
|-----------|---------|
| GDPR Compliance | No real worker biometric data stored without explicit consent |
| Explainability | Every error detection must explain WHAT was wrong and WHY |
| Edge Compatibility | Phase B models must run on NVIDIA Jetson / equivalent (≤10W) |
| Latency | Real-time feedback must be delivered within 2 seconds of error detection |
| Academic Integrity | No fabricated results; synthetic data clearly labelled as synthetic |
| Privacy | Video streams processed in-memory; not persisted unless consent given |

---

## Project File Structure

```
DBA Project/
├── CLAUDE.md                    # This file
├── Architecture.md              # System design
├── Rules.md                     # Governance rules
├── LiteratureReview.md          # Academic literature synthesis
├── GapsAnalysis.md              # Research gaps
├── Enhancements.md              # Innovation proposals
│
├── src/
│   ├── simulation/              # Phase A: simulation pipeline
│   ├── cv_pipeline/             # Computer vision: pose, detection, recognition
│   ├── intelligence/            # SOP matching, error detection, LLM feedback
│   ├── api/                     # FastAPI backend
│   └── ui/                      # Streamlit dashboard
│
├── data/
│   ├── sops/                    # SOP definitions (JSON/YAML)
│   ├── synthetic/               # Generated training videos
│   └── real/                    # Real workplace videos (gitignored)
│
├── models/                      # Trained model weights (gitignored)
├── experiments/                 # MLflow experiment logs
├── tests/                       # Unit and integration tests
├── notebooks/                   # Jupyter notebooks for exploration/analysis
├── config/                      # Configuration files
├── Literature Review/           # Source research papers
└── requirements.txt
```

---

## Research Hypotheses (to validate through implementation)

- **H1:** Employees trained using FORGE-Vision will achieve a statistically significant reduction in task error rates compared to traditional training (p < 0.05)
- **H2:** The hybrid (simulation → real-time) approach will produce better skill transfer than simulation-only or real-time-only methods
- **H3:** AI-generated real-time feedback will significantly reduce task completion time compared to post-hoc feedback
