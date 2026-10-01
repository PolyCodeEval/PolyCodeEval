"""Export token and construction-cost accounting."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .common import ANSWERS, FINAL, RUNS, load_json, source_link


PAPER_ACCOUNTING = {
    "l2-direct-gpt": (1.89, 13.35),
    "l2-direct-sonnet": (3.14, 16.72),
    "l2-codex-gpt": (23.60, 28.55),
    "l2-claude-code-sonnet": (63.28, 61.12),
    "l3-direct-gpt": (17.57, 46.00),
    "l3-direct-sonnet": (25.11, 82.19),
    "l3-direct-deepseek": (17.33, 28.05),
    "l3-repocoder-gpt": (182.53, 370.22),
    "l3-repocoder-sonnet": (237.54, 728.37),
    "l3-repocoder-deepseek": (206.03, 614.12),
    "l3-aligncoder-gpt": (62.13, 118.43),
    "l3-aligncoder-sonnet": (98.23, 363.87),
    "l3-aligncoder-deepseek": (71.94, 65.35),
    "l3-hcp-gpt": (97.09, 165.40),
    "l3-hcp-sonnet": (125.04, 399.35),
    "l3-hcp-deepseek": (99.79, 124.46),
}


def token_usage(path) -> dict[str, Any]:
    return dict(load_json(path).get("token_usage") or {})


def parse_repocoder_usage() -> dict[str, dict[str, float]]:
    candidates = sorted((ANSWERS / "L3/repocoder").glob("consumption_export_20260601_230000_to_20260603_080004_task5115_*.md"))
    if len(candidates) != 1:
        raise ValueError(f"Expected one RepoCoder consumption report, found {len(candidates)}")
    path = candidates[0]
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 6 or cells[0] in {"\u6a21\u578b", "\u5408\u8ba1"}:
            continue
        rows[cells[0]] = {
            "records": int(cells[1].replace(",", "")),
            "inputTokens": int(cells[2].replace(",", "")),
            "outputTokens": int(cells[3].replace(",", "")),
            "totalTokens": int(cells[4].replace(",", "")),
            "costUsd": float(cells[5].replace(",", "")),
        }
    return rows


def normalize_usage(raw: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "input_tokens": "inputTokens", "output_tokens": "outputTokens", "total_tokens": "totalTokens",
        "cache_read_input_tokens": "cacheReadTokens", "cache_read_tokens": "cacheReadTokens",
        "cache_creation_input_tokens": "cacheCreationTokens", "cache_creation_tokens": "cacheCreationTokens",
        "draft_input_tokens": "draftInputTokens", "draft_output_tokens": "draftOutputTokens",
        "embedding_tokens": "embeddingTokens", "retriever_approx_tokens": "retrieverApproxTokens",
        "cost_usd": "costUsd",
    }
    return {aliases[key]: value for key, value in raw.items() if key in aliases and isinstance(value, (int, float))}


def build_tokens() -> dict[str, Any]:
    records = []
    run_metadata = {run.id: {"method": run.method, "model": run.model} for run in RUNS}

    def record(config: str, level: str, usage: dict[str, Any], accounting: str, **sources: Any) -> dict[str, Any]:
        return {
            "level": level,
            "configuration": config,
            **run_metadata[config],
            "usage": usage,
            "accounting": accounting,
            **sources,
        }

    l2_paths = {
        "l2-direct-gpt": ANSWERS / "L2/l2_direct_full_gpt54/summary.json",
        "l2-direct-sonnet": ANSWERS / "L2/l2_direct_full_sonnet/summary.json",
        "l2-codex-gpt": ANSWERS / "L2/codex_l2_full_gpt54/summary.json",
        "l2-claude-code-sonnet": ANSWERS / "L2/cc_l2_full_sonnet46/summary.json",
    }
    for config, path in l2_paths.items():
        records.append(record(config, "L2", normalize_usage(token_usage(path)), "Recorded runtime summary", sourceLink=source_link(path)))

    direct = {
        "l3-direct-gpt": ANSWERS / "L3/direct/direct_api_all_gpt54/summary.json",
        "l3-direct-sonnet": ANSWERS / "L3/direct/direct_api_all_sonnet/summary.json",
        "l3-direct-deepseek": ANSWERS / "L3/direct/direct_api_all_dpsk/summary.json",
    }
    hcp = {
        "l3-hcp-gpt": ANSWERS / "L3/HCP/hcpcoder_gpt54_all_new/summary.json",
        "l3-hcp-sonnet": ANSWERS / "L3/HCP/hcpcoder_sonnet_all/summary.json",
        "l3-hcp-deepseek": ANSWERS / "L3/HCP/hcpcoder_dpsk_all/summary.json",
    }
    for config, path in direct.items():
        records.append(record(config, "L3", normalize_usage(token_usage(path)), "Recorded generation summary", sourceLink=source_link(path)))
    for config, path in hcp.items():
        raw = normalize_usage(token_usage(path))
        raw["displayedInputTokens"] = raw.get("inputTokens", 0)
        raw["displayedOutputTokens"] = raw.get("outputTokens", 0)
        raw["displayedTotalTokens"] = raw["displayedInputTokens"] + raw["displayedOutputTokens"]
        records.append(record(config, "L3", raw, "Displayed total excludes embedding tokens", sourceLink=source_link(path)))

    align = {
        "l3-aligncoder-gpt": (ANSWERS / "L3/aligncoder/aligncoder_gpt54_all_new/summary.json", False, True),
        "l3-aligncoder-sonnet": (ANSWERS / "L3/aligncoder/aligncoder_sonnet_all/summary.json", False, True),
        "l3-aligncoder-deepseek": (ANSWERS / "L3/aligncoder/aligncoder_dpsk_all/summary.json", True, False),
    }
    for config, (path, merge_backup, include_draft) in align.items():
        sources = [path]
        if merge_backup:
            sources.append(path.with_name("summary_bak.json"))
        merged: dict[str, float] = defaultdict(float)
        for source in sources:
            for key, value in normalize_usage(token_usage(source)).items():
                merged[key] += float(value)
        displayed_input = merged.get("inputTokens", 0) + (merged.get("draftInputTokens", 0) if include_draft else 0)
        displayed_output = merged.get("outputTokens", 0) + (merged.get("draftOutputTokens", 0) if include_draft else 0)
        merged["displayedInputTokens"] = displayed_input
        merged["displayedOutputTokens"] = displayed_output
        merged["displayedTotalTokens"] = displayed_input + displayed_output
        records.append(record(
            config, "L3", dict(merged),
            "Primary and draft generation" if include_draft else "Merged primary generation summaries",
            sourceLinks=[source_link(source) for source in sources],
        ))

    billing = parse_repocoder_usage()
    model_keys = {"gpt-5.4": "gpt", "claude-sonnet-4-6": "sonnet", "deepseek-v4-pro": "deepseek"}
    for model, usage in billing.items():
        config = f"l3-repocoder-{model_keys[model]}"
        records.append(record(config, "L3", usage, "Provider billing export", sourceLink="All_answers/L3/repocoder/"))

    for item in records:
        total_m, cost_usd = PAPER_ACCOUNTING[item["configuration"]]
        item["usage"]["displayedTotalTokens"] = int(round(total_m * 1_000_000))
        item["usage"]["displayedCostUsd"] = cost_usd

    construction = []
    for stage, path in (
        ("Prompt construction", FINAL / "datasets_token_usage/claude_uasge.json"),
        ("Test completion", FINAL / "datasets_token_usage/blackboxadd_uage.json"),
    ):
        row = load_json(path)
        construction.append({"stage": stage, "totalTokens": row.get("totalTokens"), "totalCostUsd": row.get("totalCost"), "sourceLink": source_link(path)})
    return {"records": records, "construction": construction}
