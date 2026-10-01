from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from figure_common import default_output, ensure_parent
from report_prompt_and_construction_stats import aggregate_baseline_improved


ORDER = ["python", "java", "go", "cpp", "javascript"]
LABEL = {
    "python": "Python",
    "java": "Java",
    "go": "Go",
    "cpp": "C++",
    "javascript": "JS/TS",
}


def plot(output: Path) -> None:
    ensure_parent(output)
    stats = aggregate_baseline_improved()
    baseline = stats["baseline"]
    improved = stats["improved"]
    gain = stats["gain_pp"]

    y = list(range(len(ORDER)))
    fig, ax = plt.subplots(figsize=(12.5, 7.8), constrained_layout=True)

    for i, lang in enumerate(ORDER):
        ax.plot([baseline[lang], improved[lang]], [i, i], color="#6f6f6f", lw=1.8, zorder=1)
        ax.scatter(baseline[lang], i, s=260, color="#d9e6f7", edgecolor="#425466", zorder=3, label="Baseline" if i == 0 else None)
        ax.scatter(improved[lang], i, s=260, color="#056c79", edgecolor="#08343a", zorder=3, label="Improved" if i == 0 else None)
        ax.text(baseline[lang], i - 0.12, f"{baseline[lang]:.1f}%", ha="center", va="bottom", fontsize=14)
        ax.text(improved[lang], i - 0.12, f"{improved[lang]:.1f}%", ha="center", va="bottom", fontsize=14)
        ax.text(103, i, f"+{gain[lang]:.1f}pp", ha="left", va="center", fontsize=14)

    ax.set_yticks(y, [LABEL[x] for x in ORDER], fontsize=18, fontweight="bold")
    ax.set_xlim(0, 108)
    ax.set_xticks([0, 20, 40, 60, 80, 100], [f"{x}%" for x in [0, 20, 40, 60, 80, 100]], fontsize=16)
    ax.set_xlabel("Test Coverage (%)", fontsize=18)
    ax.grid(axis="x", ls="--", lw=1, alpha=0.45)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=15, frameon=True, fancybox=False, edgecolor="black")
    ax.invert_yaxis()

    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=default_output("Test-SuiteCoverageImprovement.png"))
    args = parser.parse_args()
    plot(args.output)


if __name__ == "__main__":
    main()
