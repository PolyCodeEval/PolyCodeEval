"""Test output parser — extracts per-test-case pass/fail from stdout."""

from __future__ import annotations

import re

# Patterns that indicate a build/compile step failed before any tests ran
_COMPILE_FAIL_PATTERNS = [
    r"error:.*no matching function",
    r"error:.*cannot find symbol",
    r"error:.*package .* does not exist",
    r"error:.*undefined.*identifier",
    r"BUILD FAILED",
    r"Compilation failed",
    r"compilation terminated",
    r"fatal error:",
    r"SyntaxError:",
    r"ModuleNotFoundError:",
    r"ImportError:",
    r"cannot compile",
    r"\[ERROR\].*COMPILATION ERROR",
    r"COMPILATION ERROR",
    r"npm ERR! code",
    r"go: no module",
    r"malformed go\.(mod|sum)",
]

_COMPILE_FAIL_RE = re.compile("|".join(_COMPILE_FAIL_PATTERNS), re.IGNORECASE)


def infer_compile_status(combined_output: str, exit_code: int, test_total: int) -> str:
    """Return 'ok', 'compile_error', or 'runtime_error'.

    - 'ok': tests ran (total > 0) or exit_code == 0
    - 'compile_error': build/install failed before any test ran
    - 'runtime_error': tests ran but process crashed (exit!=0, total==0, no compile error)
    """
    if exit_code == 0:
        return "ok"
    if test_total > 0:
        return "ok"   # tests ran; failures are test failures, not compile errors
    if _COMPILE_FAIL_RE.search(combined_output):
        return "compile_error"
    return "runtime_error"


def parse_test_results(stdout: str, language: str) -> dict:
    """Parse test runner output and return per-test-case results.

    Returns:
        {
            "tests": [{"name": "TestFoo", "passed": True}, ...],
            "passed": 5,
            "failed": 1,
            "total": 6,
        }
    """
    parsers = {
        "go": _parse_go,
        "python": _parse_python,
        "javascript": _parse_javascript,
        "java": _parse_java,
        "cpp": _parse_cpp,
    }
    parser = parsers.get(language, _parse_generic)
    tests = parser(stdout)
    passed = sum(1 for t in tests if t["passed"])
    return {
        "tests": tests,
        "passed": passed,
        "failed": len(tests) - passed,
        "total": len(tests),
    }


def _parse_go(stdout: str) -> list[dict]:
    """Parse `go test -v` output: '--- PASS: TestName (0.00s)' / '--- FAIL: TestName (0.00s)'"""
    results = []
    for m in re.finditer(r"--- (PASS|FAIL): (\S+)", stdout):
        results.append({"name": m.group(2), "passed": m.group(1) == "PASS"})
    return results


def _parse_python(stdout: str) -> list[dict]:
    """Parse pytest -v output: 'test_file.py::test_name PASSED' / 'FAILED'"""
    results = []
    for m in re.finditer(r"(\S+::\S+)\s+(PASSED|FAILED)", stdout):
        results.append({"name": m.group(1), "passed": m.group(2) == "PASSED"})
    if not results:
        # Fallback: pytest short summary '1 passed, 2 failed'
        m = re.search(r"(\d+) passed", stdout)
        passed = int(m.group(1)) if m else 0
        m = re.search(r"(\d+) failed", stdout)
        failed = int(m.group(1)) if m else 0
        if passed or failed:
            results = (
                [{"name": f"test_{i}", "passed": True} for i in range(passed)]
                + [{"name": f"failed_{i}", "passed": False} for i in range(failed)]
            )
    return results


def _parse_javascript(stdout: str) -> list[dict]:
    """Parse Jest/Mocha/TAP output: '✓ test name' / '✗ test name' or 'PASS'/'FAIL' lines."""
    results = []
    # Jest verbose: '  ✓ test name (5ms)' or '  ✕ test name'
    for m in re.finditer(r"[✓✔]\s+(.+?)(?:\s+\(\d+\s*m?s\))?\s*$", stdout, re.MULTILINE):
        results.append({"name": m.group(1).strip(), "passed": True})
    for m in re.finditer(r"[✕✗×]\s+(.+?)(?:\s+\(\d+\s*m?s\))?\s*$", stdout, re.MULTILINE):
        results.append({"name": m.group(1).strip(), "passed": False})
    if not results:
        # TAP format: 'ok 1 - test name' or 'ok 1 test name' / 'not ok 2 ...'
        for m in re.finditer(r"^(not )?ok \d+(?:\s+-\s+|\s+)(.+)$", stdout, re.MULTILINE):
            results.append({"name": m.group(2).strip(), "passed": m.group(1) is None})
    if not results:
        # Jest summary: 'Tests:  1 failed, 293 passed, 294 total'
        m_line = re.search(r"^Tests:\s+(.*?)$", stdout, re.MULTILINE)
        if m_line:
            line = m_line.group(1)
            mp = re.search(r"(\d+)\s+passed", line)
            mf = re.search(r"(\d+)\s+failed", line)
            passed = int(mp.group(1)) if mp else 0
            failed = int(mf.group(1)) if mf else 0
            results = (
                [{"name": f"test_{i}", "passed": True} for i in range(passed)]
                + [{"name": f"failed_{i}", "passed": False} for i in range(failed)]
            )
    if not results:
        # Mocha: 'N passing' / 'N failing'
        m = re.search(r"(\d+) passing", stdout)
        passed = int(m.group(1)) if m else 0
        m = re.search(r"(\d+) failing", stdout)
        failed = int(m.group(1)) if m else 0
        if passed or failed:
            results = (
                [{"name": f"test_{i}", "passed": True} for i in range(passed)]
                + [{"name": f"failed_{i}", "passed": False} for i in range(failed)]
            )
    return results


def _parse_java(stdout: str) -> list[dict]:
    """Parse JUnit/Maven/Gradle output."""
    results = []
    # Gradle testLogging: 'ClassName > methodName PASSED/FAILED/SKIPPED'
    for m in re.finditer(r"^\S.*> \S+ (PASSED|FAILED|SKIPPED)$", stdout, re.MULTILINE):
        if m.group(1) != "SKIPPED":
            results.append({"name": m.group(0).split(">")[1].strip().split()[0], "passed": m.group(1) == "PASSED"})
    if not results:
        # Maven surefire: 'Tests run: 5, Failures: 1, Errors: 0'
        for m in re.finditer(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)", stdout):
            total = int(m.group(1))
            failures = int(m.group(2)) + int(m.group(3))
            passed = total - failures
            results += (
                [{"name": f"test_{i}", "passed": True} for i in range(passed)]
                + [{"name": f"failed_{i}", "passed": False} for i in range(failures)]
            )
    return results


def _parse_cpp(stdout: str) -> list[dict]:
    """Parse Google Test output: '[  PASSED  ] N tests' / '[  FAILED  ] TestName'"""
    results = []
    # Individual test results: '[ OK ] TestSuite.TestName (0 ms)'
    for m in re.finditer(r"\[\s+OK\s+\]\s+(\S+)", stdout):
        results.append({"name": m.group(1), "passed": True})
    for m in re.finditer(r"\[\s+FAILED\s+\]\s+(\S+?)(?:\s*\(|,|$)", stdout):
        name = m.group(1)
        if not re.match(r"^\d+\s+test", name):
            results.append({"name": name, "passed": False})

    # If the process crashed mid-run (e.g. SIGSEGV), GTest never prints the
    # final summary.  We can still recover the declared total from the header
    # line "[==========] Running N tests from M test suites." and mark every
    # test that was declared but not reported as failed.
    if results:
        header = re.search(r"\[=+\]\s+Running\s+(\d+)\s+test", stdout)
        if header:
            declared_total = int(header.group(1))
            seen = len(results)
            missing = declared_total - seen
            if missing > 0:
                for i in range(missing):
                    results.append({"name": f"crashed_test_{i}", "passed": False})
    if not results:
        # jsoncpp jsontest format: 'Testing Suite/name: OK' / 'FAILED'
        for m in re.finditer(r"^Testing\s+(\S+):\s+(OK|FAILED)\s*$", stdout, re.MULTILINE):
            results.append({"name": m.group(1), "passed": m.group(2) == "OK"})
    if not results:
        # ctest format: 'Start N: testname' + 'N/N Test #N: testname ... Passed/Failed'
        for m in re.finditer(r"Test #\d+:\s+(\S+)\s+\.+\s+(Passed|Failed)", stdout):
            results.append({"name": m.group(1), "passed": m.group(2) == "Passed"})
    if not results:
        # ctest summary: '100% tests passed, 0 tests failed out of N'
        m = re.search(r"(\d+)%\s+tests passed.*?out of (\d+)", stdout)
        if m:
            total = int(m.group(2))
            pct = int(m.group(1))
            passed = round(total * pct / 100)
            failed = total - passed
            results = (
                [{"name": f"test_{i}", "passed": True} for i in range(passed)]
                + [{"name": f"failed_{i}", "passed": False} for i in range(failed)]
            )
    if not results:
        # doctest format: 'test cases: N | M passed | K failed'
        m = re.search(r"test cases:\s+(\d+)\s+\|\s+(\d+)\s+passed", stdout)
        if m:
            total = int(m.group(1))
            passed = int(m.group(2))
            # 'failed as expected' are not real failures
            real_failed_m = re.search(r"\|\s+(\d+)\s+failed(?!\s+as)", stdout)
            failed = int(real_failed_m.group(1)) if real_failed_m else 0
            results = (
                [{"name": f"test_{i}", "passed": True} for i in range(passed)]
                + [{"name": f"failed_{i}", "passed": False} for i in range(failed)]
            )
    if not results:
        # Summary line: 'N tests from M test suites ran'
        m = re.search(r"\[\s+PASSED\s+\]\s+(\d+)\s+test", stdout)
        passed = int(m.group(1)) if m else 0
        m = re.search(r"\[\s+FAILED\s+\]\s+(\d+)\s+test", stdout)
        failed = int(m.group(1)) if m else 0
        if passed or failed:
            results = (
                [{"name": f"test_{i}", "passed": True} for i in range(passed)]
                + [{"name": f"failed_{i}", "passed": False} for i in range(failed)]
            )
    return results


def _parse_generic(stdout: str) -> list[dict]:
    """Fallback: try all parsers, return first non-empty result."""
    for parser in [_parse_go, _parse_python, _parse_javascript, _parse_java, _parse_cpp]:
        results = parser(stdout)
        if results:
            return results
    return []
