"""Orchestrate all L0 scoring dimensions."""

from __future__ import annotations

from pathlib import Path

from . import RESULT_SCHEMA_VERSION, SCORE_FORMULA, SCORE_SCALE
from .architecture import score_architecture
from .correctness import score_correctness
from .faithfulness import score_faithfulness
from .health import score_health


def apply_scoring(
    *,
    result: dict,
    task_dir: Path,
    repo_root: Path,
    language: str,
    docker_image: str,
    judge_provider: str,
    judge_model: str,
) -> dict:
    scored = dict(result)
    correctness_score, correctness_detail = score_correctness(scored)

    scored["result_schema_version"] = RESULT_SCHEMA_VERSION
    scored["score_scale"] = SCORE_SCALE
    scored["score_formula"] = SCORE_FORMULA

    radar_scores = {
        "Correctness": correctness_score,
        "Faithfulness": None,
        "Architecture": None,
        "Health": None,
    }
    dimension_details = {
        "correctness": correctness_detail,
        "faithfulness": {"status": "error"},
        "architecture": {"status": "error"},
        "health": {"status": "error"},
    }
    judge_reviews = {
        "faithfulness_review": "",
        "architecture_review": "",
    }

    try:
        faith_score, faith_detail, faith_review = score_faithfulness(
            task_dir=task_dir,
            repo_root=repo_root,
            provider=judge_provider,
            model=judge_model,
        )
        radar_scores["Faithfulness"] = faith_score
        dimension_details["faithfulness"] = faith_detail
        judge_reviews["faithfulness_review"] = faith_review
    except Exception as exc:  # noqa: BLE001
        dimension_details["faithfulness"] = {"status": "error", "error": str(exc)}

    try:
        arch_score, arch_detail, arch_review = score_architecture(
            task_dir=task_dir,
            repo_root=repo_root,
            language=language,
            provider=judge_provider,
            model=judge_model,
        )
        radar_scores["Architecture"] = arch_score
        dimension_details["architecture"] = arch_detail
        judge_reviews["architecture_review"] = arch_review
    except Exception as exc:  # noqa: BLE001
        dimension_details["architecture"] = {"status": "error", "error": str(exc)}

    try:
        health_score, health_detail = score_health(
            repo_root=repo_root,
            language=language,
            docker_image=docker_image,
        )
        radar_scores["Health"] = health_score
        dimension_details["health"] = health_detail
    except Exception as exc:  # noqa: BLE001
        dimension_details["health"] = {"status": "error", "error": str(exc)}

    if None in (radar_scores["Faithfulness"], radar_scores["Architecture"], radar_scores["Health"]):
        overall_score = None
    else:
        overall_score = round(
            0.4 * radar_scores["Correctness"]
            + 0.25 * radar_scores["Faithfulness"]
            + 0.25 * radar_scores["Architecture"]
            + 0.1 * radar_scores["Health"],
            2,
        )

    scored["radar_scores"] = radar_scores
    scored["overall_score"] = overall_score
    scored["dimension_details"] = dimension_details
    scored["judge_reviews"] = judge_reviews
    return scored
