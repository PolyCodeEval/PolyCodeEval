from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(".")
INPUT_DIR = REPO_ROOT / "output" / "l0_prompt_reval_gpt54"
TARGET_DIR = REPO_ROOT / "finalresults" / "l0_prompt_score" / "gpt5.4_judge"
LANG_ORDER = ["cpp", "go", "java", "javascript", "python"]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def round2(v: float) -> float:
    return round(v + 1e-12, 2)


def round4(v: float) -> float:
    return round(v + 1e-12, 4)


def overall_score(scores: dict) -> float:
    return mean(
        [
            float(scores["completeness"]["score"]),
            float(scores["unambiguity"]["score"]),
            float(scores["testability"]["score"]),
            float(scores["consistency"]["score"]),
        ]
    )


def collect_rows() -> list[dict]:
    rows = []
    for lang in LANG_ORDER:
        path = INPUT_DIR / f"{lang}.json"
        rows.extend(load_json(path))
    return rows


def build_l0_summary(rows: list[dict]) -> dict:
    by_language: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        lang = row["project"].split("/", 1)[0]
        by_language[lang].append(row)

    all_projects = []
    by_language_payload = {}
    all_comp, all_unamb, all_test, all_cons, all_overall = [], [], [], [], []

    for lang in LANG_ORDER:
        lang_rows = by_language[lang]
        projects = []
        comp_vals, unamb_vals, test_vals, cons_vals, overall_vals = [], [], [], [], []
        for row in lang_rows:
            scores = row["scores"]
            comp = float(scores["completeness"]["score"])
            unamb = float(scores["unambiguity"]["score"])
            test = float(scores["testability"]["score"])
            cons = float(scores["consistency"]["score"])
            ov = overall_score(scores)
            comp_vals.append(comp)
            unamb_vals.append(unamb)
            test_vals.append(test)
            cons_vals.append(cons)
            overall_vals.append(ov)
            projects.append(
                {
                    "project": row["project"],
                    "overall_score": round2(ov),
                    "scores": {
                        "completeness": comp,
                        "unambiguity": unamb,
                        "testability": test,
                        "consistency": cons,
                    },
                    "reasons": {
                        "completeness": scores["completeness"]["reason"],
                        "unambiguity": scores["unambiguity"]["reason"],
                        "testability": scores["testability"]["reason"],
                        "consistency": scores["consistency"]["reason"],
                    },
                }
            )
        all_projects.extend(projects)
        all_comp.extend(comp_vals)
        all_unamb.extend(unamb_vals)
        all_test.extend(test_vals)
        all_cons.extend(cons_vals)
        all_overall.extend(overall_vals)
        by_language_payload[lang] = {
            "count": len(projects),
            "avg_scores": {
                "completeness": round2(mean(comp_vals)),
                "unambiguity": round2(mean(unamb_vals)),
                "testability": round2(mean(test_vals)),
                "consistency": round2(mean(cons_vals)),
                "overall": round2(mean(overall_vals)),
            },
            "projects": projects,
        }

    return {
        "judge_model": "gpt-5.4",
        "review_type": "l0_prompt_review",
        "scoring_method": "manual_re-review_with_fixed_prompt",
        "weights": {
            "completeness": 0.25,
            "unambiguity": 0.25,
            "testability": 0.25,
            "consistency": 0.25,
        },
        "total_tasks": len(rows),
        "completed": len(rows),
        "failed": 0,
        "overall_avg_scores": {
            "completeness": round2(mean(all_comp)),
            "unambiguity": round2(mean(all_unamb)),
            "testability": round2(mean(all_test)),
            "consistency": round2(mean(all_cons)),
            "overall": round2(mean(all_overall)),
        },
        "by_language": by_language_payload,
        "all_projects": all_projects,
    }


def build_summary(rows: list[dict]) -> dict:
    by_language: dict[str, list[dict]] = defaultdict(list)
    by_project_payload = {}
    for row in rows:
        lang, proj = row["project"].split("/", 1)
        by_language[lang].append(row)
        by_project_payload[row["project"]] = {
            "total": 1,
            "avg_overall_score": round2(overall_score(row["scores"])),
            "avg_completeness": float(row["scores"]["completeness"]["score"]),
            "avg_unambiguity": float(row["scores"]["unambiguity"]["score"]),
            "avg_testability": float(row["scores"]["testability"]["score"]),
            "avg_consistency": float(row["scores"]["consistency"]["score"]),
        }

    payload = {
        "review_type": "l0_prompt_review",
        "review_schema_version": "1.0",
        "judge_model": "gpt-5.4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "completed": len(rows),
        "failed": 0,
        "avg_overall_score": 0.0,
        "avg_completeness": 0.0,
        "avg_unambiguity": 0.0,
        "avg_testability": 0.0,
        "avg_consistency": 0.0,
        "by_language": {},
        "by_project": by_project_payload,
        "failed_tasks": [],
    }

    overall_scores = []
    comp_all, unamb_all, test_all, cons_all = [], [], [], []
    for lang in LANG_ORDER:
        lang_rows = by_language[lang]
        comp_vals = [float(r["scores"]["completeness"]["score"]) for r in lang_rows]
        unamb_vals = [float(r["scores"]["unambiguity"]["score"]) for r in lang_rows]
        test_vals = [float(r["scores"]["testability"]["score"]) for r in lang_rows]
        cons_vals = [float(r["scores"]["consistency"]["score"]) for r in lang_rows]
        overall_vals = [overall_score(r["scores"]) for r in lang_rows]
        payload["by_language"][lang] = {
            "total": len(lang_rows),
            "avg_overall_score": round4(mean(overall_vals)),
            "avg_completeness": round4(mean(comp_vals)),
            "avg_unambiguity": round4(mean(unamb_vals)),
            "avg_testability": round4(mean(test_vals)),
            "avg_consistency": round4(mean(cons_vals)),
        }
        overall_scores.extend(overall_vals)
        comp_all.extend(comp_vals)
        unamb_all.extend(unamb_vals)
        test_all.extend(test_vals)
        cons_all.extend(cons_vals)

    payload["avg_overall_score"] = round4(mean(overall_scores))
    payload["avg_completeness"] = round4(mean(comp_all))
    payload["avg_unambiguity"] = round4(mean(unamb_all))
    payload["avg_testability"] = round4(mean(test_all))
    payload["avg_consistency"] = round4(mean(cons_all))
    return payload


def main() -> None:
    rows = collect_rows()
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    l0_summary = build_l0_summary(rows)
    summary = build_summary(rows)
    (TARGET_DIR / "l0_summary.json").write_text(json.dumps(l0_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (TARGET_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
