from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from common import FINALRESULTS_ROOT, LANG_LABEL, LANG_ORDER, floor1, load_json, round1, round4


REPORTS_ROOT = FINALRESULTS_ROOT.parents[0] / "docs" / "reports"


MODEL_PAIRS = {
    "gpt54": {
        "l2tol3": FINALRESULTS_ROOT / "L2toL3" / "l2toL3_eval_gpt54",
        "direct": FINALRESULTS_ROOT / "L3" / "direct" / "direct_eval_gpt54",
        "label": "GPT-5.4",
    },
    "sonnet": {
        "l2tol3": FINALRESULTS_ROOT / "L2toL3" / "l2toL3_eval_sonnet",
        "direct": FINALRESULTS_ROOT / "L3" / "direct" / "direct_eval_sonnet",
        "label": "Claude Sonnet 4.6",
    },
}


def iter_rows(results_dir: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted(results_dir.rglob("*.json")):
        if path.name == "summary.json":
            continue
        rel = path.relative_to(results_dir).as_posix()
        rows[rel] = load_json(path)
    return rows


def full_ok(row: dict[str, Any]) -> bool:
    return bool(row.get("full_passed", row.get("passed", False)))


def build_ok(row: dict[str, Any]) -> bool:
    return bool(row.get("compile_passed", False))


def task_test_pass_ratio(row: dict[str, Any]) -> float:
    if "test_pass_ratio" in row and row["test_pass_ratio"] is not None:
        return float(row["test_pass_ratio"])
    td = row.get("test_details") or {}
    total = td.get("total", 0) or 0
    passed = td.get("passed", 0) or 0
    return (passed / total) if total else 0.0


def _bucket_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    total = len(rows)
    full_passed = sum(1 for row in rows if full_ok(row))
    build_passed = sum(1 for row in rows if build_ok(row))
    built_rows = [row for row in rows if build_ok(row)]
    avg_test_ratio = (sum(task_test_pass_ratio(row) for row in built_rows) / len(built_rows)) if built_rows else 0.0
    mean_score = sum(float(row.get("score", 0.0) or 0.0) for row in rows) / total if total else 0.0
    return {
        "N": total,
        "full_pass_pct": round1(100.0 * full_passed / total) if total else 0.0,
        "build_pct": round1(100.0 * build_passed / total) if total else 0.0,
        "cond_test_pass_pct": floor1(100.0 * avg_test_ratio),
        "mean_task_score": round4(mean_score),
    }


def _paired_contingency(
    left_rows: dict[str, dict[str, Any]],
    right_rows: dict[str, dict[str, Any]],
    keys: list[str],
    predicate,
) -> dict[str, int]:
    buckets = {
        "left_yes_right_yes": 0,
        "left_yes_right_no": 0,
        "left_no_right_yes": 0,
        "left_no_right_no": 0,
    }
    for key in keys:
        left_ok = predicate(left_rows[key])
        right_ok = predicate(right_rows[key])
        if left_ok and right_ok:
            buckets["left_yes_right_yes"] += 1
        elif left_ok and not right_ok:
            buckets["left_yes_right_no"] += 1
        elif not left_ok and right_ok:
            buckets["left_no_right_yes"] += 1
        else:
            buckets["left_no_right_no"] += 1
    return buckets


def _top_project_deltas(
    left_rows: dict[str, dict[str, Any]],
    right_rows: dict[str, dict[str, Any]],
    keys: list[str],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        project = "/".join(key.split("/")[:2])
        grouped[project].append(key)

    deltas: list[dict[str, Any]] = []
    for project, project_keys in grouped.items():
        left_bucket = _bucket_metrics([left_rows[k] for k in project_keys])
        right_bucket = _bucket_metrics([right_rows[k] for k in project_keys])
        deltas.append(
            {
                "project": project,
                "N": len(project_keys),
                "delta_full_pass_pct": round1(left_bucket["full_pass_pct"] - right_bucket["full_pass_pct"]),
                "delta_build_pct": round1(left_bucket["build_pct"] - right_bucket["build_pct"]),
                "delta_cond_test_pass_pct": round1(
                    left_bucket["cond_test_pass_pct"] - right_bucket["cond_test_pass_pct"]
                ),
            }
        )

    return {
        "largest_full_pass_gains": sorted(
            deltas,
            key=lambda item: (item["delta_full_pass_pct"], item["delta_build_pct"], item["N"]),
            reverse=True,
        )[:10],
        "largest_full_pass_losses": sorted(
            deltas,
            key=lambda item: (item["delta_full_pass_pct"], item["delta_build_pct"], -item["N"]),
        )[:10],
    }


def compare_pair(model_key: str, spec: dict[str, Any]) -> dict[str, Any]:
    left_rows = iter_rows(spec["l2tol3"])
    right_rows = iter_rows(spec["direct"])
    intersection = sorted(set(left_rows) & set(right_rows))
    left_only = sorted(set(left_rows) - set(right_rows))
    right_only = sorted(set(right_rows) - set(left_rows))

    overall = {
        "l2tol3": _bucket_metrics([left_rows[key] for key in intersection]),
        "direct_subset": _bucket_metrics([right_rows[key] for key in intersection]),
    }
    overall["delta"] = {
        metric: round1(overall["l2tol3"][metric] - overall["direct_subset"][metric])
        if metric != "mean_task_score"
        else round4(overall["l2tol3"][metric] - overall["direct_subset"][metric])
        for metric in ["full_pass_pct", "build_pct", "cond_test_pass_pct", "mean_task_score"]
    }

    by_language: dict[str, dict[str, Any]] = {}
    for lang in LANG_ORDER:
        lang_keys = [key for key in intersection if key.split("/")[0] == lang]
        if not lang_keys:
            continue
        l2_bucket = _bucket_metrics([left_rows[key] for key in lang_keys])
        direct_bucket = _bucket_metrics([right_rows[key] for key in lang_keys])
        by_language[lang] = {
            "label": LANG_LABEL.get(lang, lang),
            "N": len(lang_keys),
            "l2tol3": l2_bucket,
            "direct_subset": direct_bucket,
            "delta": {
                metric: round1(l2_bucket[metric] - direct_bucket[metric])
                if metric != "mean_task_score"
                else round4(l2_bucket[metric] - direct_bucket[metric])
                for metric in ["full_pass_pct", "build_pct", "cond_test_pass_pct", "mean_task_score"]
            },
        }

    return {
        "model_key": model_key,
        "model_label": spec["label"],
        "counts": {
            "l2tol3_tasks": len(left_rows),
            "direct_tasks": len(right_rows),
            "intersection_tasks": len(intersection),
            "l2tol3_only_tasks": len(left_only),
            "direct_only_tasks": len(right_only),
        },
        "overall": overall,
        "by_language": by_language,
        "paired_full_pass_contingency": _paired_contingency(left_rows, right_rows, intersection, full_ok),
        "paired_build_contingency": _paired_contingency(left_rows, right_rows, intersection, build_ok),
        "project_delta_extremes": _top_project_deltas(left_rows, right_rows, intersection),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# L2-to-L3 vs L3 Direct Comparison")
    lines.append("")
    lines.append(
        "这份报告比较 `finalresults/L2toL3` 与 `finalresults/L3/direct` 中可一一对齐的同任务结果，"
        "用于观察“把 L2 生成结果中的目标函数单独抽取出来，再放到 L3 函数级评测框架下”后，"
        "与原始 L3 direct 生成结果相比会发生什么变化。"
    )
    lines.append("")
    lines.append("口径说明：")
    lines.append("- 只比较两个目录中都存在的同名任务 JSON。")
    lines.append("- 当前可对齐任务数为 1,891 个；原始 L3 direct 额外还有 433 个任务，不纳入这次 paired comparison。")
    lines.append("- `Cond. test pass` 表示 build-successful tasks 上任务级 `test_pass_ratio` 的平均值。")
    lines.append("")

    for model_key in ["gpt54", "sonnet"]:
        block = payload[model_key]
        lines.append(f"## {block['model_label']}")
        lines.append("")
        counts = block["counts"]
        lines.append(
            f"- Comparable tasks: {counts['intersection_tasks']} "
            f"(L2toL3 = {counts['l2tol3_tasks']}, Direct = {counts['direct_tasks']}, Direct-only = {counts['direct_only_tasks']})"
        )
        lines.append("")
        lines.append("| Scope | N | Full-pass | Build | Cond. test pass | Mean task score |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        ov_l = block["overall"]["l2tol3"]
        ov_r = block["overall"]["direct_subset"]
        ov_d = block["overall"]["delta"]
        lines.append(
            f"| L2toL3 | {ov_l['N']} | {ov_l['full_pass_pct']:.1f} | {ov_l['build_pct']:.1f} | "
            f"{ov_l['cond_test_pass_pct']:.1f} | {ov_l['mean_task_score']:.4f} |"
        )
        lines.append(
            f"| Direct subset | {ov_r['N']} | {ov_r['full_pass_pct']:.1f} | {ov_r['build_pct']:.1f} | "
            f"{ov_r['cond_test_pass_pct']:.1f} | {ov_r['mean_task_score']:.4f} |"
        )
        lines.append(
            f"| Delta (L2toL3 - Direct) |  | {ov_d['full_pass_pct']:.1f} | {ov_d['build_pct']:.1f} | "
            f"{ov_d['cond_test_pass_pct']:.1f} | {ov_d['mean_task_score']:.4f} |"
        )
        lines.append("")

        lines.append("### By Language")
        lines.append("")
        lines.append("| Language | N | L2toL3 Full | Direct Full | ΔFull | L2toL3 Build | Direct Build | ΔBuild | L2toL3 Cond. Test | Direct Cond. Test | ΔCond. Test |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for lang in LANG_ORDER:
            if lang not in block["by_language"]:
                continue
            row = block["by_language"][lang]
            lines.append(
                f"| {row['label']} | {row['N']} | "
                f"{row['l2tol3']['full_pass_pct']:.1f} | {row['direct_subset']['full_pass_pct']:.1f} | {row['delta']['full_pass_pct']:.1f} | "
                f"{row['l2tol3']['build_pct']:.1f} | {row['direct_subset']['build_pct']:.1f} | {row['delta']['build_pct']:.1f} | "
                f"{row['l2tol3']['cond_test_pass_pct']:.1f} | {row['direct_subset']['cond_test_pass_pct']:.1f} | {row['delta']['cond_test_pass_pct']:.1f} |"
            )
        lines.append("")

        full_ct = block["paired_full_pass_contingency"]
        build_ct = block["paired_build_contingency"]
        lines.append("### Paired Contingency")
        lines.append("")
        lines.append(
            f"- Full-pass: both yes = {full_ct['left_yes_right_yes']}, "
            f"L2toL3 only = {full_ct['left_yes_right_no']}, "
            f"Direct only = {full_ct['left_no_right_yes']}, "
            f"both no = {full_ct['left_no_right_no']}."
        )
        lines.append(
            f"- Build: both yes = {build_ct['left_yes_right_yes']}, "
            f"L2toL3 only = {build_ct['left_yes_right_no']}, "
            f"Direct only = {build_ct['left_no_right_yes']}, "
            f"both no = {build_ct['left_no_right_no']}."
        )
        lines.append("")

        lines.append("### Largest Project-Level Full-pass Gains")
        lines.append("")
        lines.append("| Project | N | ΔFull | ΔBuild | ΔCond. Test |")
        lines.append("|---|---:|---:|---:|---:|")
        for item in block["project_delta_extremes"]["largest_full_pass_gains"]:
            lines.append(
                f"| {item['project']} | {item['N']} | {item['delta_full_pass_pct']:.1f} | "
                f"{item['delta_build_pct']:.1f} | {item['delta_cond_test_pass_pct']:.1f} |"
            )
        lines.append("")

        lines.append("### Largest Project-Level Full-pass Losses")
        lines.append("")
        lines.append("| Project | N | ΔFull | ΔBuild | ΔCond. Test |")
        lines.append("|---|---:|---:|---:|---:|")
        for item in block["project_delta_extremes"]["largest_full_pass_losses"]:
            lines.append(
                f"| {item['project']} | {item['N']} | {item['delta_full_pass_pct']:.1f} | "
                f"{item['delta_build_pct']:.1f} | {item['delta_cond_test_pass_pct']:.1f} |"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def write_csv(payload: dict[str, Any], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "model",
                "scope",
                "group",
                "N",
                "l2tol3_full_pass_pct",
                "direct_full_pass_pct",
                "delta_full_pass_pct",
                "l2tol3_build_pct",
                "direct_build_pct",
                "delta_build_pct",
                "l2tol3_cond_test_pass_pct",
                "direct_cond_test_pass_pct",
                "delta_cond_test_pass_pct",
                "l2tol3_mean_task_score",
                "direct_mean_task_score",
                "delta_mean_task_score",
            ]
        )
        for model_key in ["gpt54", "sonnet"]:
            block = payload[model_key]
            ov = block["overall"]
            writer.writerow(
                [
                    model_key,
                    "overall",
                    "overall",
                    ov["l2tol3"]["N"],
                    ov["l2tol3"]["full_pass_pct"],
                    ov["direct_subset"]["full_pass_pct"],
                    ov["delta"]["full_pass_pct"],
                    ov["l2tol3"]["build_pct"],
                    ov["direct_subset"]["build_pct"],
                    ov["delta"]["build_pct"],
                    ov["l2tol3"]["cond_test_pass_pct"],
                    ov["direct_subset"]["cond_test_pass_pct"],
                    ov["delta"]["cond_test_pass_pct"],
                    ov["l2tol3"]["mean_task_score"],
                    ov["direct_subset"]["mean_task_score"],
                    ov["delta"]["mean_task_score"],
                ]
            )
            for lang in LANG_ORDER:
                if lang not in block["by_language"]:
                    continue
                row = block["by_language"][lang]
                writer.writerow(
                    [
                        model_key,
                        "language",
                        lang,
                        row["N"],
                        row["l2tol3"]["full_pass_pct"],
                        row["direct_subset"]["full_pass_pct"],
                        row["delta"]["full_pass_pct"],
                        row["l2tol3"]["build_pct"],
                        row["direct_subset"]["build_pct"],
                        row["delta"]["build_pct"],
                        row["l2tol3"]["cond_test_pass_pct"],
                        row["direct_subset"]["cond_test_pass_pct"],
                        row["delta"]["cond_test_pass_pct"],
                        row["l2tol3"]["mean_task_score"],
                        row["direct_subset"]["mean_task_score"],
                        row["delta"]["mean_task_score"],
                    ]
                )


def main() -> None:
    payload = {model_key: compare_pair(model_key, spec) for model_key, spec in MODEL_PAIRS.items()}

    json_path = REPORTS_ROOT / "l2tol3_vs_l3_direct.json"
    md_path = REPORTS_ROOT / "l2tol3_vs_l3_direct.md"
    csv_path = REPORTS_ROOT / "l2tol3_vs_l3_direct.csv"

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    write_csv(payload, csv_path)

    print(json.dumps({"json": str(json_path), "md": str(md_path), "csv": str(csv_path)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
