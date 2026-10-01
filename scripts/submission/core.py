"""Shared parsing, validation, and aggregation for result submissions."""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import re
import tempfile
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

EXPECTED_TOTALS = {"L0": 58, "L1": 58, "L2": 150, "L3": 2324}
LANGUAGES = ("cpp", "go", "java", "javascript", "python")
LOG_SUFFIXES = {".log", ".txt", ".json", ".jsonl"}
MAX_LOG_FILE_BYTES = 5 * 1024 * 1024
MAX_LOG_TOTAL_BYTES = 20 * 1024 * 1024
FLOAT_TOLERANCE = 1.5e-4

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_GITHUB_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_COMMIT_RE = re.compile(r"^(?:[0-9a-fA-F]{7,40}|unknown)$")
_SECRET_PATTERNS = (
    re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        r"(?i)\b(?:[a-z0-9]+[_-])?(?:api[_-]?key|access[_-]?token|secret[_-]?key|password)\b"
        r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}"
    ),
)
_LOCAL_PATH_RE = re.compile(r"(?:/Users/[^/\s]+/|/home/[^/\s]+/|[A-Za-z]:\\Users\\[^\\\s]+\\)")
_SOURCE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".go", ".java", ".js",
    ".jsx", ".mjs", ".py", ".ts", ".tsx", ".class", ".jar", ".o", ".so",
}


class SubmissionError(RuntimeError):
    """Raised when a package cannot be opened or its registry is unavailable."""


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    path: str = ""
    task: str = ""


@dataclass
class ValidationReport:
    valid: bool = False
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    aggregate: dict[str, Any] = field(default_factory=dict)
    submitted_tasks: int = 0
    expected_tasks: int = 0
    missing_tasks: int = 0
    log_files: int = 0
    log_bytes: int = 0

    def error(self, code: str, message: str, *, path: str = "", task: str = "") -> None:
        self.errors.append(Issue("error", code, message, path, task))

    def warn(self, code: str, message: str, *, path: str = "", task: str = "") -> None:
        self.warnings.append(Issue("warning", code, message, path, task))

    def finish(self) -> "ValidationReport":
        self.valid = not self.errors
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [asdict(issue) for issue in self.errors],
            "warnings": [asdict(issue) for issue in self.warnings],
            "metadata": self.metadata,
            "submittedTasks": self.submitted_tasks,
            "expectedTasks": self.expected_tasks,
            "missingTasks": self.missing_tasks,
            "logs": {"files": self.log_files, "bytes": self.log_bytes},
            "aggregate": self.aggregate,
        }


@dataclass(frozen=True)
class CanonicalRegistry:
    level: str
    task_ids: frozenset[str]

    @property
    def total(self) -> int:
        return EXPECTED_TOTALS[self.level]

    @property
    def by_language(self) -> dict[str, int]:
        counts = {language: 0 for language in LANGUAGES}
        for task_id in self.task_ids:
            counts[task_id.split("/", 1)[0]] += 1
        return counts

    @classmethod
    def discover(cls, repo_root: Path, level: str) -> "CanonicalRegistry":
        level = _validate_level(level)
        datasets = repo_root / "datasets"
        task_ids: set[str] = set()
        if datasets.is_dir():
            for task_file in sorted(datasets.glob("*/*/tasks/*/task.json")):
                try:
                    payload = _read_json(task_file)
                except (OSError, ValueError):
                    continue
                if payload.get("level") != level:
                    continue
                task_dir = task_file.parent
                project = task_dir.parents[1].name
                language = task_dir.parents[2].name
                task_ids.add(f"{language}/{project}/{task_dir.name}")

        if not task_ids:
            manifest = repo_root / "website/public/data/common/manifest.json"
            try:
                payload = _read_json(manifest)
                task_ids = set(payload.get("tasks", {}).get(level, []))
            except (OSError, ValueError, AttributeError):
                task_ids = set()

        expected = EXPECTED_TOTALS[level]
        if len(task_ids) != expected:
            raise SubmissionError(
                f"Canonical {level} registry contains {len(task_ids)} tasks; expected {expected}. "
                "Synchronize the pce-1.0 dataset or restore the official website manifest."
            )
        return cls(level, frozenset(task_ids))


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@contextlib.contextmanager
def opened_package(source: Path) -> Iterator[Path]:
    """Open a directory or safely extract a ZIP and yield its package root."""
    source = source.resolve()
    if source.is_dir():
        yield _resolve_package_root(source)
        return
    if not source.is_file() or source.suffix.lower() != ".zip":
        raise SubmissionError("Submission must be a directory or a .zip archive.")

    with tempfile.TemporaryDirectory(prefix="pce_submission_") as temp_name:
        temp_root = Path(temp_name)
        with zipfile.ZipFile(source) as archive:
            seen: set[str] = set()
            for info in archive.infolist():
                name = info.filename.replace("\\", "/")
                if name in seen:
                    raise SubmissionError(f"Duplicate ZIP entry: {name}")
                seen.add(name)
                if not _safe_relative_path(name):
                    raise SubmissionError(f"Unsafe ZIP entry: {name}")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise SubmissionError(f"Symbolic links are not allowed: {name}")
            archive.extractall(temp_root)
        yield _resolve_package_root(temp_root)


def validate_package(source: Path, repo_root: Path | None = None) -> ValidationReport:
    report = ValidationReport()
    repo_root = (repo_root or repository_root()).resolve()
    try:
        with opened_package(source) as root:
            _validate_root_entries(root, report)
            metadata = _load_and_validate_metadata(root / "submission.json", report)
            report.metadata = metadata
            level = metadata.get("level")
            if level not in EXPECTED_TOTALS:
                return report.finish()

            try:
                registry = CanonicalRegistry.discover(repo_root, level)
            except SubmissionError as error:
                report.error("canonical_registry", str(error))
                return report.finish()

            rows = _load_native_results(root / "evaluation", level, registry, report)
            report.submitted_tasks = len(rows)
            report.expected_tasks = registry.total
            report.missing_tasks = registry.total - len(rows)
            _validate_declared_test_mode(metadata, rows, report)
            _validate_logs(root / "logs", report)
            _scan_package_text(root, report)

            scoring_mode = _scoring_mode(metadata, level)
            normalized = [_normalize_result(row, level, scoring_mode, report) for row in rows]
            normalized = [row for row in normalized if row is not None]
            report.aggregate = aggregate_rows(
                normalized,
                registry,
                scoring_mode=scoring_mode,
                fixed_denominator=True,
            )
            _validate_native_summary(
                root / "evaluation" / "summary.json",
                normalized,
                registry,
                scoring_mode,
                report,
            )
    except (OSError, ValueError, zipfile.BadZipFile, SubmissionError) as error:
        report.error("package", str(error))
    return report.finish()


def aggregate_package(source: Path, repo_root: Path | None = None) -> dict[str, Any]:
    report = validate_package(source, repo_root)
    if not report.valid:
        messages = "; ".join(issue.message for issue in report.errors[:5])
        raise SubmissionError(f"Submission is invalid: {messages}")
    return report.aggregate


def aggregate_rows(
    rows: list[dict[str, Any]],
    registry: CanonicalRegistry,
    *,
    scoring_mode: str,
    fixed_denominator: bool,
) -> dict[str, Any]:
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_project: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_language[row["language"]].append(row)
        by_project[f'{row["language"]}/{row["project"]}'].append(row)

    overall_denominator = registry.total if fixed_denominator else len(rows)
    result = _stats(rows, overall_denominator, registry.total, scoring_mode)

    language_counts = registry.by_language
    result["by_language"] = {
        language: _stats(
            by_language.get(language, []),
            language_counts[language] if fixed_denominator else len(by_language.get(language, [])),
            language_counts[language],
            scoring_mode,
        )
        for language in LANGUAGES
    }

    canonical_by_project: dict[str, int] = defaultdict(int)
    for task_id in registry.task_ids:
        language, project, _ = task_id.split("/", 2)
        canonical_by_project[f"{language}/{project}"] += 1
    result["by_project"] = {
        project: _stats(
            by_project.get(project, []),
            expected if fixed_denominator else len(by_project.get(project, [])),
            expected,
            scoring_mode,
        )
        for project, expected in sorted(canonical_by_project.items())
    }
    result["by_task"] = {
        row["task"]: {
            "buildSuccess": row["buildSuccess"],
            "fullPass": row["fullPass"],
            "testPassRatio": _round(row["testPassRatio"]),
            "executionScore": _round(row["executionScore"]),
            "correctness": _nullable_round(row.get("correctness")),
            "faithfulness": _nullable_round(row.get("faithfulness")),
            "architecture": _nullable_round(row.get("architecture")),
            "health": _nullable_round(row.get("health")),
            "overall": _nullable_round(row.get("overall")),
        }
        for row in sorted(rows, key=lambda item: item["task"])
    }
    submitted_ids = {row["task"] for row in rows}
    result["missing_task_ids"] = sorted(registry.task_ids - submitted_ids)
    test_case_stats: dict[str, dict[str, int]] = {}
    for project, project_rows in sorted(by_project.items()):
        passed = sum(int(row.get("testCasesPassed", 0)) for row in project_rows)
        failed = sum(int(row.get("testCasesFailed", 0)) for row in project_rows)
        total = sum(int(row.get("testCasesTotal", 0)) for row in project_rows)
        if total:
            test_case_stats[project] = {"passed": passed, "failed": failed, "total": total}
    result["test_case_stats"] = test_case_stats
    return result


def _stats(
    rows: list[dict[str, Any]], denominator: int, expected: int, scoring_mode: str
) -> dict[str, Any]:
    submitted = len(rows)
    build_count = sum(bool(row["buildSuccess"]) for row in rows)
    full_count = sum(bool(row["fullPass"]) for row in rows)
    test_sum = sum(float(row["testPassRatio"]) for row in rows)
    execution_sum = sum(float(row["executionScore"]) for row in rows)
    compile_score_sum = sum(float(row.get("compileScore", 0.0)) for row in rows)
    test_score_sum = sum(float(row.get("testScore", 0.0)) for row in rows)
    built_ratios = [float(row["testPassRatio"]) for row in rows if row["buildSuccess"]]
    result: dict[str, Any] = {
        "expected_tasks": expected,
        "submitted_tasks": submitted,
        "missing_tasks": max(expected - submitted, 0),
        "coverage_rate": _division(submitted, expected),
        "build_passed": build_count,
        "full_passed": full_count,
        "build_pass_rate": _division(build_count, denominator),
        "full_pass_rate": _division(full_count, denominator),
        "avg_test_pass_ratio": _division(test_sum, denominator),
        "conditional_test_pass_ratio": _mean(built_ratios),
        "total_execution_score": _round(execution_sum),
        "avg_execution_score": _division(execution_sum, denominator),
        "total_compile_score": _round(compile_score_sum),
        "total_test_score": _round(test_score_sum),
        "scoring_mode": scoring_mode,
    }

    for key in ("correctness", "faithfulness", "architecture", "health", "overall"):
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        if key == "correctness" or scoring_mode == "full_quality":
            result[f"avg_{key}"] = _division(sum(values), denominator)
        else:
            result[f"avg_{key}"] = None
    result["quality_eligible"] = scoring_mode == "full_quality"
    return result


def _normalize_result(
    payload: dict[str, Any], level: str, scoring_mode: str, report: ValidationReport
) -> dict[str, Any] | None:
    task_id = payload.get("task")
    if not isinstance(task_id, str):
        return None
    language, project, _ = task_id.split("/", 2)
    if level in ("L0", "L1"):
        return _normalize_l01(payload, task_id, language, project, scoring_mode, report)
    return _normalize_l23(payload, task_id, language, project, report)


def _normalize_l01(
    payload: dict[str, Any],
    task_id: str,
    language: str,
    project: str,
    scoring_mode: str,
    report: ValidationReport,
) -> dict[str, Any]:
    passed = _require_bool(payload, "passed", report, task_id)
    test_ratio = _test_ratio(payload, report, task_id)
    test_details = payload.get("test_details") if isinstance(payload.get("test_details"), dict) else {}
    if scoring_mode == "full_quality" and passed and _safe_count(test_details.get("total")) == 0:
        test_ratio = 1.0
    build_status = payload.get("build_status")
    if build_status is not None and not isinstance(build_status, str):
        report.error("field_type", "build_status must be a string.", task=task_id)
    build = bool(passed or test_ratio > 0 or build_status in {"ok", "success", "passed"})
    radar = payload.get("radar_scores")
    if not isinstance(radar, dict):
        report.error("field_type", "radar_scores must be an object.", task=task_id)
        radar = {}

    values: dict[str, float | None] = {}
    for output_key, native_key in (
        ("correctness", "Correctness"),
        ("faithfulness", "Faithfulness"),
        ("architecture", "Architecture"),
        ("health", "Health"),
    ):
        values[output_key] = _optional_score(radar.get(native_key), native_key, report, task_id)

    expected_correctness = 5.0 * test_ratio
    if values["correctness"] is None:
        report.error("missing_score", "Correctness is required in radar_scores.", task=task_id)
        values["correctness"] = expected_correctness
    elif not _close(values["correctness"], expected_correctness, 0.011):
        report.error(
            "score_formula",
            f"Correctness must equal 5 * test pass ratio ({expected_correctness:.4f}).",
            task=task_id,
        )

    overall = _optional_score(payload.get("overall_score"), "overall_score", report, task_id)
    if scoring_mode == "full_quality":
        for key in ("faithfulness", "architecture", "health"):
            if values[key] is None:
                report.error("missing_score", f"{key.title()} is required for full_quality.", task=task_id)
        if overall is None:
            report.error("missing_score", "overall_score is required for full_quality.", task=task_id)
        elif all(values[key] is not None for key in ("correctness", "faithfulness", "architecture", "health")):
            expected_overall = round(
                0.4 * float(values["correctness"])
                + 0.25 * float(values["faithfulness"])
                + 0.25 * float(values["architecture"])
                + 0.1 * float(values["health"]),
                2,
            )
            if not _close(overall, expected_overall, 0.011):
                report.error(
                    "score_formula",
                    f"overall_score is {overall:.4f}; expected {expected_overall:.4f}.",
                    task=task_id,
                )
    elif overall is not None and values["correctness"] is not None and not _close(overall, values["correctness"], 0.011):
        report.warn(
            "unused_quality_score",
            "overall_score differs from Correctness and is ignored in correctness_only mode.",
            task=task_id,
        )

    return {
        "task": task_id,
        "language": language,
        "project": project,
        "buildSuccess": build,
        "fullPass": bool(passed),
        "testPassRatio": test_ratio,
        "executionScore": test_ratio,
        "compileScore": 0.0,
        "testScore": test_ratio,
        **values,
        "overall": overall,
        "testCasesPassed": _safe_count(test_details.get("passed")),
        "testCasesFailed": _safe_count(test_details.get("failed")),
        "testCasesTotal": _safe_count(test_details.get("total")),
    }


def _normalize_l23(
    payload: dict[str, Any],
    task_id: str,
    language: str,
    project: str,
    report: ValidationReport,
) -> dict[str, Any]:
    passed = _require_bool(payload, "passed", report, task_id)
    compile_passed = _native_bool(payload, "compile_passed", passed, report, task_id)
    full_passed = _native_bool(payload, "full_passed", passed, report, task_id)
    if passed is not None and full_passed is not None and passed != full_passed:
        report.error("full_pass_mismatch", "passed and full_passed must agree.", task=task_id)
    if full_passed and not compile_passed:
        report.error("full_without_build", "full_passed requires compile_passed.", task=task_id)

    if isinstance(payload.get("test_details"), dict):
        parsed_ratio = _test_ratio(payload, report, task_id)
    elif not compile_passed:
        parsed_ratio = 0.0
        report.warn(
            "derived_test_details_missing",
            "test_details is missing from a failed native result and was normalized to zero.",
            task=task_id,
        )
    else:
        parsed_ratio = _test_ratio(payload, report, task_id)
    ratio = _number(payload.get("test_pass_ratio"), "test_pass_ratio", report, task_id, 0.0)
    if ratio is None:
        ratio = parsed_ratio
    elif not _close(ratio, parsed_ratio):
        report.error(
            "test_ratio_mismatch",
            f"test_pass_ratio is {ratio:.4f}; test_details imply {parsed_ratio:.4f}.",
            task=task_id,
        )
    expected_compile = 0.5 if compile_passed else 0.0
    expected_test = round(0.5 * ratio, 4) if compile_passed else 0.0
    expected_score = round(expected_compile + expected_test, 4)

    validated_scores: dict[str, float] = {}
    for key, expected_value in (
        ("compile_score", expected_compile),
        ("test_score", expected_test),
        ("score", expected_score),
    ):
        actual = _number(payload.get(key), key, report, task_id, 0.0)
        if actual is None:
            validated_scores[key] = expected_value
            report.warn(
                "derived_score_missing",
                f"{key} is missing and was normalized to {expected_value:.4f}.",
                task=task_id,
            )
        else:
            validated_scores[key] = actual
            if not _close(actual, expected_value):
                report.error(
                    "score_formula",
                    f"{key} is {actual:.4f}; expected {expected_value:.4f}.",
                    task=task_id,
                )
    if not compile_passed and ratio != 0:
        report.error("test_without_build", "test_pass_ratio must be zero when compilation fails.", task=task_id)

    return {
        "task": task_id,
        "language": language,
        "project": project,
        "buildSuccess": bool(compile_passed),
        "fullPass": bool(full_passed),
        "testPassRatio": ratio,
        "executionScore": validated_scores["score"],
        "compileScore": validated_scores["compile_score"],
        "testScore": validated_scores["test_score"],
        "correctness": None,
        "faithfulness": None,
        "architecture": None,
        "health": None,
        "overall": None,
    }


def _load_native_results(
    evaluation: Path,
    level: str,
    registry: CanonicalRegistry,
    report: ValidationReport,
) -> list[dict[str, Any]]:
    if not evaluation.is_dir():
        report.error("missing_evaluation", "evaluation/ is required.")
        return []
    summary = evaluation / "summary.json"
    if not summary.is_file():
        report.error("missing_summary", "evaluation/summary.json is required.")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(evaluation.rglob("*")):
        relative = path.relative_to(evaluation)
        if path.is_symlink():
            report.error("symlink", "Symbolic links are not allowed.", path=relative.as_posix())
            continue
        if path.is_dir() or relative.as_posix() == "summary.json":
            continue
        if path.suffix.lower() != ".json" or len(relative.parts) != 3:
            report.error(
                "evaluation_path",
                "Task results must use evaluation/<language>/<project>/<task>.json.",
                path=relative.as_posix(),
            )
            continue
        language, project, filename = relative.parts
        if language not in LANGUAGES:
            report.error("language", f"Unsupported language: {language}", path=relative.as_posix())
            continue
        try:
            payload = _read_json(path)
        except (OSError, ValueError) as error:
            report.error("invalid_json", str(error), path=relative.as_posix())
            continue
        if not isinstance(payload, dict):
            report.error("result_type", "Task result must be a JSON object.", path=relative.as_posix())
            continue
        task_id = payload.get("task")
        expected_id = f"{language}/{project}/{Path(filename).stem}"
        if task_id != expected_id:
            report.error(
                "task_path_mismatch",
                f"Result task must be {expected_id!r} for this path.",
                path=relative.as_posix(),
            )
            continue
        if task_id in seen:
            report.error("duplicate_task", "Task ID appears more than once.", task=task_id)
            continue
        seen.add(task_id)
        if task_id not in registry.task_ids:
            report.error("unknown_task", f"Task does not belong to canonical {level}.", task=task_id)
            continue
        if f"/{level}_" not in task_id:
            report.error("task_level", f"Task ID does not match declared level {level}.", task=task_id)
            continue
        rows.append(payload)

    if not rows:
        report.error("empty_submission", "At least one canonical task result is required.")
    return rows


def _load_and_validate_metadata(path: Path, report: ValidationReport) -> dict[str, Any]:
    if not path.is_file():
        report.error("missing_metadata", "submission.json is required.")
        return {}
    try:
        payload = _read_json(path)
    except (OSError, ValueError) as error:
        report.error("invalid_metadata", str(error), path="submission.json")
        return {}
    if not isinstance(payload, dict):
        report.error("metadata_type", "submission.json must contain an object.")
        return {}

    allowed = {
        "schemaVersion", "benchmarkVersion", "level", "submissionName", "submitter",
        "method", "model", "evaluation", "notes",
    }
    _reject_unknown(payload, allowed, report, "submission.json")
    _require_equal(payload, "schemaVersion", "2", report)
    _require_equal(payload, "benchmarkVersion", "pce-1.0", report)
    level = payload.get("level")
    if level not in EXPECTED_TOTALS:
        report.error("metadata_value", "level must be L0, L1, L2, or L3.", path="submission.json")
    _required_string(payload, "submissionName", report)

    submitter = _required_object(payload, "submitter", report)
    _reject_unknown(submitter, {"github", "affiliation"}, report, "submission.json.submitter")
    github = _required_string(submitter, "github", report, "submission.json.submitter")
    if github and not _GITHUB_RE.fullmatch(github):
        report.error("metadata_value", "submitter.github is not a valid GitHub username.")
    _optional_string(submitter, "affiliation", report, "submission.json.submitter")

    method = _required_object(payload, "method", report)
    _reject_unknown(method, {"name", "version", "paperUrl", "codeUrl"}, report, "submission.json.method")
    _required_string(method, "name", report, "submission.json.method")
    _required_string(method, "version", report, "submission.json.method")
    _optional_url(method, "paperUrl", report, "submission.json.method")
    _optional_url(method, "codeUrl", report, "submission.json.method")

    model = _required_object(payload, "model", report)
    _reject_unknown(model, {"name", "version", "provider"}, report, "submission.json.model")
    _required_string(model, "name", report, "submission.json.model")
    _required_string(model, "version", report, "submission.json.model")
    _optional_string(model, "provider", report, "submission.json.model")

    evaluation = _required_object(payload, "evaluation", report)
    _reject_unknown(
        evaluation,
        {
            "polycodeevalCommit", "testMode", "scoringMode", "command", "startedAt",
            "finishedAt", "environment", "packagedAt", "workingTreeDirty",
        },
        report,
        "submission.json.evaluation",
    )
    commit = _required_string(evaluation, "polycodeevalCommit", report, "submission.json.evaluation")
    if commit and not _COMMIT_RE.fullmatch(commit):
        report.error("metadata_value", "polycodeevalCommit must be a Git commit hash.")
    test_mode = _required_string(evaluation, "testMode", report, "submission.json.evaluation")
    if test_mode and test_mode not in {"blackbox", "whitebox", "both", "mixed"}:
        report.error("metadata_value", "testMode must be blackbox, whitebox, both, or mixed.")
    scoring_mode = _required_string(evaluation, "scoringMode", report, "submission.json.evaluation")
    valid_modes = {"execution"} if level in {"L2", "L3"} else {"correctness_only", "full_quality"}
    if level in EXPECTED_TOTALS and scoring_mode not in valid_modes:
        report.error("metadata_value", f"scoringMode for {level} must be one of {sorted(valid_modes)}.")
    for key in ("command", "startedAt", "finishedAt", "packagedAt"):
        _optional_string(evaluation, key, report, "submission.json.evaluation")
    if "workingTreeDirty" in evaluation and not isinstance(evaluation["workingTreeDirty"], bool):
        report.error("metadata_type", "workingTreeDirty must be a boolean.")
    environment = evaluation.get("environment", {})
    if not isinstance(environment, dict):
        report.error("metadata_type", "evaluation.environment must be an object.")
    else:
        _reject_unknown(environment, {"os", "architecture", "python", "docker"}, report, "submission.json.evaluation.environment")
        for key in ("os", "architecture", "python", "docker"):
            _optional_string(environment, key, report, "submission.json.evaluation.environment")
    _optional_string(payload, "notes", report)
    return payload


def _validate_declared_test_mode(
    metadata: dict[str, Any], rows: list[dict[str, Any]], report: ValidationReport
) -> None:
    evaluation = metadata.get("evaluation")
    declared = evaluation.get("testMode") if isinstance(evaluation, dict) else None
    observed = {
        row.get("test_mode")
        for row in rows
        if isinstance(row.get("test_mode"), str) and row.get("test_mode")
    }
    if not observed:
        report.warn("test_mode_missing", "No task result records a test_mode value.")
        return
    expected = next(iter(observed)) if len(observed) == 1 else "mixed"
    if declared != expected:
        report.error(
            "test_mode_mismatch",
            f"submission.json declares testMode={declared!r}; native results imply {expected!r}.",
        )


def _validate_native_summary(
    path: Path,
    rows: list[dict[str, Any]],
    registry: CanonicalRegistry,
    scoring_mode: str,
    report: ValidationReport,
) -> None:
    if not path.is_file() or not rows:
        return
    try:
        summary = _read_json(path)
    except (OSError, ValueError) as error:
        report.error("invalid_summary", str(error), path="evaluation/summary.json")
        return
    if not isinstance(summary, dict):
        report.error("summary_type", "summary.json must contain an object.")
        return

    submitted_registry = CanonicalRegistry(registry.level, frozenset(row["task"] for row in rows))
    computed = aggregate_rows(
        rows,
        submitted_registry,
        scoring_mode=scoring_mode,
        fixed_denominator=False,
    )
    if registry.level in {"L2", "L3"}:
        mapping = {
            "total": "submitted_tasks",
            "full_passed": "full_passed",
            "compile_passed": "build_passed",
            "full_pass_rate": "full_pass_rate",
            "compile_pass_rate": "build_pass_rate",
            "avg_score": "avg_execution_score",
            "total_score": "total_execution_score",
            "compile_score": "total_compile_score",
            "test_score": "total_test_score",
        }
    else:
        mapping = {
            "total": "submitted_tasks",
            "passed": "full_passed",
            "pass_rate": "full_pass_rate",
            "avg_correctness": "avg_correctness",
            "avg_faithfulness": "avg_faithfulness",
            "avg_architecture": "avg_architecture",
            "avg_health": "avg_health",
            "avg_overall_score": "avg_overall",
        }
    _compare_summary_scope(summary, computed, mapping, report, "overall")

    for native_group, computed_group in (("by_language", "by_language"), ("by_project", "by_project")):
        native = summary.get(native_group)
        if native is None:
            continue
        if not isinstance(native, dict):
            report.error("summary_type", f"{native_group} must be an object.")
            continue
        for key, native_values in native.items():
            expected_values = computed[computed_group].get(key)
            if expected_values is None:
                report.error("summary_group", f"Unexpected {native_group} entry: {key}")
                continue
            if isinstance(native_values, dict):
                _compare_summary_scope(native_values, expected_values, mapping, report, f"{native_group}.{key}")

    native_tasks = summary.get("by_task")
    if native_tasks is not None:
        if not isinstance(native_tasks, dict):
            report.error("summary_type", "by_task must be an object.")
        elif registry.level in {"L2", "L3"}:
            normalized_by_task = {row["task"]: row for row in rows}
            for task_id, values in native_tasks.items():
                row = normalized_by_task.get(task_id)
                if row is None or not isinstance(values, dict):
                    report.error("summary_group", f"Unexpected or invalid by_task entry: {task_id}")
                    continue
                expected_values = {
                    "score": row["executionScore"],
                    "compile_score": row["compileScore"],
                    "test_score": row["testScore"],
                    "test_pass_ratio": row["testPassRatio"],
                }
                _compare_summary_scope(
                    values,
                    expected_values,
                    {key: key for key in expected_values},
                    report,
                    f"by_task.{task_id}",
                )

    native_test_cases = summary.get("test_case_stats")
    if native_test_cases is not None and registry.level in {"L0", "L1"}:
        if not isinstance(native_test_cases, dict):
            report.error("summary_type", "test_case_stats must be an object.")
        else:
            expected_test_cases = computed["test_case_stats"]
            if native_test_cases != expected_test_cases:
                report.error(
                    "summary_mismatch",
                    "test_case_stats does not match the submitted task results.",
                    path="evaluation/summary.json",
                )

def _compare_summary_scope(
    native: dict[str, Any],
    computed: dict[str, Any],
    mapping: dict[str, str],
    report: ValidationReport,
    scope: str,
) -> None:
    for native_key, computed_key in mapping.items():
        if native_key not in native or native[native_key] is None:
            continue
        actual = native[native_key]
        expected = computed.get(computed_key)
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or expected is None:
            continue
        tolerance = FLOAT_TOLERANCE if isinstance(actual, float) else 0
        if abs(float(actual) - float(expected)) > tolerance:
            report.error(
                "summary_mismatch",
                f"{scope}.{native_key} is {actual}; recomputed value is {expected}.",
                path="evaluation/summary.json",
            )


def _validate_root_entries(root: Path, report: ValidationReport) -> None:
    allowed = {"submission.json", "evaluation", "logs"}
    if root.is_symlink():
        report.error("symlink", "The package root cannot be a symbolic link.")
    for entry in root.iterdir():
        if entry.name not in allowed:
            report.error("unexpected_artifact", f"Unexpected top-level entry: {entry.name}", path=entry.name)
        if entry.is_symlink():
            report.error("symlink", "Symbolic links are not allowed.", path=entry.name)
        if entry.is_file() and entry.suffix.lower() in _SOURCE_SUFFIXES:
            report.error("generated_code", "Generated-code artifacts are not accepted.", path=entry.name)


def _validate_logs(logs: Path, report: ValidationReport) -> None:
    if not logs.exists():
        return
    if not logs.is_dir() or logs.is_symlink():
        report.error("logs_path", "logs must be a regular directory.", path="logs")
        return
    total = 0
    count = 0
    for path in sorted(logs.rglob("*")):
        relative = path.relative_to(logs).as_posix()
        if path.is_symlink():
            report.error("symlink", "Symbolic links are not allowed.", path=f"logs/{relative}")
            continue
        if path.is_dir():
            continue
        count += 1
        size = path.stat().st_size
        total += size
        if path.suffix.lower() not in LOG_SUFFIXES:
            report.error("log_type", f"Unsupported log file type: {path.suffix or '<none>'}", path=f"logs/{relative}")
        if size > MAX_LOG_FILE_BYTES:
            report.error("log_size", "A log file exceeds the 5 MB limit.", path=f"logs/{relative}")
    report.log_files = count
    report.log_bytes = total
    if total > MAX_LOG_TOTAL_BYTES:
        report.error("logs_size", "Optional logs exceed the 20 MB total limit.", path="logs")


def _scan_package_text(root: Path, report: ValidationReport) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() not in {".json", ".jsonl", ".txt", ".log"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            report.error("text_encoding", "Submission text files must be UTF-8.", path=relative)
            continue
        if any(pattern.search(text) for pattern in _SECRET_PATTERNS):
            report.error("secret", "A probable credential or private key was detected.", path=relative)
        if _LOCAL_PATH_RE.search(text):
            report.warn("local_path", "A user-specific absolute path was detected.", path=relative)


def _test_ratio(payload: dict[str, Any], report: ValidationReport, task_id: str) -> float:
    details = payload.get("test_details")
    if not isinstance(details, dict):
        report.error("field_type", "test_details must be an object.", task=task_id)
        return 0.0
    passed = _nonnegative_int(details.get("passed"), "test_details.passed", report, task_id)
    failed = _nonnegative_int(details.get("failed"), "test_details.failed", report, task_id)
    total = _nonnegative_int(details.get("total"), "test_details.total", report, task_id)
    if passed is None or failed is None or total is None:
        return 0.0
    if passed + failed > total:
        report.error("test_counts", "passed + failed cannot exceed total.", task=task_id)
    return passed / total if total else 0.0


def _scoring_mode(metadata: dict[str, Any], level: str) -> str:
    evaluation = metadata.get("evaluation")
    if isinstance(evaluation, dict) and isinstance(evaluation.get("scoringMode"), str):
        return evaluation["scoringMode"]
    return "execution" if level in {"L2", "L3"} else "correctness_only"


def _resolve_package_root(root: Path) -> Path:
    if (root / "submission.json").is_file():
        return root
    entries = [entry for entry in root.iterdir() if entry.name != "__MACOSX"]
    directories = [entry for entry in entries if entry.is_dir()]
    if len(entries) == 1 and len(directories) == 1 and (directories[0] / "submission.json").is_file():
        return directories[0]
    return root


def _safe_relative_path(value: str) -> bool:
    if (
        not value
        or "\x00" in value
        or value.startswith(("/", "\\"))
        or re.match(r"^[A-Za-z]:/", value)
    ):
        return False
    path = PurePosixPath(value)
    return not any(part in {"", ".", ".."} for part in path.parts)


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Invalid JSON number: {value}")))


def _validate_level(level: str) -> str:
    if level not in EXPECTED_TOTALS:
        raise SubmissionError(f"Unsupported level: {level}")
    return level


def _require_bool(payload: dict[str, Any], key: str, report: ValidationReport, task: str) -> bool | None:
    value = payload.get(key)
    if not isinstance(value, bool):
        report.error("field_type", f"{key} must be a boolean.", task=task)
        return None
    return value


def _native_bool(
    payload: dict[str, Any],
    key: str,
    passed: bool | None,
    report: ValidationReport,
    task: str,
) -> bool | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    if value is None and passed is False:
        report.warn(
            "derived_status_missing",
            f"{key} is missing from a failed native result and was normalized to false.",
            task=task,
        )
        return False
    report.error("field_type", f"{key} must be a boolean.", task=task)
    return None


def _number(
    value: Any,
    key: str,
    report: ValidationReport,
    task: str,
    lower: float,
    upper: float = 1.0,
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        report.error("field_type", f"{key} must be a finite number.", task=task)
        return None
    result = float(value)
    if result < lower or result > upper:
        report.error("field_range", f"{key} must be between {lower} and {upper}.", task=task)
    return result


def _optional_score(value: Any, key: str, report: ValidationReport, task: str) -> float | None:
    return _number(value, key, report, task, 0.0, 5.0)


def _nonnegative_int(value: Any, key: str, report: ValidationReport, task: str) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        report.error("field_type", f"{key} must be a non-negative integer.", task=task)
        return None
    return value


def _safe_count(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _required_object(payload: dict[str, Any], key: str, report: ValidationReport) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        report.error("metadata_type", f"{key} must be an object.", path="submission.json")
        return {}
    return value


def _required_string(
    payload: dict[str, Any], key: str, report: ValidationReport, prefix: str = "submission.json"
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        report.error("metadata_type", f"{prefix}.{key} must be a non-empty string.")
        return ""
    return value


def _optional_string(
    payload: dict[str, Any], key: str, report: ValidationReport, prefix: str = "submission.json"
) -> None:
    if key in payload and not isinstance(payload[key], str):
        report.error("metadata_type", f"{prefix}.{key} must be a string.")


def _optional_url(payload: dict[str, Any], key: str, report: ValidationReport, prefix: str) -> None:
    _optional_string(payload, key, report, prefix)
    value = payload.get(key)
    if value and not value.startswith(("https://", "http://")):
        report.error("metadata_value", f"{prefix}.{key} must be an HTTP(S) URL.")


def _require_equal(
    payload: dict[str, Any], key: str, expected: str, report: ValidationReport
) -> None:
    if payload.get(key) != expected:
        report.error("metadata_value", f"{key} must be {expected!r}.", path="submission.json")


def _reject_unknown(
    payload: dict[str, Any], allowed: set[str], report: ValidationReport, path: str
) -> None:
    for key in sorted(set(payload) - allowed):
        report.error("unknown_metadata_field", f"Unknown field: {path}.{key}")


def _division(numerator: float, denominator: int) -> float:
    return _round(numerator / denominator) if denominator else 0.0


def _mean(values: list[float]) -> float:
    return _round(sum(values) / len(values)) if values else 0.0


def _round(value: float) -> float:
    return round(float(value), 4)


def _nullable_round(value: Any) -> float | None:
    return None if value is None else _round(float(value))


def _close(left: float, right: float, tolerance: float = FLOAT_TOLERANCE) -> bool:
    return abs(float(left) - float(right)) <= tolerance
