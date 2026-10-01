#!/usr/bin/env python3
import json
import math
from pathlib import Path
from statistics import mean, median

from scipy.stats import wilcoxon


ROOT = Path(".")
REPORTS_DIR = ROOT / "docs" / "reports"


def load_json(path: str):
    with open(ROOT / path, "r", encoding="utf-8") as f:
        return json.load(f)


def holm_adjust(p_values):
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    m = len(p_values)
    adjusted = [None] * m
    running_max = 0.0
    for rank, (idx, p) in enumerate(indexed, start=1):
        adj = (m - rank + 1) * p
        running_max = max(running_max, adj)
        adjusted[idx] = min(running_max, 1.0)
    return adjusted


def paired_project_metric(summary_path_a: str, summary_path_b: str, metric: str):
    a = load_json(summary_path_a)["by_project"]
    b = load_json(summary_path_b)["by_project"]
    keys = sorted(set(a) & set(b))
    x = [float(a[k][metric]) for k in keys]
    y = [float(b[k][metric]) for k in keys]
    return keys, x, y


def paired_task_metric(summary_path_a: str, summary_path_b: str, metric: str):
    a = load_json(summary_path_a)["by_task"]
    b = load_json(summary_path_b)["by_task"]
    keys = sorted(set(a) & set(b))
    x = [float(a[k][metric]) for k in keys]
    y = [float(b[k][metric]) for k in keys]
    return keys, x, y


def summarize_test(name: str, level: str, hypothesis: str, keys, x, y):
    deltas = [yi - xi for xi, yi in zip(x, y)]
    nonzero = [d for d in deltas if abs(d) > 1e-12]
    if not nonzero:
        result = {
            "name": name,
            "level": level,
            "hypothesis": hypothesis,
            "n_pairs": len(keys),
            "n_nonzero": 0,
            "median_a": median(x),
            "median_b": median(y),
            "median_delta": 0.0,
            "mean_delta": 0.0,
            "positive_deltas": 0,
            "negative_deltas": 0,
            "wilcoxon_statistic": 0.0,
            "p_value": 1.0,
        }
        return result

    stat = wilcoxon(x, y, zero_method="wilcox", correction=False, alternative="two-sided", method="auto")
    positive = sum(1 for d in nonzero if d > 0)
    negative = sum(1 for d in nonzero if d < 0)
    result = {
        "name": name,
        "level": level,
        "hypothesis": hypothesis,
        "n_pairs": len(keys),
        "n_nonzero": len(nonzero),
        "median_a": median(x),
        "median_b": median(y),
        "median_delta": median(deltas),
        "mean_delta": mean(deltas),
        "positive_deltas": positive,
        "negative_deltas": negative,
        "wilcoxon_statistic": float(stat.statistic),
        "p_value": float(stat.pvalue),
    }
    return result


def fmt(v, digits=4):
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if math.isnan(v):
            return "nan"
        return f"{v:.{digits}f}"
    return str(v)


def main():
    specs = [
        {
            "name": "L3 RepoCoder-GPT-5.4 vs Direct-GPT-5.4 on task score",
            "level": "L3",
            "hypothesis": "Repository-aware retrieval improves function-level execution score.",
            "loader": paired_task_metric,
            "a_path": "finalresults/L3/direct/direct_eval_gpt54/summary.json",
            "b_path": "finalresults/L3/repocoder/repoder_eval_gpt5.4/summary.json",
            "metric": "score",
        },
        {
            "name": "L3 RepoCoder-GPT-5.4 vs HCP-GPT-5.4 on task score",
            "level": "L3",
            "hypothesis": "The simpler iterative retrieval pipeline remains stronger than HCP under GPT-5.4.",
            "loader": paired_task_metric,
            "a_path": "finalresults/L3/HCP/hcpcoder_eval_gpt54/summary.json",
            "b_path": "finalresults/L3/repocoder/repoder_eval_gpt5.4/summary.json",
            "metric": "score",
        },
        {
            "name": "L3 RepoCoder-GPT-5.4 vs AlignCoder-GPT-5.4 on task score",
            "level": "L3",
            "hypothesis": "The simpler iterative retrieval pipeline remains stronger than AlignCoder under GPT-5.4.",
            "loader": paired_task_metric,
            "a_path": "finalresults/L3/aligncoder/aligncoder_eval_gpt54/summary.json",
            "b_path": "finalresults/L3/repocoder/repoder_eval_gpt5.4/summary.json",
            "metric": "score",
        },
        {
            "name": "L2 Codex-GPT-5.4 agent vs Direct-GPT-5.4 on compile score",
            "level": "L2",
            "hypothesis": "Agent-mode repository interaction improves file-level compilability under GPT-5.4.",
            "loader": paired_task_metric,
            "a_path": "finalresults/L2/direct_gpt_l2_eval/summary.json",
            "b_path": "finalresults/L2/codex_l2_eval/summary.json",
            "metric": "compile_score",
        },
        {
            "name": "L2 Claude Code-Sonnet agent vs Direct-Sonnet on compile score",
            "level": "L2",
            "hypothesis": "Agent-mode repository interaction improves file-level compilability under Sonnet 4.6.",
            "loader": paired_task_metric,
            "a_path": "finalresults/L2/direct_sonnet_l2_eval/summary.json",
            "b_path": "finalresults/L2/cc_l2_eval/summary.json",
            "metric": "compile_score",
        },
        {
            "name": "Claude Code L1 vs L0 on project correctness",
            "level": "L0/L1",
            "hypothesis": "Providing a full project skeleton changes project-level correctness.",
            "loader": paired_project_metric,
            "a_path": "finalresults/L0/cc_l0_full_sonnet_eval_new/summary.json",
            "b_path": "finalresults/L1/cc_l1_full_sonnet_eval/summary.json",
            "metric": "avg_correctness",
        },
        {
            "name": "Codex L1 vs L0 on project correctness",
            "level": "L0/L1",
            "hypothesis": "Providing a full project skeleton changes project-level correctness.",
            "loader": paired_project_metric,
            "a_path": "finalresults/L0/codex_l0_full_gpt54_eval/summary.json",
            "b_path": "finalresults/L1/codex_l1_full_gpt54_eval/summary.json",
            "metric": "avg_correctness",
        },
        {
            "name": "Claude Code L0 vs Oracle on health score",
            "level": "L0",
            "hypothesis": "Generated repositories receive different static health scores from Oracle.",
            "loader": paired_project_metric,
            "a_path": "finalresults/oracle_l0_eval_final/summary.json",
            "b_path": "finalresults/L0/cc_l0_full_sonnet_eval_new/summary.json",
            "metric": "avg_health",
        },
        {
            "name": "Codex L0 vs Oracle on health score",
            "level": "L0",
            "hypothesis": "Generated repositories receive different static health scores from Oracle.",
            "loader": paired_project_metric,
            "a_path": "finalresults/oracle_l0_eval_final/summary.json",
            "b_path": "finalresults/L0/codex_l0_full_gpt54_eval/summary.json",
            "metric": "avg_health",
        },
    ]

    results = []
    for spec in specs:
        keys, x, y = spec["loader"](spec["a_path"], spec["b_path"], spec["metric"])
        results.append(summarize_test(spec["name"], spec["level"], spec["hypothesis"], keys, x, y))

    adjusted = holm_adjust([r["p_value"] for r in results])
    for r, p_adj in zip(results, adjusted):
        r["p_value_holm"] = p_adj
        r["significant_0_05"] = p_adj < 0.05

    json_path = REPORTS_DIR / "significance_tests_selected.json"
    md_path = REPORTS_DIR / "significance_tests_selected.md"
    csv_path = REPORTS_DIR / "significance_tests_selected.csv"

    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = []
    lines.append("# Selected Wilcoxon Signed-Rank Tests\n")
    lines.append("This report records a small batch of paired significance tests used to support selected conclusions in the paper.\n")
    lines.append("All tests are two-sided Wilcoxon signed-rank tests on paired task- or project-level scores. Holm correction is applied across the five tests.\n")
    lines.append("\n")
    lines.append("| Test | Level | Pairs | Nonzero | Median A | Median B | Median Δ (B-A) | Mean Δ (B-A) | +Δ | -Δ | W | p | Holm-adjusted p | Significant |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    for r in results:
        lines.append(
            f"| {r['name']} | {r['level']} | {r['n_pairs']} | {r['n_nonzero']} | "
            f"{fmt(r['median_a'])} | {fmt(r['median_b'])} | {fmt(r['median_delta'])} | {fmt(r['mean_delta'])} | "
            f"{r['positive_deltas']} | {r['negative_deltas']} | {fmt(r['wilcoxon_statistic'])} | "
            f"{fmt(r['p_value'], 6)} | {fmt(r['p_value_holm'], 6)} | "
            f"{'Yes' if r['significant_0_05'] else 'No'} |\n"
        )
    lines.append("\n")
    lines.append("## Interpretation Notes\n")
    lines.append("- `Median A` and `Median B` denote the paired medians of the baseline and comparison condition, respectively.\n")
    lines.append("- `Median Δ (B-A)` and `Mean Δ (B-A)` report the paired difference from condition A to condition B. Positive values indicate that condition B tends to score higher.\n")
    lines.append("- `+Δ` and `-Δ` count nonzero paired differences favoring B and A, respectively.\n")
    lines.append("- For project-level L0/L1 correctness and L0 health, each pair corresponds to one project. For L3, each pair corresponds to one function-level task.\n")
    lines.append("\n")
    lines.append("## Test Definitions\n")
    for r in results:
        lines.append(f"- **{r['name']}**: {r['hypothesis']}\n")
    md_path.write_text("".join(lines), encoding="utf-8")

    csv_lines = [
        "test,level,n_pairs,n_nonzero,median_a,median_b,median_delta,mean_delta,positive_deltas,negative_deltas,wilcoxon_statistic,p_value,p_value_holm,significant_0_05"
    ]
    for r in results:
        csv_lines.append(
            ",".join([
                '"' + r["name"].replace('"', '""') + '"',
                r["level"],
                str(r["n_pairs"]),
                str(r["n_nonzero"]),
                fmt(r["median_a"]),
                fmt(r["median_b"]),
                fmt(r["median_delta"]),
                fmt(r["mean_delta"]),
                str(r["positive_deltas"]),
                str(r["negative_deltas"]),
                fmt(r["wilcoxon_statistic"]),
                fmt(r["p_value"], 6),
                fmt(r["p_value_holm"], 6),
                "1" if r["significant_0_05"] else "0",
            ])
        )
    csv_path.write_text("\n".join(csv_lines) + "\n", encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
