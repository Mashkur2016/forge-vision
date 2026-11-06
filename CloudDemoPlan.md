# FORGE-Vision — Cloud Live-Camera Demo Plan

> **Status:** Approved 2026-06-10. Steps 1–4 are local code changes (verifiable in-browser
> over `localhost`) before any cloud work, which de-risks the deploy.
>
> **Goal:** A free, fully cloud-hosted demo of FORGE-Vision — including **live camera
> training** — with no local machine and no Docker required on the hosting platform.

---

## Why the current Live Training cannot run in the cloud as-is

The camera is opened **server-side** today:

```
UI → POST /api/v1/session/start {camera_source: 0 | http://...}
       → FastAPI opens the camera itself (src/realtime/camera_capture.py)
       → server runs CV inference
       → streams frames + feedback back to the UI over WebSocket
```

`camera_capture.py` calls either `cv2.VideoCapture(0)` (a webcam **physically attached to
the server**) or polls an IP-Webcam HTTP URL. On a cloud host:

- `source=0` → no webcam on the server → fails (degrades to "Manual Mode").
- IP-Webcam URL like `http://10.17.250.127:8080` → a **private LAN address** the cloud
  server cannot reach (phone is behind the user's home router/NAT).

**Fix:** capture the camera at the **viewer's browser** (their laptop/phone webcam) via
WebRTC and send frames *to* the server — not have the server read a camera.

---

## Decisions (locked)

| Topic | Decision |
|---|---|
| Live camera | **`streamlit-webrtc`** — viewer's own browser webcam, lowest latency, no tunnel/local app |
| Hosting | **Hugging Face Docker Space** (free CPU: 2 vCPU / 16 GB) |
| Database | **Supabase** free Postgres (keep Postgres; run Alembic + seeder against it) |
| Model shipping | `models/action_recognizer_best.pth` via **Git LFS** into the Space repo |
| LLM feedback | **Groq (free)**, key entered via the encrypted Settings page after first login |

---

## How the per-frame pipeline maps today

```
bgr_frame
 → InferencePipeline.process_frame()      # FrameProcessor (MediaPipe pose + YOLOv8n) + ActionRecognizer
   → (FrameResult, InferenceResult)
 → SOPDetector.process_frame(...)          # LSTM sequence model → Optional[SOPDeviationEvent]
   → if event.requires_llm_feedback: feedback_fn(event)   # LLM corrective text
```

`session_manager._process_loop()` wraps this with **server-side camera reads** + an asyncio
queue → WebSocket. For WebRTC we keep the middle (CV/intelligence layers) and replace the
**input** (camera) and **output** (queue) ends.

---

## Part 1 — Code changes

### 1.1 Extract a shared per-frame processor — `src/realtime/frame_pipeline.py` (new)
Pull the three-step logic out of `_process_loop` into one reusable, camera-free, queue-free,
async-free class so both the existing WebSocket path and the new WebRTC path use identical
inference:

```python
class RealtimeFramePipeline:
    def __init__(self, sop, sequence_model, inference_config=None, detector_config=None, session_id=...): ...
    def load(self) -> "RealtimeFramePipeline": ...      # build InferencePipeline + load_model; build + start SOPDetector
    def process(self, bgr) -> FramePipelineResult: ...   # (frame_result, inference, event)
    def end_session(self) -> list[SOPDeviationEvent]: ...
    def session_summary(self) -> dict: ...
    def close(self) -> None: ...
```
Refactor `session_manager` to use it — **no behaviour change locally**, just deduplication
(keeps the Docker/edge path intact).

### 1.2 WebRTC video processor — `src/ui/webrtc_live.py` (new)
A `streamlit-webrtc` `VideoProcessorBase` whose `recv(frame)`:
1. converts `av.VideoFrame` → BGR ndarray (downscaled, e.g. 480p, for CPU),
2. calls `RealtimeFramePipeline.process()`,
3. **draws the overlay** (pose landmarks + YOLO boxes + step badge) onto the frame,
4. returns the annotated frame → rendered live in the browser,
5. pushes any `SOPDeviationEvent` into a **thread-safe `deque`** (the `recv` thread must not
   touch `st.session_state` or call async code).

### 1.3 Overlay drawing — `src/cv_pipeline/annotate.py` (new)
Draw from `FrameResult.pose.landmarks` (33 points) and `FrameResult.detections.detections`
(boxes/labels). This is what makes the demo visually convincing — the viewer sees themselves
with skeleton + detected tools/PPE.

### 1.4 LLM feedback off the frame thread
`recv()` stays pure-CV. The main Streamlit script (existing ~1 Hz auto-rerun) drains the
deviation deque and fetches corrective text. To reuse the DB-stored, encrypted LLM keys, add:

- **`POST /api/v1/feedback/from-deviation`** in a small `src/api/routes/feedback.py`, wrapping
  `generate_training_feedback(...)`. The UI posts the deviation payload, gets back
  `{feedback_text, severity, ...}`, and renders the existing feedback card.

### 1.5 Rework `src/ui/pages/live_training_page.py`
- Replace the **"Camera Feed" column** (base64 frames over WS) with `webrtc_streamer(...)`.
- Keep: GDPR consent gate, SOP selector, step-by-step controls, timers, summary, DB persist.
- Drop the `camera_source` text box (camera is now the browser).
- On stop, persist the step log + deviations via the existing `/session/{id}/stop` path so the
  dashboard still gets data.

### 1.6 Model & asset availability (deployment-critical)
- `models/action_recognizer_best.pth` is gitignored → ship via **Git LFS** into the Space.
- `yolov8n.pt` auto-downloads via ultralytics → **pre-download in the Docker build**.
- MediaPipe task files download at runtime (fine; HF has internet).
- Load heavy models **once** via `@st.cache_resource`; hand them to the processor.

---

## Part 2 — Dependencies (`requirements-web.txt`)
```
streamlit-webrtc==0.47.*     # pulls aiortc, av, aioice, pylibsrtp
```
If the build complains, add system libs to the Dockerfile: `ffmpeg libsrtp2-dev`
(already installing `libgl1`, `libglib2.0-0`). The web image already has
`torch==2.4.0+cpu`, `mediapipe`, `ultralytics`.

---

## Part 3 — Deployment (Hugging Face Space + Supabase)

### 3.1 Supabase (free Postgres)
1. Create project → copy connection string.
2. `DATABASE_URL=postgresql+asyncpg://...@...supabase.co:5432/postgres?ssl=require`
   (direct connection for Alembic; if using the 6543 pooler, set asyncpg `statement_cache_size=0`).
3. One-time bootstrap: `alembic upgrade head` → run the simulation seeder (seeds 256
   workers / 1555 sessions so the dashboard is populated).

### 3.2 Hugging Face Space (Docker SDK, free CPU)
- New HF `Dockerfile` + `README.md` front-matter: `sdk: docker`, `app_port: 7860`.
- Startup runs **both** processes (supervisord or a shell script):
  - `uvicorn src.api.main:app --port 8000` (internal; UI calls `http://localhost:8000`),
  - `streamlit run src/ui/app.py --server.port 7860 --server.address 0.0.0.0 --server.headless true`
    (public; **drop the local SSL flags** — HF terminates HTTPS).
- **HF Secrets:** `DATABASE_URL`, `SETTINGS_ENCRYPTION_KEY`, `JWT_SECRET_KEY`
  (LLM key entered via the Settings page, stored encrypted in DB).
- **WebRTC config:** `RTCConfiguration` with Google STUN (`stun:stun.l.google.com:19302`) **plus a
  free TURN** (e.g. Open Relay / metered.ca free tier) — university Wi-Fi often needs TURN.

---

## Part 4 — Honest limitations & tuning
- **CPU FPS will be modest** (~a few FPS with pose + YOLO + action recognizer). Mitigations:
  480p downscale, YOLO every Nth frame, existing `inference_stride=4`, cap WebRTC input FPS.
- **First load slow** (~1–2 min) while models load; HF free Spaces **sleep after ~48 h idle**.
- **2-second latency target** (Rules.md §1.7) won't hold on free CPU — fine for a demo; note as
  a cloud-demo vs edge-deployment distinction in the thesis.
- **GDPR**: frames processed in server memory, not persisted — consistent with the consent banner.

---

## Part 5 — Build order
1. `frame_pipeline.py` shared extractor + refactor `session_manager` (verify local Docker still works).
2. `annotate.py` overlay + `webrtc_live.py` processor.
3. `/feedback/from-deviation` endpoint.
4. Rewire `live_training_page.py` to WebRTC; test locally (browser webcam over `localhost`).
5. Supabase setup + bootstrap.
6. HF Dockerfile / README / secrets + Git LFS model; deploy; tune FPS + TURN.
