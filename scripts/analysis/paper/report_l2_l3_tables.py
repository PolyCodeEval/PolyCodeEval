from __future__ import annotations

import json
from pathlib import Path

from common import ALL_ANSWERS_ROOT, FINALRESULTS_ROOT, conditional_test_pass_pct, load_json, parse_repocoder_consumption_markdown, round1


def l2_table() -> dict:
    eval_paths = {
        "direct_gpt54": FINALRESULTS_ROOT / "L2" / "direct_gpt_l2_eval" / "summary.json",
        "direct_sonnet": FINALRESULTS_ROOT / "L2" / "direct_sonnet_l2_eval" / "summary.json",
        "codex_gpt54": FINALRESULTS_ROOT / "L2" / "codex_l2_eval" / "summary.json",
        "claude_code_sonnet": FINALRESULTS_ROOT / "L2" / "cc_l2_eval" / "summary.json",
    }
    usage_paths = {
        "direct_gpt54": ALL_ANSWERS_ROOT / "L2" / "l2_direct_full_gpt54" / "summary.json",
        "direct_sonnet": ALL_ANSWERS_ROOT / "L2" / "l2_direct_full_sonnet" / "summary.json",
        "codex_gpt54": ALL_ANSWERS_ROOT / "L2" / "codex_l2_full_gpt54" / "summary.json",
        "claude_code_sonnet": ALL_ANSWERS_ROOT / "L2" / "cc_l2_full_sonnet46" / "summary.json",
    }

    evals = {name: load_json(path) for name, path in eval_paths.items()}
    usages = {name: load_json(path) for name, path in usage_paths.items()}

    out = {}
    for name, summary in evals.items():
        raw_cost = float(usages[name]["token_usage"].get("cost_usd", 0) or 0)
        out[name] = {
            "by_language": {
                lang: {
                    "full_pass_pct": round1(100 * bucket["full_pass_rate"]),
                    "build_pct": round1(100 * bucket["compile_pass_rate"]),
                    "test_pass_pct": conditional_test_pass_pct(summary, by_language=lang),
                    "N": bucket["total"],
                }
                for lang, bucket in summary["by_language"].items()
            },
            "overall": {
                "full_pass_pct": round1(100 * summary["full_pass_rate"]),
                "build_pct": round1(100 * summary["compile_pass_rate"]),
                "test_pass_pct": conditional_test_pass_pct(summary),
                "total_tokens_m": round(usages[name]["token_usage"]["total_tokens"] / 1_000_000, 2),
                "cost_usd": round(raw_cost, 2) if raw_cost > 0 else None,
            },
        }
    return out


def _l3_usage_direct_or_hcp(path: Path, *, drop_embedding: bool) -> dict[str, float]:
    usage = load_json(path)["token_usage"]
    input_tokens = float(usage.get("input_tokens", 0))
    output_tokens = float(usage.get("output_tokens", 0))
    total_tokens = input_tokens + output_tokens if drop_embedding else float(usage.get("total_tokens", input_tokens + output_tokens))
    return {
        "input_tokens_m": round(input_tokens / 1_000_000, 2),
        "output_tokens_m": round(output_tokens / 1_000_000, 2),
        "table_total_tokens_m": round(total_tokens / 1_000_000, 2),
        "raw_token_usage": usage,
    }


def _l3_usage_align(path: Path, *, merge_backup: bool, include_draft: bool) -> dict[str, float]:
    summaries = [load_json(path)]
    backup = path.with_name("summary_bak.json")
    if merge_backup and backup.exists():
        summaries.append(load_json(backup))

    def _sum(key: str) -> float:
        return sum(float(item["token_usage"].get(key, 0)) for item in summaries)

    primary_in = _sum("input_tokens")
    primary_out = _sum("output_tokens")
    draft_in = _sum("draft_input_tokens")
    draft_out = _sum("draft_output_tokens")
    if include_draft:
        shown_in = primary_in + draft_in
        shown_out = primary_out + draft_out
    else:
        shown_in = primary_in
        shown_out = primary_out
    return {
        "input_tokens_m": round(shown_in / 1_000_000, 2),
        "output_tokens_m": round(shown_out / 1_000_000, 2),
        "table_total_tokens_m": round((shown_in + shown_out) / 1_000_000, 2),
        "raw_token_usage": [item["token_usage"] for item in summaries],
        "include_draft": include_draft,
        "merged_summary_bak": merge_backup,
    }


def _l3_usage_repocoder(markdown_path: Path, model_name: str) -> dict[str, float]:
    rows = parse_repocoder_consumption_markdown(markdown_path)
    row = rows[model_name]
    return {
        "input_tokens_m": round(row["input_tokens"] / 1_000_000, 2),
        "output_tokens_m": round(row["output_tokens"] / 1_000_000, 2),
        "table_total_tokens_m": round(row["total_tokens"] / 1_000_000, 2),
        "cost_usd": round(row["cost_usd"], 2),
        "source": str(markdown_path),
    }


def l3_table() -> dict:
    eval_paths = {
        "direct_gpt54": FINALRESULTS_ROOT / "L3" / "direct" / "direct_eval_gpt54" / "summary.json",
        "direct_sonnet": FINALRESULTS_ROOT / "L3" / "direct" / "direct_eval_sonnet" / "summary.json",
        "direct_dpsk": FINALRESULTS_ROOT / "L3" / "direct" / "direct_eval_dpsk" / "summary.json",
        "repocoder_gpt54": FINALRESULTS_ROOT / "L3" / "repocoder" / "repoder_eval_gpt5.4" / "summary.json",
        "repocoder_sonnet": FINALRESULTS_ROOT / "L3" / "repocoder" / "repoder_eval_sonnet" / "summary.json",
        "repocoder_dpsk": FINALRESULTS_ROOT / "L3" / "repocoder" / "repoder_eval_dpsk" / "summary.json",
        "align_gpt54": FINALRESULTS_ROOT / "L3" / "aligncoder" / "aligncoder_eval_gpt54" / "summary.json",
        "align_sonnet": FINALRESULTS_ROOT / "L3" / "aligncoder" / "aligncoder_eval_sonnet" / "summary.json",
        "align_dpsk": FINALRESULTS_ROOT / "L3" / "aligncoder" / "aligncoder_eval_dpsk" / "summary.json",
        "hcp_gpt54": FINALRESULTS_ROOT / "L3" / "HCP" / "hcpcoder_eval_gpt54" / "summary.json",
        "hcp_sonnet": FINALRESULTS_ROOT / "L3" / "HCP" / "hcpcoder_eval_sonnet" / "summary.json",
        "hcp_dpsk": FINALRESULTS_ROOT / "L3" / "HCP" / "hcpcoder_eval_dpsk" / "summary.json",
    }
    evals = {name: load_json(path) for name, path in eval_paths.items()}

    usage = {
        "direct_gpt54": _l3_usage_direct_or_hcp(ALL_ANSWERS_ROOT / "L3" / "direct" / "direct_api_all_gpt54" / "summary.json", drop_embedding=False),
        "direct_sonnet": _l3_usage_direct_or_hcp(ALL_ANSWERS_ROOT / "L3" / "direct" / "direct_api_all_sonnet" / "summary.json", drop_embedding=False),
        "direct_dpsk": _l3_usage_direct_or_hcp(ALL_ANSWERS_ROOT / "L3" / "direct" / "direct_api_all_dpsk" / "summary.json", drop_embedding=False),
        "repocoder_gpt54": _l3_usage_repocoder(
            ALL_ANSWERS_ROOT / "L3" / "repocoder" / "consumption_export_20260601_230000_to_20260603_080004_task5115_统计明细.md",
            "gpt-5.4",
        ),
        "repocoder_sonnet": _l3_usage_repocoder(
            ALL_ANSWERS_ROOT / "L3" / "repocoder" / "consumption_export_20260601_230000_to_20260603_080004_task5115_统计明细.md",
            "claude-sonnet-4-6",
        ),
        "repocoder_dpsk": _l3_usage_repocoder(
            ALL_ANSWERS_ROOT / "L3" / "repocoder" / "consumption_export_20260601_230000_to_20260603_080004_task5115_统计明细.md",
            "deepseek-v4-pro",
        ),
        "align_gpt54": _l3_usage_align(ALL_ANSWERS_ROOT / "L3" / "aligncoder" / "aligncoder_gpt54_all_new" / "summary.json", merge_backup=False, include_draft=True),
        "align_sonnet": _l3_usage_align(ALL_ANSWERS_ROOT / "L3" / "aligncoder" / "aligncoder_sonnet_all" / "summary.json", merge_backup=False, include_draft=True),
        "align_dpsk": _l3_usage_align(ALL_ANSWERS_ROOT / "L3" / "aligncoder" / "aligncoder_dpsk_all" / "summary.json", merge_backup=True, include_draft=False),
        "hcp_gpt54": _l3_usage_direct_or_hcp(ALL_ANSWERS_ROOT / "L3" / "HCP" / "hcpcoder_gpt54_all_new" / "summary.json", drop_embedding=True),
        "hcp_sonnet": _l3_usage_direct_or_hcp(ALL_ANSWERS_ROOT / "L3" / "HCP" / "hcpcoder_sonnet_all" / "summary.json", drop_embedding=True),
        "hcp_dpsk": _l3_usage_direct_or_hcp(ALL_ANSWERS_ROOT / "L3" / "HCP" / "hcpcoder_dpsk_all" / "summary.json", drop_embedding=True),
    }

    out = {}
    for name, summary in evals.items():
        out[name] = {
            "by_language": {
                lang: {
                    "full_pass_pct": round1(100 * bucket["full_pass_rate"]),
                    "build_pct": round1(100 * bucket["compile_pass_rate"]),
                    "test_pass_pct": conditional_test_pass_pct(summary, by_language=lang),
                    "N": bucket["total"],
                }
                for lang, bucket in summary["by_language"].items()
            },
            "overall": {
                "full_pass_pct": round1(100 * summary["full_pass_rate"]),
                "build_pct": round1(100 * summary["compile_pass_rate"]),
                "test_pass_pct": conditional_test_pass_pct(summary),
            },
            "token_accounting": usage[name],
        }

    notes = {
        "conditional_test_pass_definition": "Average task-level test_pass_ratio over build-successful tasks, reported as a percentage.",
        "aligncoder_token_logic": {
            "gpt54_and_sonnet": "paper row uses primary generation tokens plus draft-generation tokens; retriever_approx_tokens are excluded",
            "dpsk": "paper row is reproduced by merging summary.json and summary_bak.json, but only summing primary input_tokens/output_tokens; draft_* and retriever_approx_tokens are excluded",
        },
        "hcpcoder_token_logic": "paper token row uses input_tokens + output_tokens only; embedding_tokens are excluded from the displayed total",
        "repocoder_token_logic": "paper token and cost rows come from the provider-side consumption export markdown generated from the Excel billing export, not from repocoder summary.json",
        "l3_cost_reproducibility": "The repository does not currently preserve one unified local pricing script for all non-RepoCoder L3 methods. Token groups are reproducible; several cost numbers were postcomputed outside the evaluator and should be treated as secondary derived values.",
    }

    return {"l3": out, "notes": notes}


def main() -> None:
    payload = {
        "l2": l2_table(),
        **l3_table(),
    }
    payload["l2_notes"] = {
        "token_rows": "direct rows are reproducible from All_answers/L2 summaries; Codex and Claude Code rows in the paper appear to rely on broader runtime accounting than the local summary.json totals",
        "cost_rows": "L2 direct GPT-5.4, direct Sonnet, and Codex cost values are not preserved in current local summary.json files; Claude Code Sonnet keeps cost_usd in summary.json",
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
