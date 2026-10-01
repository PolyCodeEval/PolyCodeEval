from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from common import DATASETS_ROOT, parse_readme_loc_tables, round1


def count_l0_l1_tasks() -> tuple[int, int]:
    l0 = sum(1 for _ in DATASETS_ROOT.glob("*/*/tasks/L0_*/task.json"))
    l1 = sum(1 for _ in DATASETS_ROOT.glob("*/*/tasks/L1_*/task.json"))
    return l0, l1


def compute_l0_l1_avg_target_loc() -> float:
    rows = parse_readme_loc_tables()
    return sum(row["loc"] for row in rows) / len(rows)


def count_lines_from_bytes(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def resolve_source_path(project_dir: Path, rel_path: str) -> Path:
    for candidate_root in (project_dir / "src", project_dir):
        candidate = candidate_root / rel_path
        if candidate.is_file():
            return candidate
    rel_norm = rel_path.replace("\\", "/")
    basename = Path(rel_norm).name
    for candidate in (project_dir / "src").rglob(basename):
        if candidate.is_file():
            if rel_norm.endswith(candidate.as_posix().split("/src/", 1)[-1]):
                return candidate
            return candidate
    raise FileNotFoundError(f"Cannot resolve {rel_path} under {project_dir}")


def compute_l2_avg_target_loc() -> tuple[int, float]:
    total = 0
    loc_sum = 0
    for task_json in sorted(DATASETS_ROOT.glob("*/*/tasks/L2_*/task.json")):
        payload = json.loads(task_json.read_text(encoding="utf-8"))
        project_dir = task_json.parents[2]
        target_rel = payload["stub_info"]["file"]
        target_path = resolve_source_path(project_dir, target_rel)
        total += 1
        loc_sum += count_lines_from_bytes(target_path.read_bytes())
    return total, (loc_sum / total if total else 0.0)


def compute_l3_avg_target_loc() -> tuple[int, float]:
    total = 0
    loc_sum = 0
    for task_json in sorted(DATASETS_ROOT.glob("*/*/tasks/L3_*/task.json")):
        payload = json.loads(task_json.read_text(encoding="utf-8"))
        project_dir = task_json.parents[2]
        stub = payload["stub_info"]
        target_path = resolve_source_path(project_dir, stub["file"])
        source_bytes = target_path.read_bytes()
        body = source_bytes[int(stub["body_start_byte"]):int(stub["body_end_byte"])]
        total += 1
        loc_sum += count_lines_from_bytes(body)
    return total, (loc_sum / total if total else 0.0)


def main() -> None:
    l0_count, l1_count = count_l0_l1_tasks()
    l0_l1_avg_loc = compute_l0_l1_avg_target_loc()
    l2_count, l2_avg_loc = compute_l2_avg_target_loc()
    l3_count, l3_avg_loc = compute_l3_avg_target_loc()

    manual_rows = {
        "HumanEval": {"function_level": 164, "source": "manual from cited paper"},
        "MBPP": {"function_level": 974, "avg_loc": 6.8, "source": "manual from cited paper"},
        "LiveCodeBench": {"function_level": 511, "source": "manual from cited paper"},
        "MultiPL-E": {"function_level": 10678, "source": "manual from cited paper"},
        "RepoEval": {"function_level": 373, "source": "manual from cited paper"},
        "CrossCodeEval": {"function_level": 9928, "source": "manual from cited paper"},
        "xCodeEval": {"function_level": 25_000_000, "source": "manual from cited paper"},
        "DevEval": {"function_level": 2690, "source": "manual from cited paper"},
        "M2RC-EVAL": {"function_level": 10800, "source": "manual from cited paper"},
        "R2C2-Bench": {"function_level": 22828, "avg_loc": 1.8, "source": "manual from cited paper"},
        "MHRC-Bench": {"function_level": 1758, "source": "manual from cited paper"},
        "SWE-bench": {"file_level": 2294, "avg_loc": 32.8, "source": "manual from cited paper"},
        "Multi-SWE-bench": {"file_level": 1632, "avg_loc": 163.3, "source": "manual from cited paper"},
        "ProjectEval": {"project_level": 20, "skeleton_level": 20, "avg_loc": 402.2, "source": "manual from cited paper"},
        "ProjDevBench": {"project_level": 20, "avg_loc": 876.7, "source": "manual from cited paper"},
    }

    payload = {
        "manual_rows": manual_rows,
        "polycodeeval": {
            "L0": {"count": l0_count, "average_target_loc": round(l0_l1_avg_loc, 2)},
            "L1": {"count": l1_count, "average_target_loc": round(l0_l1_avg_loc, 2)},
            "L2": {"count": l2_count, "average_target_loc": round(l2_avg_loc, 2)},
            "L3": {"count": l3_count, "average_target_loc": round(l3_avg_loc, 2)},
        },
        "paper_row_rounded": {
            "L0": f"{l0_count} ({round1(l0_l1_avg_loc)})",
            "L1": f"{l1_count} ({round1(l0_l1_avg_loc)})",
            "L2": f"{l2_count} ({round1(l2_avg_loc)})",
            "L3": f"{l3_count} ({round1(l3_avg_loc)})",
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
