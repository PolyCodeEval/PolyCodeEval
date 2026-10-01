"""Build Docker install/test commands with coverage instrumentation."""

from __future__ import annotations

import re
from pathlib import Path

# Per docs/guides/task_a_oracle_validation.md (JavaScript table).
JEST_JS_PROJECTS = frozenset(
    {"babel-parser", "dayjs", "jest-core", "login-registration", "pug", "node-cron"},
)
NYC_JS_PROJECTS: frozenset[str] = frozenset()
# nanoid uses node:test (wrapped with c8), minimist uses tape (wrapped with nyc),
# mitt uses mocha (handled by _augment_nyc). All are now supported.
NO_COVERAGE_JS: frozenset[str] = frozenset()


def _gradle_insert_jacoco_report(test: str) -> str:
    """Run clean + jacocoTestReport after unit test task(s), before any trailing ``-x`` flags.

    Adding 'clean' ensures tests re-run even if Gradle's build cache has stale results
    from a previous run (the src/ directory is volume-mounted and persists between runs).
    """
    stripped = test.rstrip()
    # Insert 'clean' before the test tasks to invalidate Gradle's build cache
    if not stripped.startswith("cd "):
        stripped = f"cd src && {stripped}" if "gradle" in stripped else stripped
    # Add clean before gradle tasks
    stripped = re.sub(r'\b(gradle\w*)\b', r'\1 clean', stripped, count=1)
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


def _augment_cpp(install: str, test: str, extra_excludes: list[str] | None = None) -> tuple[str, str] | None:
    """Add --coverage compilation flags and lcov collection to C++ projects."""
    base_excl = "--exclude '*/third_party/*' --exclude '*/googletest/*' --exclude '*/googlemock/*'"
    extra_excl = "".join(f" --exclude '{e}'" for e in (extra_excludes or []))
    all_excl = base_excl + extra_excl
    lcov_collect = (
        " && mkdir -p /workspace/coverage_out"
        f" && lcov --capture --directory /workspace --output-file /workspace/coverage_out/lcov.info"
        f" --no-external --gcov-tool gcov-12 --ignore-errors gcov,source"
        f" {all_excl} 2>/dev/null"
        f" || lcov --capture --directory /workspace --output-file /workspace/coverage_out/lcov.info"
        f" --no-external --gcov-tool gcov-12"
        f" {all_excl} 2>/dev/null"
        " || true"
    )
    # Install lcov
    lcov_install = "apt-get update -qq && apt-get install -y --no-install-recommends lcov"
    new_install = f"{install} && {lcov_install}" if install else lcov_install

    # cmake projects: inject coverage flags into cmake configure step
    if "cmake" in test:
        new_test = re.sub(
            r"\bcmake\b([^-\n]*)-B\b",
            r'cmake\1-DCMAKE_CXX_FLAGS="--coverage" -DCMAKE_C_FLAGS="--coverage"'
            r' -DCMAKE_EXE_LINKER_FLAGS="--coverage" -B',
            test,
            count=1,
        )
        if new_test == test:
            # fallback: append flags before -B
            new_test = test.replace("cmake -B", 'cmake -DCMAKE_CXX_FLAGS="--coverage" -DCMAKE_C_FLAGS="--coverage" -DCMAKE_EXE_LINKER_FLAGS="--coverage" -B', 1)
        cmake_lcov = (
            " && mkdir -p /workspace/coverage_out"
            f" && lcov --capture --directory /workspace --output-file /workspace/coverage_out/lcov.info"
            f" --no-external --gcov-tool gcov-12 --ignore-errors gcov,source"
            f" {all_excl} 2>/dev/null"
            f" || lcov --capture --directory /workspace --output-file /workspace/coverage_out/lcov.info"
            f" --no-external --gcov-tool gcov-12"
            f" {all_excl} 2>/dev/null"
            " || true"
        )
        return new_install, new_test + cmake_lcov

    # Makefile projects: run clean first to avoid stale object files from previous runs
    if "make" in test and "cmake" not in test:
        m = re.search(r'(make\s+-C\s+\S+\s+-f\s+\S+)', test)
        if m:
            clean_cmd = m.group(1) + " clean"
            new_test = f"{clean_cmd} 2>/dev/null; {test}"
        else:
            new_test = test
        return new_install, new_test + lcov_collect

    # Direct g++ compilation: append --coverage flag
    if "g++" in test or "gcc" in test:
        new_test = re.sub(
            r'(?<!\S)(g\+\+|gcc)(?=\s)',
            r'\1 --coverage',
            test,
            count=0,
        )
        return new_install, new_test + lcov_collect

    return None


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
    if lang == "typescript":
        lang = "javascript"

    install = install_command.strip()
    test = test_command.strip()

    if lang == "cpp":
        import json as _json
        cfg_path = project_dir / "config.json"
        extra_excludes: list[str] = []
        if cfg_path.is_file():
            try:
                extra_excludes = _json.loads(cfg_path.read_text()).get("coverage_exclude", [])
            except Exception:
                pass
        return _augment_cpp(install, test, extra_excludes)

    if lang == "go":
        new_test = re.sub(
            r"\bgo\s+test\b",
            "go test -coverprofile=/workspace/coverage_out/cover.out -coverpkg=./...",
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
            # mitt compiles TypeScript to dist/; instrument the compiled output
            if project_name == "mitt":
                return install, _augment_c8(test, include="dist/mitt.js")
            return install, _augment_c8(test)
        # AVA runner: use c8
        if "ava" in test.lower():
            return install, _augment_c8(test)
        # tape runner: minimist's npm script uses nyc internally but old version
        # doesn't support env var redirect; use local binaries directly
        if "tape" in test.lower() or project_name == "minimist":
            m = re.match(r"^(cd\s+\S+\s*&&\s*)(.*)", test)
            prefix = m.group(1) if m else ""
            return (
                install,
                f"{prefix}./node_modules/.bin/nyc --reporter=json-summary "
                f"--report-dir=/workspace/coverage_out "
                f"--exclude='test/**' --exclude='__blackbox__/**' --exclude='coverage/**' "
                f"./node_modules/.bin/tape 'test/**/*.js'",
            )
        # node:test (bnt) runner: wrap with c8
        if re.search(r"\bnode\b", test) and "test" in test:
            return install, _augment_c8(test)
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

    if "npm test" in t or "npm run test" in t:
        replacement = (
            "npm test -- --coverage --coverageReporters=json-summary "
            "--coverageDirectory=/workspace/coverage_out"
        )
        if "npm run test" in t:
            return t.replace(
                "npm run test",
                "npm run test -- --coverage --coverageReporters=json-summary "
                "--coverageDirectory=/workspace/coverage_out",
                1,
            )
        return t.replace("npm test", replacement, 1)
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


def _augment_c8(test: str, *, include: str | None = None) -> str:
    """Wrap a command with c8 for coverage."""
    include_flag = f" --include={include!r}" if include else ""
    exclude_flags = " --exclude='test/**' --exclude='__blackbox__/**' --exclude='**/*.test.*' --exclude='**/*.spec.*'"
    c8_cmd = "npx c8@10"
    if "c8" in test:
        if "--reports-dir=/workspace/coverage_out" in test:
            return test
        return test.replace("c8", f"c8 --reporter=json-summary --reports-dir=/workspace/coverage_out{include_flag}{exclude_flags}", 1)
    # If test starts with a cd, insert c8 after the cd
    m = re.match(r"^(cd\s+\S+\s*&&\s*)(.*)", test)
    if m:
        return f"{m.group(1)}{c8_cmd} --reporter=json-summary --reports-dir=/workspace/coverage_out{include_flag}{exclude_flags} {m.group(2)}"
    return f"{c8_cmd} --reporter=json-summary --reports-dir=/workspace/coverage_out{include_flag}{exclude_flags} {test}"


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
    # If test starts with a cd, insert nyc after the cd
    m = re.match(r"^(cd\s+\S+\s*&&\s*)(.*)", test)
    if m:
        return f"{m.group(1)}nyc --reporter=json-summary --report-dir=/workspace/coverage_out {m.group(2)}"
    return f"nyc --reporter=json-summary --report-dir=/workspace/coverage_out {test}"
