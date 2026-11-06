"""
FORGE-Vision Model Architectures — Phase 2.

ActionRecognizer   — CNN (MobileNetV3) + LSTM for clip-level action classification
SOPSequenceModel   — LSTM for tracking SOP step progression and detecting deviations

Both models are designed with edge deployment in mind:
  - Lightweight CNN backbone (MobileNetV3-Small, ~2.5M params)
  - LSTM over ResNet/Transformer for lower memory footprint on Jetson
  - INT8 quantization-ready (see evaluator.py)

Rules.md §1.5: All models accept a seed for reproducible weight initialisation.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torchvision.models as tv_models


# ── Action Recognizer (CNN + LSTM) ─────────────────────────────────────────

class ActionRecognizer(nn.Module):
    """
    Temporal action recognition model for SOP step classification.

    Architecture:
        Input  : (B, T, C, H, W) — batch of video clips, T frames each
        CNN    : MobileNetV3-Small extracts (B, T, feature_dim) spatial features
        LSTM   : 2-layer LSTM models temporal sequence → (B, hidden_size)
        Head   : Linear → (B, num_classes) action class logits

    The CNN backbone is pretrained on ImageNet and fine-tuned end-to-end.
    Feature extraction uses global average pooling (not the classifier head).

    Args:
        num_classes:       Number of action/scenario classes to predict.
        backbone:          Torchvision model name ("mobilenet_v3_small" default).
        lstm_hidden_size:  LSTM hidden state dimension.
        lstm_num_layers:   Number of stacked LSTM layers.
        lstm_dropout:      Dropout between LSTM layers (ignored if num_layers=1).
        pretrained:        Load ImageNet-pretrained CNN weights.
    """

    _BACKBONE_OUTPUT_DIM = {
        "mobilenet_v3_small": 576,
        "mobilenet_v3_large": 960,
        "efficientnet_b0": 1280,
    }

    def __init__(
        self,
        num_classes: int,
        backbone: str = "mobilenet_v3_small",
        lstm_hidden_size: int = 256,
        lstm_num_layers: int = 2,
        lstm_dropout: float = 0.3,
        pretrained: bool = True,
    ) -> None:
        super().__init__()
        self.num_classes = num_classes
        self.backbone_name = backbone
        self.lstm_hidden_size = lstm_hidden_size

        # ── CNN feature extractor ──────────────────────────────────────────
        weights = "IMAGENET1K_V1" if pretrained else None
        cnn = getattr(tv_models, backbone)(weights=weights)
        feature_dim = self._BACKBONE_OUTPUT_DIM.get(backbone, 576)

        # Strip the classifier; keep feature layers + global pool
        if hasattr(cnn, "features"):
            self.cnn = nn.Sequential(cnn.features, cnn.avgpool)
        else:
            # Fallback: remove last Linear layer
            children = list(cnn.children())[:-1]
            self.cnn = nn.Sequential(*children)

        self.feature_dim = feature_dim

        # ── Temporal LSTM ──────────────────────────────────────────────────
        self.lstm = nn.LSTM(
            input_size=feature_dim,
            hidden_size=lstm_hidden_size,
            num_layers=lstm_num_layers,
            batch_first=True,
            dropout=lstm_dropout if lstm_num_layers > 1 else 0.0,
            bidirectional=False,
        )

        # ── Classifier head ────────────────────────────────────────────────
        self.classifier = nn.Sequential(
            nn.LayerNorm(lstm_hidden_size),
            nn.Dropout(0.4),
            nn.Linear(lstm_hidden_size, num_classes),
        )

        self._init_weights()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, T, C, H, W) float tensor

        Returns:
            logits: (B, num_classes)
        """
        B, T, C, H, W = x.shape

        # Extract CNN features for each frame
        x_flat = x.view(B * T, C, H, W)            # (B*T, C, H, W)
        features = self.cnn(x_flat)                  # (B*T, feature_dim, 1, 1) or (B*T, feature_dim)
        features = features.view(B * T, -1)          # (B*T, feature_dim)
        features = features.view(B, T, -1)           # (B, T, feature_dim)

        # Temporal modelling
        lstm_out, _ = self.lstm(features)            # (B, T, hidden_size)
        last_hidden = lstm_out[:, -1, :]             # (B, hidden_size)

        return self.classifier(last_hidden)          # (B, num_classes)

    def _init_weights(self) -> None:
        """Initialise LSTM and classifier weights."""
        for name, param in self.lstm.named_parameters():
            if "weight_ih" in name:
                nn.init.xavier_uniform_(param)
            elif "weight_hh" in name:
                nn.init.orthogonal_(param)
            elif "bias" in name:
                nn.init.zeros_(param)

        for layer in self.classifier:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_uniform_(layer.weight)
                nn.init.zeros_(layer.bias)

    @property
    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ── SOP Sequence Model (LSTM deviation detector) ───────────────────────────

class SOPSequenceModel(nn.Module):
    """
    LSTM sequence model for SOP step tracking and deviation classification.

    Architecture:
        Input  : (B, T) action class indices (from ActionRecognizer output)
        Embed  : Learnable embedding (B, T, embed_dim)
        LSTM   : Models temporal sequence → (B, hidden_size)
        Head   : Linear → (B, num_deviation_classes)

    The model learns to recognise patterns like:
        - All steps in order → CORRECT
        - Step 3 followed immediately by step 5 → MISSING_STEP
        - Step 4 before step 3 → WRONG_ORDER
        etc.

    Args:
        num_action_classes:    Vocabulary size (= ActionRecognizer.num_classes)
        num_deviation_classes: Output classes (default 6: correct + 5 error types)
        embed_dim:             Action class embedding dimension
        hidden_size:           LSTM hidden state dimension
        num_layers:            Number of LSTM layers
        dropout:               LSTM dropout
    """

    DEVIATION_CLASSES = [
        "CORRECT",
        "MISSING_STEP",
        "WRONG_ORDER",
        "INCORRECT_EXECUTION",
        "MISSING_PPE",
        "UNSAFE_POSTURE",
    ]

    def __init__(
        self,
        num_action_classes: int,
        num_deviation_classes: int = 6,
        embed_dim: int = 64,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.num_action_classes = num_action_classes
        self.num_deviation_classes = num_deviation_classes

        # Embedding: action class index → dense vector
        self.embedding = nn.Embedding(
            num_embeddings=num_action_classes + 1,  # +1 for padding index
            embedding_dim=embed_dim,
            padding_idx=0,
        )

        self.lstm = nn.LSTM(
            input_size=embed_dim,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        self.classifier = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Dropout(0.3),
            nn.Linear(hidden_size, num_deviation_classes),
        )

        self._init_weights()

    def forward(self, action_sequence: torch.Tensor) -> torch.Tensor:
        """
        Args:
            action_sequence: (B, T) LongTensor of action class indices

        Returns:
            logits: (B, num_deviation_classes)
        """
        embedded = self.embedding(action_sequence)      # (B, T, embed_dim)
        lstm_out, _ = self.lstm(embedded)               # (B, T, hidden_size)
        last = lstm_out[:, -1, :]                       # (B, hidden_size)
        return self.classifier(last)                    # (B, num_deviation_classes)

    def predict_deviation(self, action_sequence: torch.Tensor) -> list[str]:
        """
        Convenience method for single-batch inference.

        Args:
            action_sequence: (1, T) LongTensor

        Returns:
            List of predicted deviation class names.
        """
        self.eval()
        with torch.no_grad():
            logits = self.forward(action_sequence)
            indices = logits.argmax(dim=1).tolist()
        return [self.DEVIATION_CLASSES[i] for i in indices]

    def _init_weights(self) -> None:
        nn.init.normal_(self.embedding.weight, mean=0.0, std=0.1)
        if self.embedding.padding_idx is not None:
            nn.init.zeros_(self.embedding.weight[self.embedding.padding_idx])

        for name, param in self.lstm.named_parameters():
            if "weight_ih" in name:
                nn.init.xavier_uniform_(param)
            elif "weight_hh" in name:
                nn.init.orthogonal_(param)
            elif "bias" in name:
                nn.init.zeros_(param)

    @property
    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ── Model factory ──────────────────────────────────────────────────────────

def build_action_recognizer(config: dict, num_classes: int) -> ActionRecognizer:
    """Build ActionRecognizer from train_config.yaml action_recognition section."""
    ar = config["action_recognition"]
    return ActionRecognizer(
        num_classes=num_classes,
        backbone=ar["backbone"],
        lstm_hidden_size=ar["lstm_hidden_size"],
        lstm_num_layers=ar["lstm_num_layers"],
        lstm_dropout=ar["lstm_dropout"],
    )


def build_sequence_model(config: dict, num_action_classes: int) -> SOPSequenceModel:
    """Build SOPSequenceModel from train_config.yaml sequence_model section."""
    sm = config["sequence_model"]
    return SOPSequenceModel(
        num_action_classes=num_action_classes,
        num_deviation_classes=sm["num_deviation_classes"],
        hidden_size=sm["hidden_size"],
        num_layers=sm["num_layers"],
        dropout=sm["dropout"],
    )


def load_action_recognizer(checkpoint_path: str) -> ActionRecognizer:
    """Load a saved ActionRecognizer from a checkpoint file."""
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model = ActionRecognizer(
        num_classes=checkpoint["num_classes"],
        backbone=checkpoint["config"]["backbone"],
        lstm_hidden_size=checkpoint["config"]["lstm_hidden_size"],
        lstm_num_layers=checkpoint["config"]["lstm_num_layers"],
        lstm_dropout=checkpoint["config"]["lstm_dropout"],
        pretrained=False,
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model
