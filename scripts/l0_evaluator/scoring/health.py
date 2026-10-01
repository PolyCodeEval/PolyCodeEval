"""Health scoring for L0 tasks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_DOCKER_DIR = str(Path(__file__).resolve().parents[3] / "docker")
if _DOCKER_DIR not in sys.path:
    sys.path.insert(0, _DOCKER_DIR)

from runner_lib import docker_command  # noqa: E402
from .repo_snapshot import build_file_tree, list_repo_files


def _health_script(language: str) -> str:
    flake8_cmd = "flake8 . > /tmp/flake8.out 2>/tmp/flake8.err; echo $? > /tmp/flake8.exit" if language == "python" else "true"
    gofmt_cmd = "gofmt -l . > /tmp/gofmt.out 2>/tmp/gofmt.err; echo $? > /tmp/gofmt.exit" if language == "go" else "true"
    govet_cmd = "go vet ./... > /tmp/govet.out 2>/tmp/govet.err; echo $? > /tmp/govet.exit" if language == "go" else "true"
    js_checks_cmd = (
        r"""python3 - <<'PY'
from pathlib import Path
import subprocess

eslint_bin = Path('./node_modules/.bin/eslint')
if eslint_bin.exists() and eslint_bin.is_file():
    proc = subprocess.run(
        [str(eslint_bin), '.'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    Path('/tmp/eslint.out').write_text(proc.stdout, encoding='utf-8')
    Path('/tmp/eslint.err').write_text(proc.stderr, encoding='utf-8')
    Path('/tmp/eslint.exit').write_text(str(proc.returncode), encoding='utf-8')
else:
    Path('/tmp/eslint.out').write_text('', encoding='utf-8')
    Path('/tmp/eslint.err').write_text('', encoding='utf-8')
    Path('/tmp/eslint.exit').write_text('0', encoding='utf-8')

issues = []
for path in list(Path('.').rglob('*.js'))[:50]:
    proc = subprocess.run(
        ['node', '--check', str(path)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    if proc.returncode != 0:
        issues.append(str(path))
Path('/tmp/nodecheck.out').write_text('\n'.join(issues), encoding='utf-8')
Path('/tmp/nodecheck.exit').write_text('0', encoding='utf-8')
PY"""
        if language == "javascript" else "true"
    )
    return f"""
set +e
cd /workspace/src
lizard -X . > /tmp/lizard.xml 2>/tmp/lizard.err
echo $? > /tmp/lizard.exit
{flake8_cmd}
{gofmt_cmd}
{govet_cmd}
{js_checks_cmd}
python3 - <<'PY'
from pathlib import Path
import json
import xml.etree.ElementTree as ET

TEXT_SUFFIXES = {{'.py','.go','.java','.js','.jsx','.ts','.tsx','.cpp','.cc','.c','.h','.hpp','.md','.txt','.json','.yml','.yaml','.toml','.xml','.html','.css','.vue','.sh'}}
IGNORED_DIR_NAMES = {{'.git', '.hg', '.svn', '.next', '.nuxt', '.pytest_cache', '.tox', '.venv', '__pycache__', 'build', 'coverage', 'dist', 'node_modules', 'vendor'}}

def read(path):
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''

def ignored(path):
    return any(part in IGNORED_DIR_NAMES for part in path.parts[:-1])

avg_ccn = 0.0
max_ccn = 0.0
functions_over_15 = 0
if Path('/tmp/lizard.xml').exists():
    try:
        root = ET.fromstring(read('/tmp/lizard.xml'))
        values = []
        for elem in root.iter():
            tag = elem.tag.lower()
            if tag.endswith('measure') and elem.attrib.get('type') == 'Function':
                ccn = elem.attrib.get('cyclomatic_complexity')
                if ccn is not None:
                    try:
                        values.append(float(ccn))
                    except ValueError:
                        pass
        if values:
            avg_ccn = sum(values) / len(values)
            max_ccn = max(values)
            functions_over_15 = sum(1 for value in values if value > 15)
    except ET.ParseError:
        pass

line_length = 0
trailing_ws = 0
for path in Path('.').rglob('*'):
    if not path.is_file():
        continue
    if ignored(path):
        continue
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in ('Makefile', 'Dockerfile'):
        continue
    text = read(path)
    for line in text.splitlines():
        if len(line) > 120:
            line_length += 1
        if line.rstrip() != line:
            trailing_ws += 1

def lines_count(path):
    p = Path(path)
    if not p.exists():
        return 0
    text = read(p)
    return sum(1 for line in text.splitlines() if line.strip())

language_specific = 0
tool_results = {{
    'lizard_exit': read('/tmp/lizard.exit').strip(),
    'flake8_exit': read('/tmp/flake8.exit').strip(),
    'gofmt_exit': read('/tmp/gofmt.exit').strip(),
    'govet_exit': read('/tmp/govet.exit').strip(),
    'eslint_exit': read('/tmp/eslint.exit').strip(),
    'nodecheck_exit': read('/tmp/nodecheck.exit').strip(),
}}
language_specific += lines_count('/tmp/flake8.out')
language_specific += lines_count('/tmp/gofmt.out')
language_specific += lines_count('/tmp/govet.out')
language_specific += lines_count('/tmp/eslint.out')
language_specific += lines_count('/tmp/nodecheck.out')

print('===HEALTH_JSON===')
print(json.dumps({{
    'avg_ccn': round(avg_ccn, 4),
    'max_ccn': round(max_ccn, 4),
    'functions_over_15': int(functions_over_15),
    'line_length_violations': int(line_length),
    'trailing_whitespace_violations': int(trailing_ws),
    'language_specific_issue_count': int(language_specific),
    'tool_results': tool_results,
}}, ensure_ascii=False))
print('===END_HEALTH_JSON===')
PY
exit 0
"""


def score_health(*, repo_root: Path, language: str, docker_image: str) -> tuple[float | None, dict]:
    script = _health_script(language)
    effective_image = "" if language == "javascript" else docker_image
    cmd = docker_command(repo_root.parent, script, language=language, docker_image=effective_image)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    stdout = proc.stdout or ""
    start = stdout.find("===HEALTH_JSON===")
    end = stdout.find("===END_HEALTH_JSON===")
    if start < 0 or end < 0:
        line_length = 0
        trailing = 0
        for path in list_repo_files(repo_root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                if len(line) > 120:
                    line_length += 1
                if line.rstrip() != line:
                    trailing += 1
        issue_count = line_length + trailing
        style_penalty = 0.0 if issue_count == 0 else 0.5 if issue_count <= 10 else 1.0 if issue_count <= 50 else 2.0
        score = round(max(0.0, min(5.0, 5.0 - style_penalty - 1.0)), 2)
        return score, {
            "status": "fallback",
            "avg_ccn": 0.0,
            "max_ccn": 0.0,
            "functions_over_15": 0,
            "line_length_violations": line_length,
            "trailing_whitespace_violations": trailing,
            "language_specific_issue_count": 0,
            "tool_results": {
                "raw_stdout_tail": stdout[-2000:],
                "raw_stderr_tail": (proc.stderr or "")[-1000:],
                "fallback_reason": "Static analysis container output was not parseable; heuristic health fallback used.",
            },
        }
    payload = stdout[start + len("===HEALTH_JSON==="):end].strip()
    data = json.loads(payload)

    complexity_penalty = 0.0
    avg_ccn = float(data.get("avg_ccn", 0.0))
    max_ccn = float(data.get("max_ccn", 0.0))
    if not (max_ccn <= 15 and avg_ccn <= 10):
        if max_ccn <= 20 and avg_ccn <= 15:
            complexity_penalty = 0.5
        elif max_ccn <= 30 and avg_ccn <= 20:
            complexity_penalty = 1.0
        else:
            complexity_penalty = 1.5

    issue_count = int(data.get("line_length_violations", 0)) + int(data.get("trailing_whitespace_violations", 0)) + int(data.get("language_specific_issue_count", 0))
    if issue_count == 0:
        style_penalty = 0.0
    elif issue_count <= 10:
        style_penalty = 0.5
    elif issue_count <= 50:
        style_penalty = 1.0
    else:
        style_penalty = 2.0

    tool_results = data.get("tool_results", {})
    fatal = False
    if language == "python" and tool_results.get("flake8_exit") not in {"", "0"}:
        fatal = True
    if language == "go" and tool_results.get("govet_exit") not in {"", "0"}:
        fatal = True

    score = 5.0 - complexity_penalty - style_penalty - (1.0 if fatal else 0.0)
    score = round(max(0.0, min(5.0, score)), 2)
    data["status"] = "ok"
    return score, data
