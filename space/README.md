---
title: FORGE Vision
emoji: 🏭
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Hybrid CV + GenAI system for real-time employee SOP training
---

# FORGE-Vision

A Hybrid Computer Vision and Generative AI System for Real-Time and
Simulation-Based Employee Training (DBA research project).

This Space runs the FastAPI backend and the Streamlit dashboard in a single
container (see `Dockerfile`). Live camera training uses the **viewer's browser
webcam** via WebRTC; pose estimation (MediaPipe), object detection (YOLOv8n),
and action recognition run server-side, with AI-generated corrective feedback.

## Configuration (Space secrets)

| Secret | Purpose |
|--------|---------|
| `DATABASE_URL` | Supabase Postgres (asyncpg) connection string |
| `SETTINGS_ENCRYPTION_KEY` | Fernet key for encrypted LLM/API keys |
| `JWT_SECRET_KEY` | Auth token signing |
| `SEED_ON_START` | `1` to seed synthetic data on first boot (optional) |
| `TURN_URL` / `TURN_USERNAME` / `TURN_CREDENTIAL` | TURN relay for live camera |

The LLM provider key (e.g. Groq) is entered in the in-app Settings page and
stored encrypted in the database.

> Note: free CPU Spaces run the vision pipeline at a few FPS and sleep after
> ~48h idle. This is a cloud demo; the 2-second latency target applies to edge
> deployment.
