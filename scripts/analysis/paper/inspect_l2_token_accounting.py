from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_m(tokens: float) -> float:
    return round(tokens / 1_000_000, 2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect L2 token accounting from an All_answers summary.json file."
    )
    parser.add_argument(
        "summary_json",
        type=Path,
        help="Path to All_answers/L2/*/summary.json",
    )
    args = parser.parse_args()

    data = load_json(args.summary_json)
    token_usage = data.get("token_usage", {})
    per_task = data.get("per_task", {})

    input_tokens = sum((row.get("input_tokens", 0) or 0) for row in per_task.values())
    output_tokens = sum((row.get("output_tokens", 0) or 0) for row in per_task.values())
    reasoning_output_tokens = sum((row.get("reasoning_output_tokens", 0) or 0) for row in per_task.values())
    cache_read_input_tokens = sum((row.get("cache_read_input_tokens", 0) or 0) for row in per_task.values())
    cache_creation_input_tokens = sum((row.get("cache_creation_input_tokens", 0) or 0) for row in per_task.values())

    payload = {
        "summary_json": str(args.summary_json),
        "task_count": len(per_task),
        "top_level_token_usage": token_usage,
        "recomputed_from_per_task": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_output_tokens": reasoning_output_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "input_plus_output": input_tokens + output_tokens,
            "input_plus_output_plus_cache_read": input_tokens + output_tokens + cache_read_input_tokens,
            "input_plus_output_plus_cache_read_plus_cache_creation": (
                input_tokens + output_tokens + cache_read_input_tokens + cache_creation_input_tokens
            ),
        },
        "recomputed_in_millions": {
            "input_tokens_m": fmt_m(input_tokens),
            "output_tokens_m": fmt_m(output_tokens),
            "reasoning_output_tokens_m": fmt_m(reasoning_output_tokens),
            "cache_read_input_tokens_m": fmt_m(cache_read_input_tokens),
            "cache_creation_input_tokens_m": fmt_m(cache_creation_input_tokens),
            "input_plus_output_m": fmt_m(input_tokens + output_tokens),
            "input_plus_output_plus_cache_read_m": fmt_m(input_tokens + output_tokens + cache_read_input_tokens),
            "input_plus_output_plus_cache_read_plus_cache_creation_m": fmt_m(
                input_tokens + output_tokens + cache_read_input_tokens + cache_creation_input_tokens
            ),
        },
        "notes": {
            "top_level_total_tokens_meaning": "Usually equals input_tokens + output_tokens at the summary top level.",
            "paper_agent_mode_total_if_cache_is_counted": "Use input_tokens + output_tokens + cache_read_input_tokens.",
        },
    }

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
