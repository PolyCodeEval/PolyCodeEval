from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import FINALRESULTS_ROOT
from figure_common import default_output, ensure_parent


LEVELS = [
    ("L2 file-level", "l2_prompt_score", ["python", "java", "go", "cpp", "javascript"], "dpskv4_judge"),
    ("L3 function-level", "l3_prompt_score", ["python", "java", "go", "cpp", "javascript"], "dpskv4pro_judge"),
]
JUDGES = [("Son", "sonnet4.6_judge"), ("Ds", None), ("GPT", "gpt5.4_judge")]
COLS = ["Python", "Java", "Go", "C++", "JS", "Overall"]


def load_level_matrix(root_name: str, ds_folder: str) -> np.ndarray:
    rows = []
    for _, folder in JUDGES:
        actual_folder = ds_folder if folder is None else folder
        path = FINALRESULTS_ROOT / root_name / actual_folder / "summary.json"
        summary = json.loads(path.read_text(encoding="utf-8"))
        by_language = summary["by_language"]
        row = [
            round(float(by_language["python"]["avg_score"]), 2),
            round(float(by_language["java"]["avg_score"]), 2),
            round(float(by_language["go"]["avg_score"]), 2),
            round(float(by_language["cpp"]["avg_score"]), 2),
            round(float(by_language["javascript"]["avg_score"]), 2),
            round(float(summary["avg_score"]), 2),
        ]
        rows.append(row)
    return np.array(rows)


def add_heatmap(ax: plt.Axes, data: np.ndarray, title: str) -> None:
    im = ax.imshow(data, cmap="Blues", vmin=4.4, vmax=4.9, aspect="auto")
    ax.set_title(title, fontsize=28, fontweight="bold", pad=14)
    ax.set_xticks(range(len(COLS)), COLS, fontsize=16)
    ax.set_yticks(range(len(JUDGES)), [x[0] for x in JUDGES], fontsize=18, fontweight="bold")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            color = "white" if data[i, j] >= 4.75 else "black"
            ax.text(j, i, f"{data[i, j]:.2f}", ha="center", va="center", fontsize=18, fontweight="bold", color=color)
    ax.tick_params(length=0)
    for x in np.arange(-0.5, data.shape[1], 1):
        ax.axvline(x, color="gray", lw=0.8, alpha=0.6)
    for y in np.arange(-0.5, data.shape[0], 1):
        ax.axhline(y, color="gray", lw=0.8, alpha=0.6)
    return im


def plot(output: Path) -> None:
    ensure_parent(output)
    mats = [load_level_matrix(root_name, ds_folder) for _, root_name, _, ds_folder in LEVELS]
    fig = plt.figure(figsize=(20, 9), constrained_layout=True)
    gs = fig.add_gridspec(2, 3, height_ratios=[14, 3], width_ratios=[10, 10, 4])
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])]
    cax = fig.add_subplot(gs[1, 0:2])
    key_ax = fig.add_subplot(gs[:, 2])

    im = None
    for ax, mat, (title, _, _, _) in zip(axes, mats, LEVELS):
        im = add_heatmap(ax, mat, title)
    axes[1].set_yticklabels([])
    axes[1].tick_params(left=False)

    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
    cb.set_label("Prompt Quality Score", fontsize=18, labelpad=10)
    cb.ax.tick_params(labelsize=14)

    key_ax.axis("off")
    key_ax.text(
        0.05,
        0.15,
        "Key:\n\nSon = Sonnet 4.6\n\nDs = DeepSeek V4 Pro\n\nGPT = GPT-5.4",
        fontsize=15,
        va="bottom",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "white", "edgecolor": "#2b5dd1"},
    )

    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=default_output("Cross-modelPromptQualityScoresforL2L3.png"))
    args = parser.parse_args()
    plot(args.output)


if __name__ == "__main__":
    main()
