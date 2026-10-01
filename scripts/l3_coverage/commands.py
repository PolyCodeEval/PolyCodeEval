"""Build Docker install/test commands with coverage instrumentation."""

from __future__ import annotations

import re
from pathlib import Path

# Per docs/guides/task_a_oracle_validation.md (JavaScript table).
JEST_JS_PROJECTS = frozenset(
    {"babel-parser", "dayjs", "jest-core", "login-registration", "pug", "node-cron"},
)
NYC_JS_PROJECTS = frozenset({"got", "ejs"})
NO_COVERAGE_JS = frozenset({"nanoid", "minimist", "mitt"})


def _gradle_insert_jacoco_report(test: str) -> str:
    """Run jacocoTestReport after unit test task(s), before any trailing ``-x`` flags."""
    stripped = test.rstrip()
    idx = stripped.find(" -x")
    if idx != -1:
        head = stripped[:idx].rstrip()
        tail = stripped[idx:].lstrip()
        return f"{head} jacocoTestReport {tail}"
    return f"{stripped} jacocoTestReport"


def _maven_augment_test_command(test: str) -> str:
    """Append jacoco:report; write XML under /workspace/coverage_out for reliable host discovery."""
    t = test.rstrip()
    out_dir = "-Djacoco.outputDirectory=/workspace/coverage_out"
    fi = "-Dmaven.test.failure.ignore=true"
    if fi not in t:
        t = re.sub(r"\bmvn(\s+)", rf"mvn {fi}\1", t, count=1)
        t = re.sub(r"\bmvnw(\s+)", rf"mvnw {fi}\1", t, count=1)
    if "jacoco:report" in t:
        if "jacoco.outputDirectory=/workspace/coverage_out" in t:
            return t
        return re.sub(
            r"\bjacoco:report\b",
            f"{out_dir} jacoco:report",
            t,
            count=1,
        )
    return f"{t} {out_dir} jacoco:report"


def augment_for_coverage(
    *,
    language: str,
    project_name: str,
    install_command: str,
    test_command: str,
    project_dir: Path,
) -> tuple[str, str] | None:
    """Return (install, test) augmented for coverage, or None to skip Docker (all unknown)."""
    lang = language.lower()
    if lang == "cpp":
        return None
    if lang == "typescript":
        lang = "javascript"

    install = install_command.strip()
    test = test_command.strip()

    if lang == "go":
        new_test = re.sub(
            r"\bgo\s+test\b",
            "go test -coverprofile=/workspace/coverage_out/cover.out",
            test,
            count=1,
        )
        if new_test == test:
            return None
        return install, new_test

    if lang == "python":
        cov = "pip install -q pytest-cov"
        if install:
            new_install = f"{install} && {cov}"
        else:
            new_install = cov
        if "pytest" not in test and "py.test" not in test:
            return None
        suffix = " --cov=src --cov-report=json:/workspace/coverage_out/coverage.json"
        if "--cov=" in test:
            new_test = test
        else:
            new_test = test + suffix
        return new_install, new_test

    if lang == "java":
        if "mvn" in test or "mvnw" in test:
            return install, _maven_augment_test_command(test)
        if "gradle" in test or "gradlew" in test:
            if "jacocoTestReport" in test:
                return install, test
            return install, _gradle_insert_jacoco_report(test)
        return None

    if lang == "javascript":
        if project_name in NO_COVERAGE_JS:
            return None
        if project_name in JEST_JS_PROJECTS or "jest" in test:
            return install, _augment_jest(test)
        if project_name in NYC_JS_PROJECTS or "nyc" in test.lower():
            return install, _augment_nyc(test)
        if "mocha" in test.lower():
            return install, _augment_nyc(test)
        if "npm test" in test:
            return install, _augment_jest(test)
        return None

    return None


def _jest_coverage_suffix() -> str:
    return " --coverage --coverageReporters=json-summary --coverageDirectory=/workspace/coverage_out"


def _strip_jest_coverage_off(test: str) -> str:
    """Remove flags that disable coverage so we can re-instrument."""
    t = test
    t = t.replace("--coverage=false", "")
    t = re.sub(r"\s*--no-coverage\b", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def _augment_jest(test: str) -> str:
    suffix = _jest_coverage_suffix()
    if "--coverageDirectory=/workspace/coverage_out" in test:
        return test

    t = _strip_jest_coverage_off(test)

    if "npm test" in t:
        return t.replace(
            "npm test",
            "npm test -- --coverage --coverageReporters=json-summary "
            "--coverageDirectory=/workspace/coverage_out",
            1,
        )
    if "npx jest" in t:
        return t.replace(
            "npx jest",
            "npx jest --coverage --coverageReporters=json-summary "
            "--coverageDirectory=/workspace/coverage_out",
            1,
        )
    if ".bin/jest" in t:
        return t + suffix
    if re.search(r"\bjest\b", t, flags=re.IGNORECASE):
        return t + suffix
    return t


def _augment_nyc(test: str) -> str:
    if "nyc" in test:
        if "--report-dir=/workspace/coverage_out" in test:
            return test
        return test.replace(
            "nyc",
            "nyc --reporter=json-summary --report-dir=/workspace/coverage_out",
            1,
        )
    if "npm test" in test:
        return test.replace(
            "npm test",
            "nyc --reporter=json-summary --report-dir=/workspace/coverage_out npm test",
            1,
        )
    return f"nyc --reporter=json-summary --report-dir=/workspace/coverage_out {test}"
