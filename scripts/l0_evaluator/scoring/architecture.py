"""Architecture scoring for L0 tasks."""

from __future__ import annotations

from pathlib import Path

from .codex_review import CodexReviewError, run_codex_review
from .prompts import build_codex_architecture_analysis_prompt
from .repo_snapshot import (
    build_file_tree,
    collect_key_snippets,
    detect_stack_profile,
    summarize_prompt_requirements,
)


def _review_to_markdown(review: dict) -> str:
    sections = [
        "### Stack Inference",
        review.get("stack_inference", "No stack inference provided."),
        "### Scoring Mode",
        review.get("mode_explanation", "No mode explanation provided."),
        "### Strengths",
        "\n".join(f"- {item}" for item in review.get("strengths", []) or ["None noted."]),
        "### Issues",
        "\n".join(f"- {item}" for item in review.get("issues", []) or ["None noted."]),
        "### Stack Mismatches",
        "\n".join(f"- {item}" for item in review.get("stack_mismatches", []) or ["None noted."]),
        "### Reference Gaps",
        "\n".join(f"- {item}" for item in review.get("reference_gaps", []) or ["None noted."]),
    ]
    return "\n\n".join(sections)


def score_architecture(
    *,
    task_dir: Path,
    repo_root: Path,
    language: str,
    provider: str,
    model: str,
) -> tuple[float | None, dict, str]:
    prompt_text = (task_dir / "prompt.md").read_text(encoding="utf-8")
    prompt_excerpt = summarize_prompt_requirements(prompt_text)
    file_tree = build_file_tree(repo_root)
    snippets = collect_key_snippets(repo_root)
    stack_profile = detect_stack_profile(repo_root, language)

    if not stack_profile:
        stack_profile = {
            "language": language,
            "framework": "unknown",
            "app_style": "unknown",
            "build_system": "unknown",
            "persistence": "unknown",
            "frontend_presence": False,
            "confidence": 0.0,
        }

    prompt_payload = build_codex_architecture_analysis_prompt(
        prompt_excerpt=prompt_excerpt,
        file_tree=file_tree,
        stack_profile=stack_profile,
        snippets=snippets,
    )
    judge = None
    try:
        judge = run_codex_review(
            task_dir=task_dir,
            repo_root=repo_root,
            mode="architecture",
            analysis_prompt=prompt_payload,
            prompt_text=prompt_text,
            extra_payload={
                "stack_profile": stack_profile,
                "file_tree": file_tree,
                "snippets": snippets,
            },
            schema={
                "type": "object",
                "properties": {
                    "subscores": {
                        "type": "object",
                        "properties": {
                            "structure_reasonableness": {"type": "number"},
                            "stack_alignment": {"type": "number"},
                            "reference_alignment": {"type": "number"},
                        },
                        "required": [
                            "structure_reasonableness",
                            "stack_alignment",
                            "reference_alignment",
                        ],
                        "additionalProperties": False,
                    },
                    "review": {
                        "type": "object",
                        "properties": {
                            "stack_inference": {"type": "string"},
                            "mode_explanation": {"type": "string"},
                            "strengths": {"type": "array", "items": {"type": "string"}},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "stack_mismatches": {"type": "array", "items": {"type": "string"}},
                            "reference_gaps": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "stack_inference",
                            "mode_explanation",
                            "strengths",
                            "issues",
                            "stack_mismatches",
                            "reference_gaps",
                        ],
                        "additionalProperties": False,
                    },
                },
                "required": ["subscores", "review"],
                "additionalProperties": False,
            },
            model=None,
        )
    except (CodexReviewError, Exception) as exc:
        review_md = "\n\n".join([
            "### Stack Inference",
            "Codex architecture review failed.",
            "### Scoring Mode",
            "Codex review failed after retry; architecture score is set to -1.",
            "### Strengths",
            "- Not available because Codex review failed.",
            "### Issues",
            f"- Review error: {exc}",
            "### Stack Mismatches",
            "- Not available because Codex review failed.",
            "### Reference Gaps",
            "- Not available because Codex review failed.",
        ])
        detail = {
            "status": "error",
            "stack_profile": stack_profile,
            "reference_mode": "codex_review",
            "reference_sources": [],
            "reference_architecture_summary": "",
            "reference_checklist": [],
            "subscores": {
                "structure_reasonableness": -1.0,
                "stack_alignment": -1.0,
                "reference_alignment": -1.0,
            },
            "fallback_reason": "",
            "error": str(exc),
        }
        return -1.0, detail, review_md

    subscores = judge.get("subscores", {})

    def _score(name: str) -> float:
        try:
            value = float(subscores.get(name, 0.0))
        except (TypeError, ValueError):
            value = 0.0
        return max(0.0, min(5.0, value))

    structure = _score("structure_reasonableness")
    stack_align = _score("stack_alignment")
    reference_align = _score("reference_alignment")
    score = round((structure + stack_align + reference_align) / 3, 2)

    detail = {
        "status": "ok",
        "stack_profile": stack_profile,
        "reference_mode": "codex_review",
        "reference_sources": [],
        "reference_architecture_summary": "",
        "reference_checklist": [],
        "subscores": {
            "structure_reasonableness": structure,
            "stack_alignment": stack_align,
            "reference_alignment": reference_align,
        },
        "fallback_reason": "",
    }
    return score, detail, _review_to_markdown(judge.get("review", {}))
