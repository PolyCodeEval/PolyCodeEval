"""Faithfulness scoring for L0 tasks."""

from __future__ import annotations

import re
from pathlib import Path

from .codex_review import CodexReviewError, run_codex_review
from .prompts import build_codex_faithfulness_analysis_prompt
from .repo_snapshot import build_file_tree, find_evidence, summarize_prompt_requirements


def _extract_project_requirements(prompt_text: str) -> str:
    marker = "# Project Requirements"
    if marker in prompt_text:
        return prompt_text.split(marker, 1)[1].strip()
    return prompt_text.strip()


def _normalize_requirement_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip(" -*\t")).strip()


def _collect_requirements(section: str) -> list[dict]:
    requirements: list[dict] = []
    current_kind = "feature"
    feature_idx = 1
    constraint_idx = 1

    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("## constraints") or lowered.startswith("### constraints"):
            current_kind = "constraint"
            continue
        if lowered.startswith("## ") or lowered.startswith("### "):
            if any(token in lowered for token in ("constraint", "security", "non-functional")):
                current_kind = "constraint"
            else:
                current_kind = "feature"
            continue
        if line.startswith("|") and line.count("|") >= 2 and not re.search(r"^-{3,}$", line.replace("|", "").strip()):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells and not all(set(cell) <= {"-", ":"} for cell in cells):
                text = " - ".join(cell for cell in cells if cell)
                text = _normalize_requirement_text(text)
                if text and text.lower() not in {"export - description", "export - description "}:
                    req_id = f"{'C' if current_kind == 'constraint' else 'F'}{constraint_idx if current_kind == 'constraint' else feature_idx:03d}"
                    requirements.append({"id": req_id, "type": current_kind, "text": text})
                    if current_kind == "constraint":
                        constraint_idx += 1
                    else:
                        feature_idx += 1
            continue
        if line.startswith(("-", "*")) or re.match(r"^\d+\.", line):
            text = _normalize_requirement_text(re.sub(r"^(\*|-|\d+\.)\s*", "", line))
            if text:
                req_id = f"{'C' if current_kind == 'constraint' else 'F'}{constraint_idx if current_kind == 'constraint' else feature_idx:03d}"
                requirements.append({"id": req_id, "type": current_kind, "text": text})
                if current_kind == "constraint":
                    constraint_idx += 1
                else:
                    feature_idx += 1
            continue
        if current_kind == "constraint" or any(token in lowered for token in ("must", "cannot", "should", "required")):
            text = _normalize_requirement_text(line)
            req_id = f"{'C' if current_kind == 'constraint' else 'F'}{constraint_idx if current_kind == 'constraint' else feature_idx:03d}"
            requirements.append({"id": req_id, "type": current_kind, "text": text})
            if current_kind == "constraint":
                constraint_idx += 1
            else:
                feature_idx += 1

    return requirements


def score_faithfulness(
    *,
    task_dir: Path,
    repo_root: Path,
    provider: str,
    model: str,
) -> tuple[float | None, dict, str]:
    prompt_text = (task_dir / "prompt.md").read_text(encoding="utf-8")
    requirement_section = _extract_project_requirements(prompt_text)
    requirements = _collect_requirements(requirement_section)
    enriched_requirements = [
        {
            **requirement,
            "evidence": find_evidence(repo_root, requirement["text"]),
        }
        for requirement in requirements
    ]

    file_tree = build_file_tree(repo_root)
    try:
        judge = run_codex_review(
            task_dir=task_dir,
            repo_root=repo_root,
            mode="faithfulness",
            analysis_prompt=build_codex_faithfulness_analysis_prompt(
                prompt_excerpt=summarize_prompt_requirements(prompt_text),
                file_tree=file_tree,
                requirements=enriched_requirements,
            ),
            prompt_text=prompt_text,
            extra_payload={"requirements": enriched_requirements, "file_tree": file_tree},
            schema={
                "type": "object",
                "properties": {
                    "requirements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": ["implemented", "partial", "missing", "unclear"],
                                },
                                "reason": {"type": "string"},
                            },
                            "required": ["id", "status", "reason"],
                            "additionalProperties": False,
                        },
                    },
                    "review": {
                        "type": "object",
                        "properties": {
                            "implemented_summary": {"type": "string"},
                            "missing_list": {"type": "array", "items": {"type": "string"}},
                            "critical_constraint_misses": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["implemented_summary", "missing_list", "critical_constraint_misses"],
                        "additionalProperties": False,
                    },
                },
                "required": ["requirements", "review"],
                "additionalProperties": False,
            },
            model=model,
        )
    except (CodexReviewError, Exception) as exc:
        review_md = "\n\n".join([
            "### Implemented Summary",
            "Codex faithfulness review failed after retry.",
            "### Missing List",
            "- Not available because Codex review failed.",
            "### Critical Constraint Misses",
            f"- Review error: {exc}",
        ])
        detail = {
            "status": "error",
            "requirements": enriched_requirements,
            "feature_count": len([req for req in enriched_requirements if req["type"] == "feature"]),
            "constraint_count": len([req for req in enriched_requirements if req["type"] == "constraint"]),
            "implemented_count": 0,
            "partial_count": 0,
            "missing_count": 0,
            "unclear_count": 0,
            "feature_coverage": 0.0,
            "constraint_coverage": 0.0,
            "fallback_used": False,
            "error": str(exc),
        }
        return -1.0, detail, review_md

    decisions = {item["id"]: item for item in (judge or {}).get("requirements", []) if item.get("id")}

    implemented = partial = missing = unclear = 0
    for requirement in enriched_requirements:
        decision = decisions.get(requirement["id"], {})
        status = decision.get("status", "")
        if status not in {"implemented", "partial", "missing", "unclear"}:
            evidence_count = len(requirement.get("evidence") or [])
            if evidence_count >= 2:
                status = "implemented"
            elif evidence_count == 1:
                status = "partial"
            else:
                status = "missing"
        requirement["status"] = status
        requirement["reason"] = decision.get("reason", "")
        if status == "implemented":
            implemented += 1
        elif status == "partial":
            partial += 1
        elif status == "missing":
            missing += 1
        else:
            unclear += 1

    features = [req for req in enriched_requirements if req["type"] == "feature"]
    constraints = [req for req in enriched_requirements if req["type"] == "constraint"]

    def _coverage(items: list[dict]) -> float:
        if not items:
            return 0.0
        total = 0.0
        for item in items:
            if item["status"] == "implemented":
                total += 1.0
            elif item["status"] == "partial":
                total += 0.5
        return total / len(items)

    feature_coverage = _coverage(features)
    constraint_coverage = _coverage(constraints) if constraints else feature_coverage
    score = round(5 * ((feature_coverage + constraint_coverage) / 2), 2) if enriched_requirements else 0.0

    review = judge.get("review", {})
    review_md = "\n\n".join([
        "### Implemented Summary",
        review.get("implemented_summary", "No summary provided."),
        "### Missing List",
        "\n".join(f"- {item}" for item in review.get("missing_list", []) or ["None noted."]),
        "### Critical Constraint Misses",
        "\n".join(f"- {item}" for item in review.get("critical_constraint_misses", []) or ["None noted."]),
    ])

    detail = {
        "status": "ok",
        "requirements": enriched_requirements,
        "feature_count": len(features),
        "constraint_count": len(constraints),
        "implemented_count": implemented,
        "partial_count": partial,
        "missing_count": missing,
        "unclear_count": unclear,
        "feature_coverage": round(feature_coverage, 4),
        "constraint_coverage": round(constraint_coverage, 4),
        "fallback_used": False,
    }
    return score, detail, review_md
