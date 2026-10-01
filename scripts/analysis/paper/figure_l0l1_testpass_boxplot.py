from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import FINALRESULTS_ROOT, build_ok, full_ok, load_json
from figure_common import default_output, ensure_parent


SERIES = {
    "L0": {
        "Codex": FINALRESULTS_ROOT / "L0" / "codex_l0_full_gpt54_eval",
        "Claude Code": FINALRESULTS_ROOT / "L0" / "cc_l0_full_sonnet_eval_new",
    },
    "L1": {
        "Codex": FINALRESULTS_ROOT / "L1" / "codex_l1_full_gpt54_eval",
        "Claude Code": FINALRESULTS_ROOT / "L1" / "cc_l1_full_sonnet_eval",
    },
}

COLORS = ["#a8bddf", "#f1c88b", "#b9d3a0"]


def compute_metrics(root: Path) -> tuple[float, float, float]:
    total = 0
    build_count = 0
    full_count = 0
    ratios = []
    for path in sorted(root.glob("**/*.json")):
        if path.name == "summary.json":
            continue
        row = load_json(path)
        total += 1
        if build_ok(row):
            build_count += 1
            detail = ((row.get("dimension_details") or {}).get("correctness") or {})
            if detail.get("test_pass_ratio") is not None:
                ratios.append(float(detail["test_pass_ratio"]))
        if full_ok(row):
            full_count += 1
    return full_count / total, build_count / total, sum(ratios) / len(ratios)


def plot(output: Path) -> None:
    ensure_parent(output)
    fig, axes = plt.subplots(2, 1, figsize=(10.6, 11.8), constrained_layout=False)
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.06, top=0.82, hspace=0.42)
    fig.suptitle("L0/L1: Build Success vs. Post-build Test Pass", fontsize=22, y=0.985)

    legend_handles = [plt.Rectangle((0, 0), 1, 1, color=c, alpha=0.85, ec="#666666") for c in COLORS]
    fig.legend(
        legend_handles,
        ["Full-pass", "Build-success", "Test-pass\nif build succeeds"],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.94),
        ncol=3,
        fontsize=15,
        frameon=False,
        handlelength=1.8,
        columnspacing=2.4,
    )

    for ax, (level, roots) in zip(axes, SERIES.items()):
        labels = list(roots.keys())
        vals = [compute_metrics(root) for root in roots.values()]
        x = np.arange(len(labels))
        w = 0.22
        for idx, metric_name in enumerate(["full", "build", "test"]):
            heights = [v[idx] for v in vals]
            bars = ax.bar(x + (idx - 1) * w, heights, width=w, color=COLORS[idx], alpha=0.85, edgecolor="#777777")
            for bar, h in zip(bars, heights):
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.012, f"{h*100:.1f}%", ha="center", va="bottom", fontsize=13)
        ax.set_title(level, fontsize=20, pad=12)
        ax.set_xticks(x, labels, fontsize=14)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Ratio", fontsize=14)
        ax.tick_params(axis="y", labelsize=12)
        ax.grid(axis="y", ls="--", lw=1, alpha=0.4)
        ax.set_axisbelow(True)
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=default_output("l0l1_testpass_boxplot.png"))
    args = parser.parse_args()
    plot(args.output)


if __name__ == "__main__":
    main()
