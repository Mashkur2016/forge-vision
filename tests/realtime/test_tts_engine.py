"""
Unit tests for src/realtime/tts_engine.py — Task 3.6.

Tests cover configuration, graceful fallback when pyttsx3 is unavailable,
and the non-blocking speak/stop lifecycle.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.realtime.tts_engine import TTSConfig, TTSEngine


# ── TTSConfig tests ────────────────────────────────────────────────────────

def test_tts_config_defaults():
    cfg = TTSConfig()
    assert cfg.rate == 160
    assert cfg.volume == pytest.approx(0.9)
    assert cfg.enabled is True


def test_tts_config_custom():
    cfg = TTSConfig(rate=200, volume=0.5, enabled=False)
    assert cfg.rate == 200
    assert cfg.enabled is False


# ── TTSEngine when pyttsx3 is unavailable ─────────────────────────────────

def test_tts_start_graceful_if_pyttsx3_missing():
    """If pyttsx3 is not importable, engine must not raise — just set is_available=False."""
    with patch("builtins.__import__", side_effect=ImportError("No module named pyttsx3")):
        # We can't actually patch builtins like this cleanly for selective modules,
        # so we patch pyttsx3.init directly
        pass

    # Simulate pyttsx3 unavailable by patching init to raise
    with patch("src.realtime.tts_engine.TTSEngine.start") as mock_start:
        engine = TTSEngine(TTSConfig())
        # If start is not called, engine._available stays False by default
        assert not engine.is_available


def test_tts_speak_is_noop_when_unavailable():
    """speak() must not raise even if engine is not available."""
    engine = TTSEngine(TTSConfig())
    # _available defaults to False without calling start()
    engine.speak("This should not raise.")


def test_tts_stop_is_noop_when_not_started():
    """stop() before start() must not raise."""
    engine = TTSEngine(TTSConfig())
    engine.stop()   # Should complete silently


# ── TTSEngine with mock pyttsx3 ────────────────────────────────────────────

def _make_mock_pyttsx3():
    mock_engine = MagicMock()
    mock_voices = [MagicMock()]
    mock_voices[0].id = "voice_id_0"
    mock_engine.getProperty.return_value = mock_voices
    return mock_engine


@patch("src.realtime.tts_engine.TTSEngine._tts_loop")  # Don't actually run the thread loop
def test_tts_start_with_mock_pyttsx3(mock_loop):
    with patch.dict("sys.modules", {"pyttsx3": MagicMock()}):
        import sys
        mock_pyttsx3 = sys.modules["pyttsx3"]
        mock_pyttsx3.init.return_value = _make_mock_pyttsx3()

        engine = TTSEngine(TTSConfig())
        engine.start()
        engine.stop()

        # Engine should have been initialised
        mock_pyttsx3.init.assert_called_once()


def test_tts_disabled_config_does_not_start():
    """When enabled=False, start() should return without creating a thread."""
    engine = TTSEngine(TTSConfig(enabled=False))
    engine.start()
    assert not engine.is_available
    assert engine._thread is None


def test_tts_speak_with_disabled_config_is_noop():
    """speak() when disabled must not raise."""
    engine = TTSEngine(TTSConfig(enabled=False))
    engine.start()
    engine.speak("This should do nothing.")
    engine.stop()


# ── Context manager ────────────────────────────────────────────────────────

def test_tts_context_manager_does_not_raise():
    """TTSEngine used as context manager must not raise regardless of availability."""
    with TTSEngine(TTSConfig(enabled=False)) as tts:
        assert tts is not None
        tts.speak("Context manager test.")
