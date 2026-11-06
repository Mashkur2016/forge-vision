"""
Tests for src/training/models.py — ActionRecognizer, SOPSequenceModel, factory functions.

All tests use CPU only and do NOT load pretrained weights (pretrained=False) so
they run in any environment without downloading ImageNet weights.
"""
from __future__ import annotations

import pytest
import torch

from src.training.models import (
    ActionRecognizer,
    SOPSequenceModel,
    build_action_recognizer,
    build_sequence_model,
)


# ── ActionRecognizer ───────────────────────────────────────────────────────

class TestActionRecognizerInit:
    def test_default_construction(self):
        model = ActionRecognizer(num_classes=5, pretrained=False)
        assert model.num_classes == 5
        assert model.lstm_hidden_size == 256

    def test_param_count_reasonable(self):
        model = ActionRecognizer(num_classes=5, pretrained=False)
        # MobileNetV3-Small ~ 2.5M params; total should be under 5M
        assert model.param_count < 5_000_000

    def test_backbone_feature_dim_mobilenet_small(self):
        model = ActionRecognizer(num_classes=5, backbone="mobilenet_v3_small", pretrained=False)
        assert model.feature_dim == 576

    def test_backbone_feature_dim_mobilenet_large(self):
        model = ActionRecognizer(num_classes=5, backbone="mobilenet_v3_large", pretrained=False)
        assert model.feature_dim == 960

    def test_classifier_output_dim(self):
        model = ActionRecognizer(num_classes=7, pretrained=False)
        # Inspect last layer of classifier
        last = list(model.classifier.children())[-1]
        assert hasattr(last, "out_features")
        assert last.out_features == 7


class TestActionRecognizerForward:
    @pytest.fixture
    def model(self):
        m = ActionRecognizer(num_classes=5, pretrained=False)
        m.eval()
        return m

    def test_output_shape(self, model):
        B, T, C, H, W = 2, 8, 3, 112, 112
        x = torch.randn(B, T, C, H, W)
        with torch.no_grad():
            logits = model(x)
        assert logits.shape == (B, 5)

    def test_output_shape_batch_1(self, model):
        x = torch.randn(1, 4, 3, 112, 112)
        with torch.no_grad():
            logits = model(x)
        assert logits.shape == (1, 5)

    def test_single_frame_sequence(self, model):
        x = torch.randn(1, 1, 3, 112, 112)
        with torch.no_grad():
            logits = model(x)
        assert logits.shape == (1, 5)

    def test_output_is_finite(self, model):
        x = torch.randn(2, 8, 3, 112, 112)
        with torch.no_grad():
            logits = model(x)
        assert torch.isfinite(logits).all()

    def test_different_num_frames(self, model):
        for T in (4, 8, 16):
            x = torch.randn(1, T, 3, 112, 112)
            with torch.no_grad():
                out = model(x)
            assert out.shape == (1, 5)

    def test_gradients_flow(self):
        model = ActionRecognizer(num_classes=5, pretrained=False)
        model.train()
        x = torch.randn(2, 4, 3, 112, 112)
        logits = model(x)
        loss = logits.sum()
        loss.backward()
        # Check at least one gradient is non-zero
        grad_norms = [p.grad.norm().item() for p in model.parameters() if p.grad is not None]
        assert any(g > 0 for g in grad_norms)

    def test_deterministic_with_eval_mode(self):
        model = ActionRecognizer(num_classes=5, pretrained=False)
        model.eval()
        x = torch.randn(1, 4, 3, 112, 112)
        with torch.no_grad():
            out1 = model(x)
            out2 = model(x)
        assert torch.allclose(out1, out2)


# ── SOPSequenceModel ───────────────────────────────────────────────────────

class TestSOPSequenceModelInit:
    def test_deviation_classes_count(self):
        assert len(SOPSequenceModel.DEVIATION_CLASSES) == 6

    def test_deviation_classes_content(self):
        expected = {"CORRECT", "MISSING_STEP", "WRONG_ORDER",
                    "INCORRECT_EXECUTION", "MISSING_PPE", "UNSAFE_POSTURE"}
        assert set(SOPSequenceModel.DEVIATION_CLASSES) == expected

    def test_construction(self):
        model = SOPSequenceModel(num_action_classes=10)
        assert model.num_action_classes == 10
        assert model.num_deviation_classes == 6

    def test_custom_num_deviation_classes(self):
        model = SOPSequenceModel(num_action_classes=10, num_deviation_classes=4)
        assert model.num_deviation_classes == 4

    def test_param_count_small(self):
        # Sequence model should be very lightweight (< 500K params)
        model = SOPSequenceModel(num_action_classes=20)
        assert model.param_count < 500_000


class TestSOPSequenceModelForward:
    @pytest.fixture
    def model(self):
        m = SOPSequenceModel(num_action_classes=10)
        m.eval()
        return m

    def test_output_shape(self, model):
        seq = torch.randint(0, 10, (4, 16))  # (B=4, T=16)
        with torch.no_grad():
            logits = model(seq)
        assert logits.shape == (4, 6)

    def test_output_shape_batch_1(self, model):
        seq = torch.randint(0, 10, (1, 8))
        with torch.no_grad():
            logits = model(seq)
        assert logits.shape == (1, 6)

    def test_output_is_finite(self, model):
        seq = torch.randint(0, 10, (2, 16))
        with torch.no_grad():
            logits = model(seq)
        assert torch.isfinite(logits).all()

    def test_padding_index_handled(self, model):
        """Sequence with padding tokens (0) should not raise."""
        seq = torch.zeros(2, 16, dtype=torch.long)
        with torch.no_grad():
            logits = model(seq)
        assert logits.shape == (2, 6)


class TestPredictDeviation:
    def test_returns_list_of_strings(self):
        model = SOPSequenceModel(num_action_classes=10)
        seq = torch.randint(0, 10, (1, 8))
        result = model.predict_deviation(seq)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] in SOPSequenceModel.DEVIATION_CLASSES

    def test_predict_batch_of_2(self):
        model = SOPSequenceModel(num_action_classes=10)
        seq = torch.randint(0, 10, (2, 8))
        result = model.predict_deviation(seq)
        assert len(result) == 2
        for r in result:
            assert r in SOPSequenceModel.DEVIATION_CLASSES


# ── Factory functions ──────────────────────────────────────────────────────

class TestBuildActionRecognizer:
    @pytest.fixture
    def config(self):
        return {
            "action_recognition": {
                "backbone": "mobilenet_v3_small",
                "lstm_hidden_size": 128,
                "lstm_num_layers": 1,
                "lstm_dropout": 0.2,
            }
        }

    def test_builds_model(self, config):
        model = build_action_recognizer(config, num_classes=5)
        assert isinstance(model, ActionRecognizer)

    def test_config_applied(self, config):
        model = build_action_recognizer(config, num_classes=5)
        assert model.lstm_hidden_size == 128
        assert model.num_classes == 5


class TestBuildSequenceModel:
    @pytest.fixture
    def config(self):
        return {
            "sequence_model": {
                "num_deviation_classes": 6,
                "hidden_size": 64,
                "num_layers": 1,
                "dropout": 0.1,
            }
        }

    def test_builds_model(self, config):
        model = build_sequence_model(config, num_action_classes=10)
        assert isinstance(model, SOPSequenceModel)

    def test_config_applied(self, config):
        model = build_sequence_model(config, num_action_classes=10)
        assert model.num_deviation_classes == 6
        assert model.num_action_classes == 10
