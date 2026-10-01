from __future__ import annotations

import json
from pathlib import Path

from common import FINALRESULTS_ROOT, LANG_LABEL, LANG_ORDER, aggregate_project_level_dir


def relabel(block: dict) -> dict:
    return {LANG_LABEL[k]: v for k, v in block["by_language"].items() if k in LANG_LABEL}


def main() -> None:
    sources = {
        "oracle_l0": FINALRESULTS_ROOT / "oracle_l0_eval_final",
        "l0_claude_code_sonnet": FINALRESULTS_ROOT / "L0" / "cc_l0_full_sonnet_eval_new",
        "l0_codex_gpt54": FINALRESULTS_ROOT / "L0" / "codex_l0_full_gpt54_eval",
        "l0_chatdev_sonnet": FINALRESULTS_ROOT / "L0" / "chatdev_l0_full_sonnet46_eval",
        "l0_chatdev_gpt54": FINALRESULTS_ROOT / "L0" / "chatdev_l0_full_gpt54_eval",
        "l1_claude_code_sonnet": FINALRESULTS_ROOT / "L1" / "cc_l1_full_sonnet_eval",
        "l1_codex_gpt54": FINALRESULTS_ROOT / "L1" / "codex_l1_full_gpt54_eval",
    }

    aggregated = {name: aggregate_project_level_dir(path) for name, path in sources.items()}

    payload = {
        "oracle_scores_table": {
            "by_language": relabel(aggregated["oracle_l0"]),
            "overall": aggregated["oracle_l0"]["overall"],
            "source": str(sources["oracle_l0"]),
            "formula": {
                "Corr_percent": "mean(correctness)",
                "Faith": "mean(faithfulness_score)",
                "Arch": "mean(architecture_score)",
                "Health": "mean(health_score)",
            },
        },
        "l0_chatdev_table": {
            "claude_code_sonnet": relabel(aggregated["l0_claude_code_sonnet"]),
            "codex_gpt54": relabel(aggregated["l0_codex_gpt54"]),
            "chatdev_sonnet": relabel(aggregated["l0_chatdev_sonnet"]),
            "chatdev_gpt54": relabel(aggregated["l0_chatdev_gpt54"]),
            "overall": {
                "claude_code_sonnet": aggregated["l0_claude_code_sonnet"]["overall"],
                "codex_gpt54": aggregated["l0_codex_gpt54"]["overall"],
                "chatdev_sonnet": aggregated["l0_chatdev_sonnet"]["overall"],
                "chatdev_gpt54": aggregated["l0_chatdev_gpt54"]["overall"],
            },
        },
        "l0_l1_table": {
            "L0": {
                "oracle": relabel(aggregated["oracle_l0"]),
                "claude_code_sonnet": relabel(aggregated["l0_claude_code_sonnet"]),
                "codex_gpt54": relabel(aggregated["l0_codex_gpt54"]),
                "overall": {
                    "oracle": aggregated["oracle_l0"]["overall"],
                    "claude_code_sonnet": aggregated["l0_claude_code_sonnet"]["overall"],
                    "codex_gpt54": aggregated["l0_codex_gpt54"]["overall"],
                },
            },
            "L1": {
                "oracle": relabel(aggregated["oracle_l0"]),
                "claude_code_sonnet": relabel(aggregated["l1_claude_code_sonnet"]),
                "codex_gpt54": relabel(aggregated["l1_codex_gpt54"]),
                "overall": {
                    "oracle": aggregated["oracle_l0"]["overall"],
                    "claude_code_sonnet": aggregated["l1_claude_code_sonnet"]["overall"],
                    "codex_gpt54": aggregated["l1_codex_gpt54"]["overall"],
                },
            },
        },
        "notes": {
            "project_level_formula": {
                "C": "per-language mean of task-level correctness (%)",
                "F": "per-language mean of task-level faithfulness_score",
                "A": "per-language mean of task-level architecture_score",
                "H": "per-language mean of task-level health_score",
                "Build": "share of tasks with build_status == 'ok'",
                "Full": "share of tasks with all_tests_passed == true",
                "Avg_row": "same aggregation on all tasks in the block, not simple mean of language rows",
            },
            "language_order": [LANG_LABEL[key] for key in LANG_ORDER],
        },
    }

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
