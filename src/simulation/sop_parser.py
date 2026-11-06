"""
SOP Parser — loads and validates SOP definitions from YAML or JSON files.

Usage:
    sop = load_sop("data/sops/motor_wiring_v1.yaml")
    all_sops = load_all_sops("data/sops/")
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Union

import yaml
from pydantic import ValidationError

from src.simulation.sop_schema import SOP

# Supported file extensions
_SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".json"}


def load_sop(path: Union[str, Path]) -> SOP:
    """
    Load and validate a single SOP from a YAML or JSON file.

    The file may contain the SOP data at the top level, or nested under
    a top-level 'sop:' key (as shown in Architecture.md examples).

    Args:
        path: Path to the YAML or JSON SOP file.

    Returns:
        Validated SOP instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unsupported, the file is empty,
                    or the content fails schema validation.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"SOP file not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported SOP file format: '{suffix}'. "
            f"Supported formats: {sorted(_SUPPORTED_EXTENSIONS)}"
        )

    with open(path, encoding="utf-8") as f:
        if suffix == ".json":
            raw = json.load(f)
        else:
            raw = yaml.safe_load(f)  # safe_load — never yaml.load()

    if raw is None:
        raise ValueError(f"SOP file is empty: {path}")

    if not isinstance(raw, dict):
        raise ValueError(f"SOP file must contain a YAML/JSON mapping, got {type(raw).__name__}: {path}")

    # Support both top-level 'sop:' wrapper and bare SOP data
    if "sop" in raw and isinstance(raw["sop"], dict):
        raw = raw["sop"]

    try:
        return SOP.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"SOP validation failed for '{path}':\n{exc}") from exc


def load_all_sops(directory: Union[str, Path]) -> dict[str, SOP]:
    """
    Load and validate all YAML/JSON SOP files from a directory.

    Files are sorted alphabetically before loading so the result is
    deterministic across runs (important for reproducibility).

    Args:
        directory: Directory containing SOP files.

    Returns:
        Mapping of sop.id → SOP for every valid file found.

    Raises:
        FileNotFoundError: If the directory does not exist.
        ValueError: If any SOP file fails to parse (all errors are collected
                    and raised together so the caller sees every problem at once).
    """
    directory = Path(directory)

    if not directory.exists():
        raise FileNotFoundError(f"SOP directory not found: {directory}")

    if not directory.is_dir():
        raise ValueError(f"Expected a directory, got a file: {directory}")

    candidate_files: list[Path] = []
    for ext in _SUPPORTED_EXTENSIONS:
        candidate_files.extend(sorted(directory.glob(f"*{ext}")))

    if not candidate_files:
        return {}

    sops: dict[str, SOP] = {}
    errors: list[str] = []

    for file_path in candidate_files:
        try:
            sop = load_sop(file_path)
            if sop.id in sops:
                errors.append(
                    f"Duplicate SOP id '{sop.id}' found in '{file_path}' "
                    f"(already loaded from another file)"
                )
            else:
                sops[sop.id] = sop
        except (ValueError, FileNotFoundError) as exc:
            errors.append(str(exc))

    if errors:
        raise ValueError(
            f"Errors loading SOPs from '{directory}':\n"
            + "\n".join(f"  • {e}" for e in errors)
        )

    return sops


def sop_to_dict(sop: SOP) -> dict:
    """Serialise an SOP back to a plain dictionary (for saving or API responses)."""
    return sop.model_dump()


def sop_to_yaml(sop: SOP) -> str:
    """Serialise an SOP to YAML string."""
    return yaml.dump({"sop": sop_to_dict(sop)}, allow_unicode=True, sort_keys=False)


def sop_to_json(sop: SOP, indent: int = 2) -> str:
    """Serialise an SOP to a JSON string."""
    return json.dumps({"sop": sop_to_dict(sop)}, indent=indent, ensure_ascii=False)
