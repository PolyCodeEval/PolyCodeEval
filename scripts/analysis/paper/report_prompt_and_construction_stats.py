from __future__ import annotations

import json
from collections import defaultdict

from common import FINALRESULTS_ROOT, RESULTS_ROOT, load_json, round1


def js_group(language: str) -> str:
    return "javascript" if language in {"javascript", "typescript"} else language


def aggregate_coverage_mean(summary_path: str) -> dict[str, float]:
    data = load_json(FINALRESULTS_ROOT / summary_path)
    groups: dict[str, list[float]] = defaultdict(list)
    for row in data["projects"]:
        groups[js_group(row["language"])].append(float(row["project_line_coverage_pct"]))
    return {lang: round1(sum(vals) / len(vals)) for lang, vals in groups.items()}


def aggregate_level_coverage(summary_path: str, *, weighted: bool) -> dict[str, float]:
    data = load_json(FINALRESULTS_ROOT / summary_path)
    sums: dict[str, float] = defaultdict(float)
    weights: dict[str, float] = defaultdict(float)
    for row in data["projects"]:
        lang = js_group(row["language"])
        value = float(row["avg_coverage_pct"])
        weight = float(row["task_count"]) if weighted else 1.0
        sums[lang] += value * weight
        weights[lang] += weight
    out = {lang: round1(sums[lang] / weights[lang]) for lang in sums}
    out["total"] = round1(sum(sums.values()) / sum(weights.values()))
    return out


def aggregate_baseline_improved() -> dict[str, dict[str, float]]:
    baseline = load_json(RESULTS_ROOT / "coverage_baseline" / "summary.json")
    improved = load_json(RESULTS_ROOT / "coverage" / "summary.json")

    def _mean(data: dict) -> dict[str, float]:
        groups: dict[str, list[float]] = defaultdict(list)
        for row in data["projects"]:
            value = row.get("line_coverage_pct")
            if value is None:
                continue
            groups[js_group(row["language"])].append(float(value))
        out = {lang: round1(sum(vals) / len(vals)) for lang, vals in groups.items()}
        out["total"] = round1(sum(sum(vals) for vals in groups.values()) / sum(len(vals) for vals in groups.values()))
        return out

    base = _mean(baseline)
    imp = _mean(improved)
    keys = sorted(set(base) | set(imp))
    return {
        "baseline": base,
        "improved": imp,
        "gain_pp": {key: round1(imp[key] - base[key]) for key in keys if key in base and key in imp},
    }


def main() -> None:
    l0_l1_prompt = load_json(FINALRESULTS_ROOT / "l0_prompt_score" / "re_eval_final.json")
    l2_prompt = {
        judge: load_json(FINALRESULTS_ROOT / "l2_prompt_score" / judge / "summary.json")
        for judge in ["sonnet4.6_judge", "dpskv4_judge", "gpt5.4_judge"]
    }
    l3_prompt = {
        judge: load_json(FINALRESULTS_ROOT / "l3_prompt_score" / judge / "summary.json")
        for judge in ["sonnet4.6_judge", "dpskv4pro_judge", "gpt5.4_judge"]
    }

    coverage_improvement = aggregate_baseline_improved()
    coverage_stats = {
        "L0/L1_functional": aggregate_level_coverage("coverage_report/L0/summary.json", weighted=False),
        "L2_file": aggregate_level_coverage("coverage_report/L2/summary.json", weighted=True),
        "L3_function": aggregate_level_coverage("coverage_report/L3/summary.json", weighted=True),
    }

    construction_cost = {
        "prompt_construction": load_json(FINALRESULTS_ROOT / "datasets_token_usage" / "claude_uasge.json"),
        "coverage_augmentation": load_json(FINALRESULTS_ROOT / "datasets_token_usage" / "blackboxadd_uage.json"),
    }

    payload = {
        "prompt_quality_l0_l1": {
            "source": str(FINALRESULTS_ROOT / "l0_prompt_score" / "re_eval_final.json"),
            "average_scores": l0_l1_prompt["summary"]["average_scores"],
            "overall_average": l0_l1_prompt["summary"]["overall_average"],
            "formula": "For each project and each dimension, take the median score across three judges; then average across the 58 projects.",
        },
        "prompt_quality_l2": {
            judge: {
                "overall": summary["avg_score"],
                "by_language": summary["by_language"],
            }
            for judge, summary in l2_prompt.items()
        },
        "prompt_quality_l3": {
            judge: {
                "overall": summary["avg_score"],
                "by_language": summary["by_language"],
            }
            for judge, summary in l3_prompt.items()
        },
        "coverage_improvement": {
            "source_baseline": str(RESULTS_ROOT / "coverage_baseline" / "summary.json"),
            "source_improved": str(RESULTS_ROOT / "coverage" / "summary.json"),
            "baseline": coverage_improvement["baseline"],
            "improved": coverage_improvement["improved"],
            "gain_pp": coverage_improvement["gain_pp"],
            "note": "JavaScript and TypeScript are merged into a single JS/TS bucket for the paper table.",
        },
        "coverage_statistics_by_level": {
            "source_L0": str(FINALRESULTS_ROOT / "coverage_report" / "L0" / "summary.json"),
            "source_L2": str(FINALRESULTS_ROOT / "coverage_report" / "L2" / "summary.json"),
            "source_L3": str(FINALRESULTS_ROOT / "coverage_report" / "L3" / "summary.json"),
            "values": coverage_stats,
            "formula": {
                "L0/L1_functional": "arithmetic mean of project-level line coverage percentages",
                "L2_file": "task-count-weighted mean of per-project avg_coverage_pct",
                "L3_function": "task-count-weighted mean of per-project avg_coverage_pct",
            },
        },
        "dataset_construction_cost": {
            "prompt_construction": {
                "tokens_m": round(construction_cost["prompt_construction"]["totalTokens"] / 1_000_000, 2),
                "cost_usd": round(construction_cost["prompt_construction"]["totalCost"], 2),
            },
            "coverage_augmentation": {
                "tokens_m": round(construction_cost["coverage_augmentation"]["totalTokens"] / 1_000_000, 2),
                "cost_usd": round(construction_cost["coverage_augmentation"]["totalCost"], 2),
            },
            "total": {
                "tokens_m": round(
                    (construction_cost["prompt_construction"]["totalTokens"] + construction_cost["coverage_augmentation"]["totalTokens"]) / 1_000_000,
                    2,
                ),
                "cost_usd": round(
                    construction_cost["prompt_construction"]["totalCost"] + construction_cost["coverage_augmentation"]["totalCost"],
                    2,
                ),
            },
        },
    }

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
