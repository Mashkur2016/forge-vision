"""
Camera Capture — Task 3.1 (Phase 3).

Wraps OpenCV VideoCapture with a background reader thread so the main
inference loop always gets the latest available frame without blocking
on I/O.  Supports webcams (integer index) and IP cameras (URL).

For HTTP sources (IP Webcam / MJPEG apps) the capture loop fetches
individual JPEG snapshots via urllib instead of relying on OpenCV's
MJPEG stream parser, which fails on multipart/x-mixed-replace streams.

Architecture.md Layer 1: "Phase B: Live camera feed"
Rules.md §1.7: Frame acquisition must not add latency to the 2-second budget.
Rules.md §2: GDPR — frames are held in memory only; never written to disk.
"""
from __future__ import annotations

import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class CameraConfig:
    """Runtime configuration for a camera source."""
    # Integer index (0 = default webcam) or URL string (RTSP / HTTP)
    source: int | str = 0

    # Maximum frames per second to capture (CPU budget guard)
    target_fps: int = 15

    # Resolution to request from the camera driver (may be ignored by driver)
    width: int = 640
    height: int = 480

    # Seconds to wait for the camera to deliver its first frame
    # IP cameras (Wi-Fi / RTSP) need more time than a local webcam
    open_timeout: float = 15.0


def _is_http_source(source: int | str) -> bool:
    return isinstance(source, str) and source.lower().startswith("http")


def _snapshot_url(source: str) -> str:
    """
    Derive a single-frame JPEG URL from an IP Webcam stream URL.
    /video  → /shot.jpg
    /shot.jpg → unchanged
    bare host:port → /shot.jpg appended
    """
    s = source.rstrip("/")
    if s.endswith("/shot.jpg"):
        return s
    if s.endswith("/video") or s.endswith("/videofeed"):
        return s.rsplit("/", 1)[0] + "/shot.jpg"
    return s + "/shot.jpg"


class CameraCapture:
    """
    Thread-safe camera capture using a background reader thread.

    The background thread reads frames from the camera at the camera's
    native rate and stores the latest frame in a 1-slot buffer.  The main
    thread reads from the buffer without blocking on I/O.

    Usage:
        with CameraCapture(CameraConfig(source=0)) as cam:
            while cam.is_running:
                frame = cam.read()
                if frame is not None:
                    process(frame)
    """

    def __init__(self, config: Optional[CameraConfig] = None) -> None:
        self._config = config or CameraConfig()
        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._frame_count: int = 0
        self._start_time: float = 0.0

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> "CameraCapture":
        """Open the camera and start the background capture thread."""
        self._http_mode = _is_http_source(self._config.source)

        if not self._http_mode:
            self._cap = cv2.VideoCapture(self._config.source)
            if not self._cap.isOpened():
                raise RuntimeError(
                    f"CameraCapture: failed to open source '{self._config.source}'. "
                    "Check that the camera is connected and not in use by another process."
                )
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.height)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            # Verify the HTTP source is reachable before starting the thread
            snap = _snapshot_url(self._config.source)
            try:
                with urllib.request.urlopen(snap, timeout=5) as resp:
                    data = resp.read()
                arr = np.frombuffer(data, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is None:
                    raise RuntimeError("CameraCapture: HTTP source returned non-image data.")
                with self._frame_lock:
                    self._latest_frame = frame
            except urllib.error.URLError as exc:
                raise RuntimeError(
                    f"CameraCapture: cannot reach HTTP source '{self._config.source}': {exc}. "
                    "Ensure the IP camera is running and both devices are on the same network."
                ) from exc

        self._stop_event.clear()
        self._frame_count = 0
        self._start_time = time.perf_counter()

        self._thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="forge-camera-capture",
        )
        self._thread.start()

        if not self._http_mode:
            # Block until the first frame arrives (or timeout)
            deadline = time.perf_counter() + self._config.open_timeout
            while self._latest_frame is None:
                if time.perf_counter() > deadline:
                    self.stop()
                    raise RuntimeError(
                        f"CameraCapture: no frame received within {self._config.open_timeout}s. "
                        "The source may be offline or the URL may be incorrect."
                    )
                time.sleep(0.05)

        return self

    def stop(self) -> None:
        """Stop the background thread and release the camera."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── Frame access ──────────────────────────────────────────────────────

    def read(self) -> Optional[np.ndarray]:
        """
        Return the most recently captured frame (BGR uint8 ndarray).

        Returns None if no frame has been captured yet.
        Never blocks — returns whatever is currently in the 1-slot buffer.
        """
        with self._frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    # ── Stats ─────────────────────────────────────────────────────────────

    @property
    def actual_fps(self) -> float:
        """Approximate capture FPS since start() was called."""
        elapsed = time.perf_counter() - self._start_time
        return self._frame_count / elapsed if elapsed > 0 else 0.0

    @property
    def frame_count(self) -> int:
        """Total frames captured since start()."""
        return self._frame_count

    # ── Background capture loop ───────────────────────────────────────────

    def _capture_loop(self) -> None:
        """
        Background thread: continuously reads frames from the camera.

        HTTP sources: polls /shot.jpg at target_fps using urllib.
        Other sources: uses OpenCV VideoCapture.read().

        Throttles to target_fps to bound CPU usage.  Exits cleanly when
        stop_event is set or when the camera stops delivering frames.
        """
        min_interval = 1.0 / self._config.target_fps
        last_read_time = 0.0

        if self._http_mode:
            snap = _snapshot_url(self._config.source)
            consecutive_failures = 0
            while not self._stop_event.is_set():
                now = time.perf_counter()
                if now - last_read_time < min_interval:
                    time.sleep(0.002)
                    continue
                try:
                    with urllib.request.urlopen(snap, timeout=3) as resp:
                        data = resp.read()
                    arr = np.frombuffer(data, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        with self._frame_lock:
                            self._latest_frame = frame
                        self._frame_count += 1
                        consecutive_failures = 0
                    last_read_time = time.perf_counter()
                except Exception:
                    consecutive_failures += 1
                    if consecutive_failures >= 10:
                        break
                    time.sleep(0.1)
        else:
            while not self._stop_event.is_set():
                now = time.perf_counter()
                if now - last_read_time < min_interval:
                    time.sleep(0.002)
                    continue

                ret, frame = self._cap.read()
                if not ret:
                    break

                with self._frame_lock:
                    self._latest_frame = frame

                self._frame_count += 1
                last_read_time = now

    # ── Context manager ───────────────────────────────────────────────────

    def __enter__(self) -> "CameraCapture":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()
