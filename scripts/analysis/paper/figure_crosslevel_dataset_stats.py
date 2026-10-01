from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from figure_common import default_output, ensure_parent


LANGS = ["Python", "Java", "Go", "C++", "JS/TS"]
DIFFS = ["Small", "Medium", "Large", "Very Large"]
COLORS = {
    "Small": "#8fb6e8",
    "Medium": "#71c7a3",
    "Large": "#ffb064",
    "Very Large": "#ff6a6a",
}

PAPER_COUNTS = {
    "L0/L1\nrepository-level": {
        "Python": [8, 2, 3, 0],
        "Java": [3, 4, 3, 1],
        "Go": [3, 5, 3, 1],
        "C++": [2, 4, 4, 1],
        "JS/TS": [4, 3, 1, 3],
    },
    "L2\nfile-level": {
        "Python": [11, 2, 0, 0],
        "Java": [29, 0, 0, 0],
        "Go": [26, 8, 1, 0],
        "C++": [23, 14, 9, 1],
        "JS/TS": [14, 7, 4, 1],
    },
    "L3\nfunction-level": {
        "Python": [99, 99, 41, 13],
        "Java": [128, 87, 18, 1],
        "Go": [177, 187, 53, 47],
        "C++": [274, 334, 120, 108],
        "JS/TS": [216, 211, 56, 55],
    },
}

RANGE_ROWS = [
    ("Small", "0 to 499 LOC", "under 500 LOC", "under 15 LOC"),
    ("Medium", "500 to 2.0K LOC", "500 to 2,000 LOC", "15 to 29 LOC"),
    ("Large", "2.0K to 6.0K LOC", "2,000 to 6,000 LOC", "30 to 49 LOC"),
    ("Very Large", "above 6.0K LOC", "above 6,000 LOC", "50 LOC or more"),
]


def bubble_size(n: int) -> float:
    return 120 + 38 * n


def draw_panel(ax: plt.Axes, title: str, counts: dict[str, list[int]]) -> None:
    ax.set_xlim(-0.5, len(DIFFS) - 0.5)
    ax.set_ylim(len(LANGS) - 0.5, -0.5)
    ax.set_xticks(range(len(DIFFS)), DIFFS, fontsize=16)
    ax.set_yticks(range(len(LANGS)), LANGS, fontsize=18, fontweight="bold")
    ax.set_title(title, fontsize=26, fontweight="bold", pad=18)
    ax.grid(color="#bdbdbd", lw=1, alpha=0.7)
    ax.set_axisbelow(True)
    for i, lang in enumerate(LANGS):
        row = counts[lang]
        for j, diff in enumerate(DIFFS):
            n = row[j]
            if n <= 0:
                continue
            ax.scatter(j, i, s=bubble_size(n), color=COLORS[diff], edgecolor="#1b1b1b", alpha=0.72)
            ax.text(j, i, str(n), ha="center", va="center", fontsize=15, fontweight="bold")
    ax.tick_params(length=0)


def draw_range_table(ax: plt.Axes) -> None:
    ax.axis("off")
    cell_text = [[r[0], r[1], r[2], r[3]] for r in RANGE_ROWS]
    table = ax.table(
        cellText=cell_text,
        colLabels=["", "L0/L1\nrepository-level", "L2\nfile-level", "L3\nfunction-level"],
        cellLoc="center",
        colLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.15, 1.9)
    for (row, col), cell in table.get_celld().items():
        cell.set_linewidth(1.0)
        if row == 0:
            cell.set_fontsize(13)
            cell.set_text_props(weight="bold")
            cell.set_height(cell.get_height() * 1.25)
        if col == 0 and row > 0:
            cell.set_text_props(weight="bold")


def draw_legends(ax: plt.Axes) -> None:
    ax.axis("off")
    y0 = 0.82
    ax.text(0.03, y0 + 0.11, "Difficulty", fontsize=18, fontweight="bold", transform=ax.transAxes)
    for idx, diff in enumerate(DIFFS):
        y = y0 - idx * 0.17
        ax.scatter(0.06, y, s=800, color=COLORS[diff], edgecolor="#1b1b1b", alpha=0.72, transform=ax.transAxes)
        ax.text(0.14, y, diff, va="center", fontsize=15, transform=ax.transAxes)

    ax.text(0.56, y0 + 0.11, "Bubble size encodes N", fontsize=18, fontweight="bold", transform=ax.transAxes)
    sample_sizes = [1, 5, 10, 20, 50, 100, 200, 300]
    xs = np.linspace(0.58, 0.98, len(sample_sizes))
    for x, n in zip(xs, sample_sizes):
        ax.scatter(x, 0.47, s=bubble_size(n), color="white", edgecolor="#1b1b1b", alpha=0.95, transform=ax.transAxes)
        ax.text(x, 0.24, str(n), ha="center", fontsize=13, transform=ax.transAxes)
    ax.text(0.72, 0.05, "Same size scale across all panels.", ha="center", fontsize=15, transform=ax.transAxes)


def plot(output: Path) -> None:
    ensure_parent(output)
    fig = plt.figure(figsize=(18, 10), constrained_layout=True)
    gs = fig.add_gridspec(2, 3, height_ratios=[10, 6])

    top_axes = [fig.add_subplot(gs[0, i]) for i in range(3)]
    for ax, (title, counts) in zip(top_axes, PAPER_COUNTS.items()):
        draw_panel(ax, title, counts)
    top_axes[1].set_yticklabels([])
    top_axes[1].tick_params(left=False)
    top_axes[2].set_yticklabels([])
    top_axes[2].tick_params(left=False)

    lower_left = fig.add_subplot(gs[1, 0])
    lower_mid = fig.add_subplot(gs[1, 1])
    lower_right = fig.add_subplot(gs[1, 2])
    draw_legends(lower_left)
    draw_range_table(lower_mid)
    draw_legends(lower_right)
    lower_left.remove()
    lower_left = fig.add_subplot(gs[1, 0])
    lower_left.axis("off")
    lower_mid.axis("off")
    lower_right.axis("off")
    draw_legends(lower_left)
    draw_range_table(lower_mid)
    draw_legends(lower_right)

    fig.text(0.5, 0.01, "Bubble area encodes N; colors encode difficulty; same size scale across all panels.", ha="center", fontsize=18, style="italic")
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=default_output("crossleveldatasetstatics.png"))
    args = parser.parse_args()
    plot(args.output)


if __name__ == "__main__":
    main()
