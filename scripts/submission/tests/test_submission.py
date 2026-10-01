from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parents[1]
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from core import (
    EXPECTED_TOTALS,
    MAX_LOG_FILE_BYTES,
    CanonicalRegistry,
    tree_hashes,
    validate_package,
)
from prepare_submission import prepare_submission


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def make_registry(root: Path, level: str) -> list[str]:
    task_ids = []
    for index in range(EXPECTED_TOTALS[level]):
        task_name = f"{level}_task_{index:04d}"
        task_id = f"cpp/project/{task_name}"
        write_json(
            root / "datasets" / "cpp" / "project" / "tasks" / task_name / "task.json",
            {"level": level},
        )
        task_ids.append(task_id)
    return task_ids


def metadata(level: str, scoring_mode: str) -> dict:
    return {
        "schemaVersion": "2",
        "benchmarkVersion": "pce-1.0",
        "level": level,
        "submissionName": "Test submission",
        "submitter": {"github": "example-user", "affiliation": ""},
        "method": {"name": "Method", "version": "1", "paperUrl": "", "codeUrl": ""},
        "model": {"name": "Model", "version": "1", "provider": ""},
        "evaluation": {
            "polycodeevalCommit": "abcdef1",
            "testMode": "both" if level in {"L2", "L3"} else "blackbox",
            "scoringMode": scoring_mode,
        },
        "notes": "",
    }


def l23_row(task_id: str, ratio: float = 0.5) -> dict:
    return {
        "task": task_id,
        "solver": "generated_outputs",
        "passed": False,
        "compile_passed": True,
        "full_passed": False,
        "test_pass_ratio": ratio,
        "compile_score": 0.5,
        "test_score": round(0.5 * ratio, 4),
        "score": round(0.5 + 0.5 * ratio, 4),
        "test_details": {"tests": [], "passed": 1, "failed": 1, "total": 2},
        "test_mode": "both",
    }


def l23_summary(task_id: str, row: dict) -> dict:
    score = row["score"]
    stats = {
        "total": 1,
        "full_passed": 0,
        "compile_passed": 1,
        "full_pass_rate": 0.0,
        "compile_pass_rate": 1.0,
        "compile_score": 0.5,
        "test_score": row["test_score"],
        "avg_score": score,
        "total_score": score,
    }
    return {
        "solver": "generated_outputs",
        **stats,
        "by_language": {"cpp": stats},
        "by_project": {"cpp/project": stats},
        "by_task": {
            task_id: {
                "score": score,
                "compile_score": 0.5,
                "test_score": row["test_score"],
                "test_pass_ratio": row["test_pass_ratio"],
            }
        },
    }


def l01_row(task_id: str, full_quality: bool) -> dict:
    radar = {
        "Correctness": 2.5,
        "Faithfulness": 4.0 if full_quality else None,
        "Architecture": 3.0 if full_quality else None,
        "Health": 5.0 if full_quality else None,
    }
    return {
        "task": task_id,
        "solver": "generated_outputs",
        "passed": False,
        "build_status": "success",
        "test_details": {"tests": [], "passed": 1, "failed": 1, "total": 2},
        "radar_scores": radar,
        "overall_score": 3.25 if full_quality else 2.5,
        "test_mode": "blackbox",
        "result_schema_version": "l0_scoring_v4_codex_review",
    }


def l01_summary(row: dict, full_quality: bool) -> dict:
    stats = {
        "total": 1,
        "passed": 0,
        "pass_rate": 0.0,
        "scored_tasks": 1,
        "scoring_coverage": 1.0,
        "avg_overall_score": row["overall_score"],
        "avg_correctness": 2.5,
        "avg_faithfulness": 4.0 if full_quality else None,
        "avg_architecture": 3.0 if full_quality else None,
        "avg_health": 5.0 if full_quality else None,
    }
    return {
        "solver": "generated_outputs",
        **stats,
        "by_language": {"cpp": stats},
        "by_project": {"cpp/project": stats},
        "test_case_stats": {"cpp/project": {"passed": 1, "failed": 1, "total": 2}},
    }


def make_package(root: Path, level: str, scoring_mode: str, task_id: str, row: dict, summary: dict) -> Path:
    package = root / "package"
    write_json(package / "submission.json", metadata(level, scoring_mode))
    write_json(package / "evaluation" / "summary.json", summary)
    language, project, task_name = task_id.split("/", 2)
    write_json(package / "evaluation" / language / project / f"{task_name}.json", row)
    return package


class SubmissionValidationTests(unittest.TestCase):
    def test_canonical_registry_matches_release_counts(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        for level, expected in EXPECTED_TOTALS.items():
            with self.subTest(level=level):
                self.assertEqual(CanonicalRegistry.discover(repo_root, level).total, expected)

    def test_partial_l2_submission_uses_fixed_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task_id = make_registry(root, "L2")[0]
            row = l23_row(task_id)
            package = make_package(root, "L2", "execution", task_id, row, l23_summary(task_id, row))
            report = validate_package(package, root)
            self.assertTrue(report.valid, report.to_dict())
            self.assertEqual(report.submitted_tasks, 1)
            self.assertEqual(report.missing_tasks, 149)
            self.assertEqual(report.aggregate["avg_execution_score"], round(0.75 / 150, 4))
            self.assertEqual(report.aggregate["build_pass_rate"], round(1 / 150, 4))

    def test_l0_correctness_only(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task_id = make_registry(root, "L0")[0]
            row = l01_row(task_id, False)
            package = make_package(root, "L0", "correctness_only", task_id, row, l01_summary(row, False))
            report = validate_package(package, root)
            self.assertTrue(report.valid, report.to_dict())
            self.assertFalse(report.aggregate["quality_eligible"])
            self.assertEqual(report.aggregate["avg_correctness"], round(2.5 / 58, 4))

    def test_l1_full_quality(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task_id = make_registry(root, "L1")[0]
            row = l01_row(task_id, True)
            package = make_package(root, "L1", "full_quality", task_id, row, l01_summary(row, True))
            report = validate_package(package, root)
            self.assertTrue(report.valid, report.to_dict())
            self.assertTrue(report.aggregate["quality_eligible"])
            self.assertEqual(report.aggregate["avg_overall"], round(3.25 / 58, 4))

    def test_full_quality_pass_without_parsed_tests_uses_evaluator_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task_id = make_registry(root, "L0")[0]
            row = l01_row(task_id, True)
            row["passed"] = True
            row["test_details"] = {"tests": [], "passed": 0, "failed": 0, "total": 0}
            row["radar_scores"]["Correctness"] = 5.0
            row["overall_score"] = 4.25
            summary = l01_summary(row, True)
            summary.update({"passed": 1, "pass_rate": 1.0, "avg_correctness": 5.0, "avg_overall_score": 4.25})
            summary["by_language"]["cpp"].update(
                {"passed": 1, "pass_rate": 1.0, "avg_correctness": 5.0, "avg_overall_score": 4.25}
            )
            summary["by_project"]["cpp/project"].update(
                {"passed": 1, "pass_rate": 1.0, "avg_correctness": 5.0, "avg_overall_score": 4.25}
            )
            summary.pop("test_case_stats")
            package = make_package(root, "L0", "full_quality", task_id, row, summary)
            report = validate_package(package, root)
            self.assertTrue(report.valid, report.to_dict())
            self.assertEqual(report.aggregate["avg_correctness"], round(5.0 / 58, 4))

    def test_invalid_l3_formula_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task_id = make_registry(root, "L3")[0]
            row = l23_row(task_id)
            row["score"] = 1.0
            package = make_package(root, "L3", "execution", task_id, row, l23_summary(task_id, row))
            report = validate_package(package, root)
            self.assertFalse(report.valid)
            self.assertIn("score_formula", {issue.code for issue in report.errors})

    def test_summary_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task_id = make_registry(root, "L2")[0]
            row = l23_row(task_id)
            summary = l23_summary(task_id, row)
            summary["compile_passed"] = 0
            package = make_package(root, "L2", "execution", task_id, row, summary)
            report = validate_package(package, root)
            self.assertFalse(report.valid)
            self.assertIn("summary_mismatch", {issue.code for issue in report.errors})

    def test_declared_test_mode_must_match_native_results(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task_id = make_registry(root, "L2")[0]
            row = l23_row(task_id)
            package = make_package(root, "L2", "execution", task_id, row, l23_summary(task_id, row))
            submission_path = package / "submission.json"
            submission = json.loads(submission_path.read_text(encoding="utf-8"))
            submission["evaluation"]["testMode"] = "blackbox"
            write_json(submission_path, submission)
            report = validate_package(package, root)
            self.assertFalse(report.valid)
            self.assertIn("test_mode_mismatch", {issue.code for issue in report.errors})

    def test_native_l3_setup_failure_is_normalized_to_zero(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task_id = make_registry(root, "L3")[0]
            row = {
                "task": task_id,
                "solver": "generated_outputs",
                "passed": False,
                "exit_code": -1,
                "duration_seconds": 0.0,
                "stdout": "",
                "stderr": "",
                "error": "Container setup failed",
                "test_mode": "both",
            }
            summary = {
                "total": 1,
                "full_passed": 0,
                "compile_passed": 0,
                "full_pass_rate": 0.0,
                "compile_pass_rate": 0.0,
                "compile_score": 0.0,
                "test_score": 0.0,
                "avg_score": 0.0,
                "total_score": 0.0,
            }
            package = make_package(root, "L3", "execution", task_id, row, summary)
            report = validate_package(package, root)
            self.assertTrue(report.valid, report.to_dict())
            self.assertEqual(report.aggregate["avg_execution_score"], 0.0)
            self.assertIn("derived_status_missing", {issue.code for issue in report.warnings})

    def test_log_type_and_size_limits_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task_id = make_registry(root, "L2")[0]
            row = l23_row(task_id)
            package = make_package(root, "L2", "execution", task_id, row, l23_summary(task_id, row))
            logs = package / "logs"
            logs.mkdir()
            (logs / "binary.bin").write_bytes(b"x")
            with (logs / "oversized.log").open("wb") as handle:
                handle.truncate(MAX_LOG_FILE_BYTES + 1)
            report = validate_package(package, root)
            codes = {issue.code for issue in report.errors}
            self.assertTrue({"log_type", "log_size"}.issubset(codes))

    def test_unsafe_zip_path_is_rejected(self) -> None:
        import zipfile

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("../submission.json", "{}")
            report = validate_package(archive, root)
            self.assertFalse(report.valid)
            self.assertIn("Unsafe ZIP entry", report.errors[0].message)

            windows_archive = root / "windows-absolute.zip"
            with zipfile.ZipFile(windows_archive, "w") as handle:
                handle.writestr("C:\\Users\\name\\submission.json", "{}")
            windows_report = validate_package(windows_archive, root)
            self.assertFalse(windows_report.valid)
            self.assertIn("Unsafe ZIP entry", windows_report.errors[0].message)

    def test_unknown_task_secret_and_generated_code_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            canonical = make_registry(root, "L2")[0]
            unknown = "cpp/project/L2_unknown"
            row = l23_row(unknown)
            package = make_package(root, "L2", "execution", unknown, row, l23_summary(unknown, row))
            (package / "generated.py").write_text("print('generated')\n", encoding="utf-8")
            (package / "logs").mkdir()
            (package / "logs" / "run.log").write_text("OPENAI_API_KEY=abcdefghijklmnopqrstuv\n", encoding="utf-8")
            report = validate_package(package, root)
            codes = {issue.code for issue in report.errors}
            self.assertFalse(report.valid)
            self.assertTrue({"unknown_task", "unexpected_artifact", "secret"}.issubset(codes))
            self.assertNotEqual(canonical, unknown)


class PrepareSubmissionTests(unittest.TestCase):
    def test_prepare_preserves_evaluation_files_and_creates_valid_zip(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            task_id = make_registry(root, "L2")[0]
            row = l23_row(task_id)
            native = root / "native"
            write_json(native / "summary.json", l23_summary(task_id, row))
            write_json(native / "cpp" / "project" / "L2_task_0000.json", row)
            before = tree_hashes(native)
            output = root / "my-submission"
            args = argparse.Namespace(
                results=native,
                output=output,
                level="L2",
                submission_name="My submission",
                github_user="example-user",
                affiliation="",
                method="Method",
                method_version="1",
                method_paper_url="",
                method_code_url="",
                model="Model",
                model_version="1",
                model_provider="",
                scoring_mode=None,
                evaluation_command="",
                started_at="",
                finished_at="",
                logs=None,
                notes="",
                repo_root=root,
            )
            directory, archive, report = prepare_submission(args)
            self.assertEqual(before, tree_hashes(directory / "evaluation"))
            self.assertTrue(archive.is_file())
            self.assertTrue(report["valid"])
            zipped = validate_package(archive, root)
            self.assertTrue(zipped.valid, zipped.to_dict())


if __name__ == "__main__":
    unittest.main()
