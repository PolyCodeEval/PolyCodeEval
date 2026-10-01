"""Scoring helpers for L0 project-level evaluation."""

from __future__ import annotations

RESULT_SCHEMA_VERSION = "l0_scoring_v4_codex_review"
SCORE_SCALE = "0-5"
SCORE_FORMULA = "0.4*C + 0.25*F + 0.25*A + 0.1*H"


def is_current_result(result: dict) -> bool:
    """Return True when a cached result matches the current scoring schema."""
    return result.get("result_schema_version") == RESULT_SCHEMA_VERSION
