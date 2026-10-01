from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import FINALRESULTS_ROOT
from figure_common import default_output, ensure_parent


LEVEL_FILES = {
    "L0/L1 functional": FINALRESULTS_ROOT / "coverage_report" / "L0" / "summary.json",
    "L2 file": FINALRESULTS_ROOT / "coverage_report" / "L2" / "summary.json",
    "L3 function": FINALRESULTS_ROOT / "coverage_report" / "L3" / "summary.json",
}

LEVEL_COLORS = {
    "L0/L1 functional": "#8FB3E8",
    "L2 file": "#F2BF74",
    "L3 function": "#8FCF9A",
}

LANG_ORDER = ["python", "java", "go", "cpp", "javascript"]
LANG_LABELS = {
    "python": "Python",
    "java": "Java",
    "go": "Go",
    "cpp": "C++",
    "javascript": "JavaScript",
}


def js_group(language: str) -> str:
    return "javascript" if language in {"javascript", "typescript"} else language


def load_level_values(path: Path, value_key: str) -> dict[str, list[float]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in data["projects"]:
        grouped[js_group(row["language"])].append(float(row[value_key]))
    return grouped


def build_payload() -> dict[str, dict[str, list[float]]]:
    return {
        "L0/L1 functional": load_level_values(LEVEL_FILES["L0/L1 functional"], "project_line_coverage_pct"),
        "L2 file": load_level_values(LEVEL_FILES["L2 file"], "avg_coverage_pct"),
        "L3 function": load_level_values(LEVEL_FILES["L3 function"], "avg_coverage_pct"),
    }


def overall_mean(values: dict[str, list[float]]) -> float:
    flat = [x for bucket in values.values() for x in bucket]
    return sum(flat) / len(flat)


def weighted_overall_from_summary(path: Path, *, value_key: str, weight_key: str | None = None) -> float:
    data = json.loads(path.read_text(encoding="utf-8"))
    if weight_key is None:
        vals = [float(row[value_key]) for row in data["projects"]]
        return sum(vals) / len(vals)
    numer = sum(float(row[value_key]) * float(row[weight_key]) for row in data["projects"])
    denom = sum(float(row[weight_key]) for row in data["projects"])
    return numer / denom


def plot(output: Path) -> None:
    ensure_parent(output)
    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib-cache")
    payload = build_payload()

    fig, ax = plt.subplots(figsize=(12.4, 7.8), constrained_layout=True)

    centers = np.arange(len(LANG_ORDER))
    offsets = [-0.24, 0.0, 0.24]
    widths = 0.2

    for offset, (level_name, by_lang) in zip(offsets, payload.items()):
        series = [by_lang.get(lang, []) for lang in LANG_ORDER]
        positions = centers + offset
        bp = ax.boxplot(
            series,
            positions=positions,
            widths=widths,
            patch_artist=True,
            showfliers=False,
            medianprops={"color": "#1f1f1f", "linewidth": 2.0},
            whiskerprops={"color": "#666666", "linewidth": 1.4},
            capprops={"color": "#666666", "linewidth": 1.4},
            boxprops={
                "facecolor": LEVEL_COLORS[level_name],
                "edgecolor": "#666666",
                "linewidth": 1.4,
                "alpha": 0.9,
            },
        )
        means = [sum(vals) / len(vals) if vals else None for vals in series]
        for x, mean in zip(positions, means):
            if mean is None:
                continue
            ax.scatter(x, mean, marker="D", s=32, color="#222222", zorder=4)

    ax.set_xticks(centers, [LANG_LABELS[x] for x in LANG_ORDER], fontsize=17)
    ax.set_ylabel("Coverage (%)", fontsize=20)
    ax.set_ylim(84, 100.5)
    ax.set_yticks(np.arange(84, 101, 4))
    ax.tick_params(axis="y", labelsize=17)
    ax.grid(axis="y", linestyle="--", linewidth=0.9, alpha=0.35)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=LEVEL_COLORS[name], edgecolor="#666666", alpha=0.9)
        for name in payload.keys()
    ]
    mean_handle = plt.Line2D([0], [0], marker="D", color="w", markerfacecolor="#222222", markersize=7, linestyle="None")
    ax.legend(
        legend_handles + [mean_handle],
        list(payload.keys()) + ["Per-language mean"],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.23),
        ncol=4,
        frameon=False,
        fontsize=17,
    )

    fig.savefig(output, dpi=240, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output("CoverageStatisticsByEvaluationLevelBoxplot.png"),
    )
    args = parser.parse_args()
    plot(args.output)


if __name__ == "__main__":
    main()
