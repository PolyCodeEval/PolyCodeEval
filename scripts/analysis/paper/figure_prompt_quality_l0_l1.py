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


JUDGES = [
    ("Son", "sonnet4.6_judge"),
    ("Ds", "dpskv4pro_judge"),
    ("GPT", "gpt5.4_judge"),
]
COLS = ["Completeness", "Clarity", "Consistency", "Testability", "Average"]
KEY_MAP = {
    "Completeness": "avg_completeness",
    "Clarity": "avg_unambiguity",
    "Consistency": "avg_consistency",
    "Testability": "avg_testability",
    "Average": "avg_overall",
}


def weighted_row(summary: dict) -> list[float]:
    by_language = summary["by_language"]
    def weight(bucket: dict) -> int:
        return int(bucket.get("project_count", bucket.get("total", 0)))

    def value_key(col: str) -> str:
        if col == "Average":
            return "avg_overall" if "avg_overall" in next(iter(by_language.values())) else "avg_overall_score"
        return KEY_MAP[col]

    total = sum(weight(bucket) for bucket in by_language.values())
    row = []
    for col in COLS:
        key = value_key(col)
        value = sum(weight(bucket) * float(bucket[key]) for bucket in by_language.values()) / total
        row.append(round(value, 2))
    return row


def load_matrix() -> np.ndarray:
    rows = []
    for _, folder in JUDGES:
        path = FINALRESULTS_ROOT / "l0_prompt_score" / folder / "summary.json"
        summary = json.loads(path.read_text(encoding="utf-8"))
        rows.append(weighted_row(summary))
    return np.array(rows)


def plot(output: Path) -> None:
    data = load_matrix()
    ensure_parent(output)

    fig = plt.figure(figsize=(12.5, 7.8), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, height_ratios=[14, 3], width_ratios=[14, 4])
    ax = fig.add_subplot(gs[0, :])
    cax = fig.add_subplot(gs[1, 0])
    key_ax = fig.add_subplot(gs[1, 1])

    im = ax.imshow(data, cmap="Blues", vmin=3.8, vmax=4.65, aspect="auto")
    ax.set_xticks(range(len(COLS)), COLS, fontsize=15)
    ax.set_yticks(range(len(JUDGES)), [x[0] for x in JUDGES], fontsize=18, fontweight="bold")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            color = "white" if data[i, j] >= 4.2 else "black"
            ax.text(j, i, f"{data[i, j]:.2f}", ha="center", va="center", fontsize=18, fontweight="bold", color=color)
    for x in np.arange(-0.5, data.shape[1], 1):
        ax.axvline(x, color="white", lw=1, alpha=0.7)
    for y in np.arange(-0.5, data.shape[0], 1):
        ax.axhline(y, color="white", lw=1, alpha=0.7)
    ax.tick_params(length=0)

    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
    cb.set_label("Prompt Quality Score", fontsize=18, labelpad=10)
    cb.ax.tick_params(labelsize=14)

    key_ax.axis("off")
    key_text = "Key:\n\nSon = Sonnet 4.6\n\nDs = DeepSeek V4 Pro\n\nGPT = GPT-5.4"
    key_ax.text(
        0.0,
        0.9,
        key_text,
        va="top",
        fontsize=15,
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "white", "edgecolor": "#2b5dd1"},
    )

    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=default_output("Cross-modelPromptQualityScoresforL0L1.png"))
    args = parser.parse_args()
    plot(args.output)


if __name__ == "__main__":
    main()
