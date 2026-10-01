from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common import FINALRESULTS_ROOT, pct
from figure_common import default_output, ensure_parent


FAMILIES = [
    ("Direct", [("GPT", "direct/direct_eval_gpt54"), ("Son", "direct/direct_eval_sonnet"), ("DSK", "direct/direct_eval_dpsk")], "#9fb2cf"),
    ("RepoCoder", [("GPT", "repocoder/repoder_eval_gpt5.4"), ("Son", "repocoder/repoder_eval_sonnet"), ("DSK", "repocoder/repoder_eval_dpsk")], "#efc88e"),
    ("AlignCoder", [("GPT", "aligncoder/aligncoder_eval_gpt54"), ("Son", "aligncoder/aligncoder_eval_sonnet"), ("DSK", "aligncoder/aligncoder_eval_dpsk")], "#b5abd3"),
    ("HCP", [("GPT", "HCP/hcpcoder_eval_gpt54"), ("Son", "HCP/hcpcoder_eval_sonnet"), ("DSK", "HCP/hcpcoder_eval_dpsk")], "#afc992"),
]


def load_rows(rel_dir: str) -> tuple[list[list[float]], list[str]]:
    root = FINALRESULTS_ROOT / "L3" / rel_dir
    per_box = []
    labels = []
    for path in sorted(root.glob("**/*.json")):
        if path.name == "summary.json":
            summary = json.loads(path.read_text(encoding="utf-8"))
            continue
    for label, _ in []:
        pass
    return per_box, labels


def values_for_dir(rel_dir: str) -> tuple[list[float], float, float]:
    root = FINALRESULTS_ROOT / "L3" / rel_dir
    values = []
    compile_ok = 0
    total = 0
    full_ok = 0
    for path in sorted(root.glob("**/*.json")):
        if path.name == "summary.json":
            continue
        row = json.loads(path.read_text(encoding="utf-8"))
        total += 1
        if row.get("full_passed"):
            full_ok += 1
        if row.get("compile_passed"):
            compile_ok += 1
            ratio = row.get("test_pass_ratio")
            if ratio is not None and not row.get("full_passed"):
                values.append(float(ratio))
    return values, pct(full_ok / total), pct(compile_ok / total)


def plot(output: Path) -> None:
    ensure_parent(output)
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 13.2), sharey=True, constrained_layout=True)
    axes = axes.flatten()
    for ax, (title, items, color) in zip(axes, FAMILIES):
        series = []
        xticklabels = []
        for short, rel_dir in items:
            values, full_pct, compile_pct = values_for_dir(rel_dir)
            series.append(values)
            xticklabels.append(f"{short}\nF {full_pct:.1f}%\nC {compile_pct:.1f}%")
        bp = ax.boxplot(
            series,
            patch_artist=True,
            widths=0.55,
            showfliers=False,
            medianprops={"color": "#222222", "linewidth": 2.4},
            boxprops={"facecolor": color, "alpha": 0.92, "edgecolor": "#737373", "linewidth": 1.8},
            whiskerprops={"color": "#6f6f6f", "linewidth": 1.8},
            capprops={"color": "#6f6f6f", "linewidth": 1.8},
        )
        ax.set_title(title, fontsize=24, pad=4)
        ax.set_xticks(range(1, len(xticklabels) + 1), xticklabels, fontsize=17)
        ax.set_ylim(0.0, 1.02)
        ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0], [f"{int(v*100)}%" for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]], fontsize=17)
        ax.grid(axis="y", ls="--", lw=1.2, alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[0].set_ylabel("Test-pass ratio", fontsize=20)
    axes[2].set_ylabel("Test-pass ratio", fontsize=20)
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=default_output("l3_testpass_boxplot_grid.png"))
    args = parser.parse_args()
    plot(args.output)


if __name__ == "__main__":
    main()
