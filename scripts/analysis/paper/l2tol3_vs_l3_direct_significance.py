#!/usr/bin/env python3
import json
from pathlib import Path
from statistics import mean, median

from scipy.stats import binomtest
from scipy.stats import wilcoxon


ROOT = Path(".")
REPORTS_DIR = ROOT / "docs" / "reports"


def load_summary(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def split_language(task_id: str) -> str:
    return task_id.split("/", 1)[0]


def paired_task_scores(summary_a: dict, summary_b: dict, language: str | None = None):
    by_task_a = summary_a["by_task"]
    by_task_b = summary_b["by_task"]
    keys = sorted(set(by_task_a) & set(by_task_b))
    if language is not None:
        keys = [k for k in keys if split_language(k) == language]
    x = [float(by_task_a[k]["score"]) for k in keys]
    y = [float(by_task_b[k]["score"]) for k in keys]
    return keys, x, y


def summarize(model_label: str, scope_label: str, keys: list[str], x: list[float], y: list[float]) -> dict:
    deltas = [yi - xi for xi, yi in zip(x, y)]
    nonzero = [d for d in deltas if abs(d) > 1e-12]
    if nonzero:
        stat = wilcoxon(x, y, zero_method="wilcox", correction=False, alternative="two-sided", method="auto")
        p_value = float(stat.pvalue)
        w_stat = float(stat.statistic)
    else:
        p_value = 1.0
        w_stat = 0.0
    return {
        "model": model_label,
        "scope": scope_label,
        "n_pairs": len(keys),
        "n_nonzero": len(nonzero),
        "median_direct": median(x) if x else None,
        "median_l2tol3": median(y) if y else None,
        "median_delta": median(deltas) if deltas else None,
        "mean_direct": mean(x) if x else None,
        "mean_l2tol3": mean(y) if y else None,
        "mean_delta": mean(deltas) if deltas else None,
        "positive_deltas": sum(1 for d in nonzero if d > 0),
        "negative_deltas": sum(1 for d in nonzero if d < 0),
        "wilcoxon_statistic": w_stat,
        "p_value": p_value,
    }


def summarize_full_pass_exact(model_label: str, scope_label: str, keys: list[str], x: list[float], y: list[float]) -> dict:
    direct_yes = [v >= 0.999999 for v in x]
    l2tol3_yes = [v >= 0.999999 for v in y]
    both_yes = 0
    l2tol3_only = 0
    direct_only = 0
    both_no = 0
    for a, b in zip(direct_yes, l2tol3_yes):
        if a and b:
            both_yes += 1
        elif (not a) and b:
            l2tol3_only += 1
        elif a and (not b):
            direct_only += 1
        else:
            both_no += 1
    discordant = l2tol3_only + direct_only
    if discordant == 0:
        p_value = 1.0
    else:
        p_value = float(binomtest(l2tol3_only, discordant, 0.5, alternative="two-sided").pvalue)
    return {
        "model": model_label,
        "scope": scope_label,
        "n_pairs": len(keys),
        "both_yes": both_yes,
        "l2tol3_only": l2tol3_only,
        "direct_only": direct_only,
        "both_no": both_no,
        "p_value": p_value,
    }


def fmt_num(value: float | None, digits: int = 4) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def fmt_p(value: float) -> str:
    return f"{value:.2e}"


def main():
    specs = [
        (
            "GPT-5.4",
            "finalresults/L3/direct/direct_eval_gpt54/summary.json",
            "finalresults/L2toL3/l2toL3_eval_gpt54/summary.json",
        ),
        (
            "Claude Sonnet 4.6",
            "finalresults/L3/direct/direct_eval_sonnet/summary.json",
            "finalresults/L2toL3/l2toL3_eval_sonnet/summary.json",
        ),
    ]
    language_order = ["cpp", "go", "java", "javascript", "python"]
    language_labels = {
        "cpp": "C++",
        "go": "Go",
        "java": "Java",
        "javascript": "JavaScript",
        "python": "Python",
    }

    score_results = []
    full_pass_results = []
    for model_label, direct_path, l2tol3_path in specs:
        direct = load_summary(direct_path)
        l2tol3 = load_summary(l2tol3_path)
        keys, x, y = paired_task_scores(direct, l2tol3)
        score_results.append(summarize(model_label, "Overall", keys, x, y))
        full_pass_results.append(summarize_full_pass_exact(model_label, "Overall", keys, x, y))
        for language in language_order:
            keys_l, x_l, y_l = paired_task_scores(direct, l2tol3, language=language)
            score_results.append(summarize(model_label, language_labels[language], keys_l, x_l, y_l))
            full_pass_results.append(summarize_full_pass_exact(model_label, language_labels[language], keys_l, x_l, y_l))

    json_path = REPORTS_DIR / "l2tol3_vs_l3_direct_significance.json"
    md_path = REPORTS_DIR / "l2tol3_vs_l3_direct_significance.md"
    csv_path = REPORTS_DIR / "l2tol3_vs_l3_direct_significance.csv"

    json_path.write_text(
        json.dumps({"score_wilcoxon": score_results, "full_pass_exact": full_pass_results}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    lines = []
    lines.append("# L2-to-L3 vs L3 Direct Significance Tests\n\n")
    lines.append("Two paired significance views are reported below.\n\n")
    lines.append("1. Two-sided Wilcoxon signed-rank tests on paired task-level execution scores (`score`).\n")
    lines.append("2. Two-sided exact paired binary tests on full-pass outcomes, using the discordant-pair binomial form of McNemar's test.\n\n")
    lines.append("## Task-score Wilcoxon tests\n\n")
    lines.append("| Model | Scope | Pairs | Nonzero | Mean Direct | Mean L2toL3 | Mean Δ | Median Δ | +Δ | -Δ | W | p |\n")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    for r in score_results:
        lines.append(
            f"| {r['model']} | {r['scope']} | {r['n_pairs']} | {r['n_nonzero']} | "
            f"{fmt_num(r['mean_direct'])} | {fmt_num(r['mean_l2tol3'])} | {fmt_num(r['mean_delta'])} | "
            f"{fmt_num(r['median_delta'])} | {r['positive_deltas']} | {r['negative_deltas']} | "
            f"{fmt_num(r['wilcoxon_statistic'])} | {fmt_p(r['p_value'])} |\n"
        )
    lines.append("\n")
    lines.append("## Full-pass exact paired tests\n\n")
    lines.append("| Model | Scope | Pairs | Both yes | L2toL3 only | Direct only | Both no | p |\n")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|\n")
    for r in full_pass_results:
        lines.append(
            f"| {r['model']} | {r['scope']} | {r['n_pairs']} | {r['both_yes']} | {r['l2tol3_only']} | "
            f"{r['direct_only']} | {r['both_no']} | {fmt_p(r['p_value'])} |\n"
        )
    md_path.write_text("".join(lines), encoding="utf-8")

    csv_lines = [
        "section,model,scope,n_pairs,n_nonzero,mean_direct,mean_l2tol3,mean_delta,median_delta,positive_deltas,negative_deltas,wilcoxon_statistic,both_yes,l2tol3_only,direct_only,both_no,p_value"
    ]
    for r in score_results:
        csv_lines.append(
            ",".join([
                "score_wilcoxon",
                r["model"],
                r["scope"],
                str(r["n_pairs"]),
                str(r["n_nonzero"]),
                fmt_num(r["mean_direct"]),
                fmt_num(r["mean_l2tol3"]),
                fmt_num(r["mean_delta"]),
                fmt_num(r["median_delta"]),
                str(r["positive_deltas"]),
                str(r["negative_deltas"]),
                fmt_num(r["wilcoxon_statistic"]),
                "",
                "",
                "",
                "",
                fmt_p(r["p_value"]),
            ])
        )
    for r in full_pass_results:
        csv_lines.append(
            ",".join([
                "full_pass_exact",
                r["model"],
                r["scope"],
                str(r["n_pairs"]),
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                str(r["both_yes"]),
                str(r["l2tol3_only"]),
                str(r["direct_only"]),
                str(r["both_no"]),
                fmt_p(r["p_value"]),
            ])
        )
    csv_path.write_text("\n".join(csv_lines) + "\n", encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
