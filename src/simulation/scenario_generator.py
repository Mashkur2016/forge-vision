"""
Scenario Generator — Phase A synthetic labelled video clip generation.

For each SOP and each scenario type, this module generates a sequence of
synthetic BGR frames that represent a worker executing (or mis-executing) the
procedure. Frames use simple OpenCV shapes to represent the worker, tools, and
workspace — sufficient for training and validating the CV pipeline architecture
before real video is captured in Phase B.

Scenario types (matching Architecture.md deviation classifier):
    CORRECT          — all steps executed in order, within time, with PPE
    MISSING_STEP     — one required step is skipped entirely
    WRONG_ORDER      — two adjacent steps are swapped
    UNSAFE           — step performed without required PPE / unsafe posture
    RARE_FAILURE     — critical safety step skipped (e.g. power not isolated)

Output:
    Each generate_clip() call returns:
        frames: list[np.ndarray]   — BGR frames at FRAME_WIDTH × FRAME_HEIGHT
        label:  ClipLabel          — metadata for training supervision
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import cv2
import numpy as np

from src.simulation.sop_schema import SOP, SOPStep

# ── Constants ──────────────────────────────────────────────────────────────

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FPS = 30
FRAMES_PER_STEP = 30          # 1 second of video per SOP step
TRANSITION_FRAMES = 10        # Short transition between steps

# Colour palette (BGR)
_BG_COLOUR = (200, 200, 200)            # Light gray workbench
_WORKER_COLOUR = (180, 80, 30)          # Dark blue — worker silhouette
_HAND_COLOUR = (100, 180, 60)           # Green — hands
_OBJECT_COLOURS = [                      # Rotating palette for objects
    (0, 120, 255),   # Orange-red
    (255, 60, 0),    # Blue
    (0, 200, 100),   # Green
    (180, 0, 200),   # Purple
    (0, 200, 220),   # Yellow
    (200, 0, 100),   # Indigo
]
_ERROR_OVERLAY = (0, 0, 220)            # Red — error highlight
_PPE_MISSING_COLOUR = (0, 80, 220)      # Orange — PPE warning
_TEXT_BG = (30, 30, 30)
_TEXT_FG = (240, 240, 240)
_SAFE_STEP_COLOUR = (40, 180, 40)       # Green — correct step indicator


# ── Data models ────────────────────────────────────────────────────────────

class ScenarioType(str, Enum):
    CORRECT = "correct"
    MISSING_STEP = "missing_step"
    WRONG_ORDER = "wrong_order"
    UNSAFE = "unsafe"
    RARE_FAILURE = "rare_failure"


@dataclass
class ClipLabel:
    """Ground-truth metadata for one synthetic video clip."""

    clip_id: str
    sop_id: str
    sop_name: str
    scenario_type: ScenarioType

    # Which steps were executed, in order (step ids)
    executed_steps: list[int]

    # The step where the deviation occurred (None for CORRECT clips)
    error_step_id: Optional[int]

    # Deviation class (matches Architecture.md SOP deviation classifier output)
    error_type: Optional[str]

    frame_count: int
    fps: int = FPS

    # For thesis reproducibility (Rules.md §1.5)
    seed: int = 0

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.fps

    def to_dict(self) -> dict:
        return {
            "clip_id": self.clip_id,
            "sop_id": self.sop_id,
            "sop_name": self.sop_name,
            "scenario_type": self.scenario_type.value,
            "executed_steps": self.executed_steps,
            "error_step_id": self.error_step_id,
            "error_type": self.error_type,
            "frame_count": self.frame_count,
            "fps": self.fps,
            "duration_seconds": round(self.duration_seconds, 2),
            "seed": self.seed,
        }


# ── Frame renderer ─────────────────────────────────────────────────────────

class _FrameRenderer:
    """
    Renders a single synthetic BGR frame representing a worker performing
    a specific SOP step.

    The visual layout:
        Top bar   — SOP name, step number, scenario type
        Centre    — Worker silhouette + hands positioned near active objects
        Bottom    — Object area showing required tools
        Overlay   — Error highlights / PPE-missing warnings when applicable
    """

    W = FRAME_WIDTH
    H = FRAME_HEIGHT

    # Worker silhouette bounding box (relative to frame)
    _WORKER_X = int(W * 0.35)
    _WORKER_Y = int(H * 0.25)
    _WORKER_W = int(W * 0.30)
    _WORKER_H = int(H * 0.50)

    # Object area (bottom strip)
    _OBJ_Y_START = int(H * 0.72)
    _OBJ_Y_END = int(H * 0.90)

    def render(
        self,
        sop: SOP,
        step: Optional[SOPStep],
        scenario_type: ScenarioType,
        frame_index: int,
        total_frames: int,
        is_error: bool = False,
        ppe_missing: bool = False,
    ) -> np.ndarray:
        frame = np.full((self.H, self.W, 3), _BG_COLOUR, dtype=np.uint8)

        self._draw_workbench(frame)
        self._draw_worker(frame, step, frame_index, is_error, ppe_missing)
        if step:
            self._draw_objects(frame, step)
        self._draw_hud(frame, sop, step, scenario_type, is_error, ppe_missing, frame_index, total_frames)

        return frame

    # ── Drawing helpers ────────────────────────────────────────────────────

    def _draw_workbench(self, frame: np.ndarray) -> None:
        """Draw a simple workbench surface at the bottom of the frame."""
        cv2.rectangle(
            frame,
            (0, int(self.H * 0.70)),
            (self.W, self.H),
            (150, 120, 90),
            -1,
        )
        cv2.line(
            frame,
            (0, int(self.H * 0.70)),
            (self.W, int(self.H * 0.70)),
            (100, 80, 60),
            3,
        )

    def _draw_worker(
        self,
        frame: np.ndarray,
        step: Optional[SOPStep],
        frame_index: int,
        is_error: bool,
        ppe_missing: bool,
    ) -> None:
        # Worker body
        body_colour = _ERROR_OVERLAY if is_error else _WORKER_COLOUR
        cv2.rectangle(
            frame,
            (self._WORKER_X, self._WORKER_Y),
            (self._WORKER_X + self._WORKER_W, self._WORKER_Y + self._WORKER_H),
            body_colour,
            -1,
        )
        # Head
        head_cx = self._WORKER_X + self._WORKER_W // 2
        head_cy = self._WORKER_Y - 28
        head_colour = _PPE_MISSING_COLOUR if ppe_missing else _WORKER_COLOUR
        cv2.circle(frame, (head_cx, head_cy), 25, head_colour, -1)

        # Animated hands — oscillate toward the active object area
        t = frame_index / max(1, FRAMES_PER_STEP - 1)
        hand_y = int(self._OBJ_Y_START + (self._OBJ_Y_END - self._OBJ_Y_START) * 0.5 * (1 + np.sin(t * np.pi)))
        hand_x_left = self._WORKER_X - 30
        hand_x_right = self._WORKER_X + self._WORKER_W + 30

        for hx in (hand_x_left, hand_x_right):
            cv2.circle(frame, (hx, hand_y), 14, _HAND_COLOUR, -1)

        # PPE indicator (hard hat shape above head)
        if not ppe_missing:
            pts = np.array([
                [head_cx - 28, head_cy - 18],
                [head_cx + 28, head_cy - 18],
                [head_cx + 20, head_cy - 38],
                [head_cx - 20, head_cy - 38],
            ], np.int32)
            cv2.fillPoly(frame, [pts], (0, 200, 200))

    def _draw_objects(self, frame: np.ndarray, step: SOPStep) -> None:
        """Draw coloured circles in the object area for each required object."""
        objects = step.required_objects
        if not objects:
            return

        spacing = self.W // (len(objects) + 1)
        obj_cy = (self._OBJ_Y_START + self._OBJ_Y_END) // 2

        for i, obj_name in enumerate(objects):
            cx = spacing * (i + 1)
            colour = _OBJECT_COLOURS[i % len(_OBJECT_COLOURS)]
            cv2.circle(frame, (cx, obj_cy), 20, colour, -1)
            cv2.circle(frame, (cx, obj_cy), 20, (255, 255, 255), 2)

            # Object label
            label_size = cv2.getTextSize(obj_name, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)[0]
            lx = cx - label_size[0] // 2
            cv2.putText(
                frame, obj_name,
                (lx, obj_cy + 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (50, 50, 50), 1, cv2.LINE_AA,
            )

    def _draw_hud(
        self,
        frame: np.ndarray,
        sop: SOP,
        step: Optional[SOPStep],
        scenario_type: ScenarioType,
        is_error: bool,
        ppe_missing: bool,
        frame_index: int,
        total_frames: int,
    ) -> None:
        """Draw the top HUD bar with SOP name, step info, and scenario type."""
        # Background bar
        cv2.rectangle(frame, (0, 0), (self.W, 55), _TEXT_BG, -1)

        # SOP name
        cv2.putText(
            frame, f"SOP: {sop.name}",
            (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.50, _TEXT_FG, 1, cv2.LINE_AA,
        )

        # Step info
        if step:
            step_text = f"Step {step.id}/{sop.step_count}: {step.name}"
            colour = _ERROR_OVERLAY if is_error else _SAFE_STEP_COLOUR
            cv2.putText(
                frame, step_text,
                (8, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.48, colour, 1, cv2.LINE_AA,
            )

        # Scenario type badge (top-right)
        badge_colour = _ERROR_OVERLAY if scenario_type != ScenarioType.CORRECT else _SAFE_STEP_COLOUR
        badge_text = scenario_type.value.upper().replace("_", " ")
        badge_size = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
        bx = self.W - badge_size[0] - 12
        cv2.putText(
            frame, badge_text,
            (bx, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, badge_colour, 1, cv2.LINE_AA,
        )

        # PPE warning
        if ppe_missing:
            cv2.putText(
                frame, "⚠ PPE MISSING",
                (bx - 20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _PPE_MISSING_COLOUR, 1, cv2.LINE_AA,
            )

        # Frame progress bar
        progress = frame_index / max(1, total_frames - 1)
        bar_w = int(self.W * progress)
        cv2.rectangle(frame, (0, 53), (bar_w, 55), (80, 180, 80), -1)


# ── Scenario generator ─────────────────────────────────────────────────────

class ScenarioGenerator:
    """
    Generates synthetic labelled video clips for Phase A training data.

    Each call to generate_clip() produces a list of BGR frames and a ClipLabel
    that describes the ground-truth for that clip.

    Example:
        gen = ScenarioGenerator(seed=42)
        frames, label = gen.generate_clip(sop, ScenarioType.MISSING_STEP)
    """

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._rng = random.Random(seed)
        self._renderer = _FrameRenderer()

    def generate_clip(
        self,
        sop: SOP,
        scenario_type: ScenarioType,
    ) -> tuple[list[np.ndarray], ClipLabel]:
        """
        Generate one synthetic clip for the given SOP and scenario type.

        Returns:
            frames: List of BGR numpy arrays (FRAME_WIDTH × FRAME_HEIGHT)
            label:  ClipLabel with ground-truth metadata
        """
        clip_id = str(uuid.uuid4())[:8]
        dispatch = {
            ScenarioType.CORRECT: self._generate_correct,
            ScenarioType.MISSING_STEP: self._generate_missing_step,
            ScenarioType.WRONG_ORDER: self._generate_wrong_order,
            ScenarioType.UNSAFE: self._generate_unsafe,
            ScenarioType.RARE_FAILURE: self._generate_rare_failure,
        }
        frames, label_kwargs = dispatch[scenario_type](sop)

        label = ClipLabel(
            clip_id=clip_id,
            sop_id=sop.id,
            sop_name=sop.name,
            scenario_type=scenario_type,
            frame_count=len(frames),
            fps=FPS,
            seed=self._seed,
            **label_kwargs,
        )
        return frames, label

    # ── Scenario builders ──────────────────────────────────────────────────

    def _generate_correct(self, sop: SOP) -> tuple[list[np.ndarray], dict]:
        """All steps in order, no errors, PPE present throughout."""
        frames: list[np.ndarray] = []
        total_steps = sop.step_count

        for step in sop.steps:
            step_frames = self._render_step(sop, step, ScenarioType.CORRECT, total_steps)
            frames.extend(step_frames)

        return frames, {
            "executed_steps": [s.id for s in sop.steps],
            "error_step_id": None,
            "error_type": None,
        }

    def _generate_missing_step(self, sop: SOP) -> tuple[list[np.ndarray], dict]:
        """
        Skip one non-safety-critical step.
        If all steps are safety-critical, skip the last step.
        """
        frames: list[np.ndarray] = []
        skippable = [s for s in sop.steps if not s.safety_critical]
        if not skippable:
            skippable = [sop.steps[-1]]

        skipped = self._rng.choice(skippable)
        executed_steps: list[int] = []
        total_frames_approx = (sop.step_count - 1) * (FRAMES_PER_STEP + TRANSITION_FRAMES)

        for step in sop.steps:
            if step.id == skipped.id:
                continue
            step_frames = self._render_step(sop, step, ScenarioType.MISSING_STEP, sop.step_count)
            frames.extend(step_frames)
            executed_steps.append(step.id)

        return frames, {
            "executed_steps": executed_steps,
            "error_step_id": skipped.id,
            "error_type": "MISSING_STEP",
        }

    def _generate_wrong_order(self, sop: SOP) -> tuple[list[np.ndarray], dict]:
        """
        Swap two adjacent steps.
        The earlier step is flagged as the error step.
        """
        frames: list[np.ndarray] = []
        steps = list(sop.steps)

        # Find a swappable pair (neither safety-critical preferred)
        swap_candidates = [
            i for i in range(len(steps) - 1)
            if not steps[i].safety_critical and not steps[i + 1].safety_critical
        ]
        if not swap_candidates:
            swap_candidates = list(range(len(steps) - 1))

        swap_idx = self._rng.choice(swap_candidates)
        steps[swap_idx], steps[swap_idx + 1] = steps[swap_idx + 1], steps[swap_idx]
        error_step = steps[swap_idx]  # The step now in the wrong position

        executed_steps: list[int] = []
        for i, step in enumerate(steps):
            is_error = step.id == error_step.id
            step_frames = self._render_step(
                sop, step, ScenarioType.WRONG_ORDER, sop.step_count, is_error=is_error
            )
            frames.extend(step_frames)
            executed_steps.append(step.id)

        return frames, {
            "executed_steps": executed_steps,
            "error_step_id": error_step.id,
            "error_type": "WRONG_ORDER",
        }

    def _generate_unsafe(self, sop: SOP) -> tuple[list[np.ndarray], dict]:
        """
        Worker performs a step with PPE missing (MISSING_PPE).
        Pick a step that requires PPE, or any step if none do.
        """
        frames: list[np.ndarray] = []
        ppe_steps = [s for s in sop.steps if s.required_ppe or sop.required_ppe]
        unsafe_step = self._rng.choice(ppe_steps if ppe_steps else sop.steps)

        executed_steps: list[int] = []
        for step in sop.steps:
            ppe_missing = step.id == unsafe_step.id
            step_frames = self._render_step(
                sop, step, ScenarioType.UNSAFE, sop.step_count, ppe_missing=ppe_missing
            )
            frames.extend(step_frames)
            executed_steps.append(step.id)

        return frames, {
            "executed_steps": executed_steps,
            "error_step_id": unsafe_step.id,
            "error_type": "MISSING_PPE",
        }

    def _generate_rare_failure(self, sop: SOP) -> tuple[list[np.ndarray], dict]:
        """
        A safety-critical step is skipped — the most dangerous deviation.
        Falls back to the first step if none are marked safety_critical.
        """
        frames: list[np.ndarray] = []
        critical = [s for s in sop.steps if s.safety_critical]
        skipped = self._rng.choice(critical) if critical else sop.steps[0]

        executed_steps: list[int] = []
        for step in sop.steps:
            if step.id == skipped.id:
                continue
            step_frames = self._render_step(
                sop, step, ScenarioType.RARE_FAILURE, sop.step_count, is_error=False
            )
            frames.extend(step_frames)
            executed_steps.append(step.id)

        return frames, {
            "executed_steps": executed_steps,
            "error_step_id": skipped.id,
            "error_type": "MISSING_STEP",  # Subset of missing step — safety-critical variant
        }

    # ── Frame sequence renderer ────────────────────────────────────────────

    def _render_step(
        self,
        sop: SOP,
        step: SOPStep,
        scenario_type: ScenarioType,
        total_steps: int,
        is_error: bool = False,
        ppe_missing: bool = False,
    ) -> list[np.ndarray]:
        """Render FRAMES_PER_STEP frames for a single SOP step."""
        total = FRAMES_PER_STEP + TRANSITION_FRAMES
        frames: list[np.ndarray] = []

        for i in range(total):
            in_transition = i >= FRAMES_PER_STEP
            frame = self._renderer.render(
                sop=sop,
                step=step if not in_transition else None,
                scenario_type=scenario_type,
                frame_index=i,
                total_frames=total,
                is_error=is_error and not in_transition,
                ppe_missing=ppe_missing and not in_transition,
            )
            frames.append(frame)

        return frames
