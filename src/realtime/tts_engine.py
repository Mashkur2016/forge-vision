"""
TTS Engine — Task 3.6 (Phase 3) — Enhancement 3.

Converts LLM-generated corrective feedback text to spoken audio.
Uses pyttsx3 for fully offline, cross-platform TTS (no API key required).
Falls back gracefully — logs a warning and disables itself if pyttsx3
is not installed or the audio subsystem is unavailable.

Rules.md §1.7: TTS must not block the inference loop.
               Speech runs in a dedicated background thread.
"""
from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class TTSConfig:
    """TTS engine configuration."""
    rate: int = 160          # Words per minute (natural speech ~130-160 wpm)
    volume: float = 0.9      # Volume level 0.0–1.0
    voice_index: int = 0     # Index into available system voices
    enabled: bool = True


class TTSEngine:
    """
    Non-blocking text-to-speech engine backed by a dedicated thread.

    A single-slot queue ensures that if the worker receives a new instruction
    before the previous one finishes speaking, the new instruction takes
    priority — avoiding a backlog of stale guidance.

    Usage:
        tts = TTSEngine(TTSConfig())
        tts.start()
        tts.speak("Please put on your safety helmet before continuing.")
        # ... later ...
        tts.stop()

    Or as a context manager:
        with TTSEngine() as tts:
            tts.speak("Step 3: Apply torque to 25 Nm.")
    """

    def __init__(self, config: Optional[TTSConfig] = None) -> None:
        self._config = config or TTSConfig()
        self._engine = None
        # Single-slot queue — new speech replaces pending speech
        self._queue: queue.Queue[Optional[str]] = queue.Queue(maxsize=1)
        self._thread: Optional[threading.Thread] = None
        self._available: bool = False

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> "TTSEngine":
        """Initialise the TTS engine and start the background speech thread."""
        if not self._config.enabled:
            return self

        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._config.rate)
            self._engine.setProperty("volume", self._config.volume)

            voices = self._engine.getProperty("voices")
            if voices and self._config.voice_index < len(voices):
                self._engine.setProperty(
                    "voice", voices[self._config.voice_index].id
                )

            self._available = True
        except Exception as exc:
            log.warning(
                "TTS engine unavailable (%s) — audio feedback disabled. "
                "Install pyttsx3 to enable: pip install pyttsx3",
                exc,
            )
            self._available = False
            return self

        self._thread = threading.Thread(
            target=self._tts_loop,
            daemon=True,
            name="forge-tts",
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        """Flush the queue and stop the background speech thread."""
        # Send sentinel value to exit the loop
        try:
            self._queue.put(None, timeout=1.0)
        except queue.Full:
            pass

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass

    @property
    def is_available(self) -> bool:
        return self._available

    # ── Speech ────────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """
        Queue text for speech synthesis.

        If a previous utterance is pending, it is replaced with this one
        so the worker always hears the most current instruction.

        Args:
            text: Plain-English corrective instruction to speak.
        """
        if not self._available or not self._config.enabled:
            return

        # Drop any pending speech (replace with newest instruction)
        try:
            self._queue.get_nowait()
        except queue.Empty:
            pass

        try:
            self._queue.put_nowait(text)
        except queue.Full:
            pass  # Safety valve — should not happen with maxsize=1 after get

    # ── Background thread ─────────────────────────────────────────────────

    def _tts_loop(self) -> None:
        """Background thread: receive text and synthesise speech."""
        while True:
            try:
                text = self._queue.get(timeout=2.0)
            except queue.Empty:
                continue

            if text is None:   # Sentinel — exit
                break

            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as exc:
                log.warning("TTS speak error: %s", exc)

    # ── Context manager ───────────────────────────────────────────────────

    def __enter__(self) -> "TTSEngine":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()
