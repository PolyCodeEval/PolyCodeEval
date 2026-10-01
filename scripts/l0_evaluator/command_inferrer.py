"""CommandInferrer — uses an LLM to infer install and test commands from generated project files."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _load_env():
    """Load .env file from project root (no external dependency)."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_env()


# --- Prompts ---

SYSTEM_PROMPT = """\
You are a DevOps expert. Given project files and workspace layout, infer the \
shell commands to install dependencies and run the test suite.

Workspace layout inside Docker:
  /workspace/          <- working directory (commands execute here)
  /workspace/src/      <- project source code
  /workspace/tests/    <- test files (may exist outside src/)

Rules:
- If tests/ exists at workspace root, run tests from /workspace, not src/
- Python: "pip install -r src/requirements.txt" then "PYTHONPATH=src pytest tests/"
- Go: "cd src && go test ./..." (add GO111MODULE=off if no go.mod)
- Java/Gradle: install gradle via apt-get if wrapper jar is missing
- Java/Maven: install maven via apt-get if mvn not found
- C++: check for Makefile/makefile_test before assuming cmake

Return EXACTLY two lines, no explanation:
Line 1: install command (or empty)
Line 2: test command
"""

RETRY_SYSTEM_PROMPT = """\
You are a DevOps expert. A previous attempt to run tests failed.
Given the error output, fix the commands.

Same workspace layout: /workspace/ (cwd), /workspace/src/ (source), /workspace/tests/ (tests).

Return EXACTLY two lines, no explanation:
Line 1: install command (or empty)
Line 2: test command
"""

# Config files to read from src/ for context
_CONFIG_FILES = [
    "go.mod", "go.sum",
    "package.json", "package-lock.json",
    "pom.xml", "build.gradle", "build.gradle.kts",
    "CMakeLists.txt", "Makefile", "makefile_test", "meson.build",
    "requirements.txt", "setup.py", "setup.cfg", "pyproject.toml",
    "Cargo.toml", "README.md",
]

_MAX_FILE_CHARS = 2000


# --- Public API ---

def infer_commands(
    tmp_dir: Path,
    docker_image: str,
    language: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    config_hint: dict | None = None,
) -> tuple[str, str]:
    """Infer install/test commands for a workspace. Returns (install_cmd, test_cmd)."""
    provider, model = _resolve_provider_model(provider, model)
    src_dir = tmp_dir / "src"

    context = _build_context(tmp_dir, src_dir, docker_image, language, config_hint)
    if not context:
        return _fallback(language)

    try:
        response = _call_llm(provider, model, SYSTEM_PROMPT, context)
        install, test = _parse_response(response, language)
    except Exception:
        install, test = _fallback(language)

    return _post_process(install, test, src_dir, language)


def retry_infer_commands(
    tmp_dir: Path,
    docker_image: str,
    language: str,
    prev_install: str,
    prev_test: str,
    stderr: str,
    stdout: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    config_hint: dict | None = None,
) -> tuple[str, str]:
    """Re-infer commands after failure, feeding error output to the LLM."""
    provider, model = _resolve_provider_model(provider, model)
    src_dir = tmp_dir / "src"

    error_output = (stderr or stdout or "")[-2000:]
    context = _build_retry_context(
        tmp_dir, src_dir, docker_image, language,
        prev_install, prev_test, error_output, config_hint,
    )

    try:
        response = _call_llm(provider, model, RETRY_SYSTEM_PROMPT, context)
        install, test = _parse_response(response, language)
    except Exception:
        return prev_install, prev_test

    return _post_process(install, test, src_dir, language)


# --- Internal helpers ---

def _resolve_provider_model(provider: str | None, model: str | None) -> tuple[str, str]:
    if provider is None:
        provider = os.environ.get("LLM_PROVIDER", "openai")
    if model is None:
        model = os.environ.get(
            "OPENAI_MODEL" if provider == "openai" else "ANTHROPIC_MODEL",
            "gpt-4o-mini",
        )
    return provider, model


def _build_context(
    tmp_dir: Path, src_dir: Path, docker_image: str, language: str,
    config_hint: dict | None,
) -> str:
    file_listing = _gather_config_files(src_dir)
    workspace_tree = _gather_workspace_tree(tmp_dir)
    if not file_listing and not workspace_tree:
        return ""

    parts = [f"Language: {language}", f"Docker image: {docker_image}", ""]
    if config_hint:
        parts.append(f"Reference config.json:\n```json\n{json.dumps(config_hint, indent=2)}\n```\n")
    parts.append(f"Project files:\n\n{file_listing}")
    if workspace_tree:
        parts.append(workspace_tree)
    return "\n".join(parts)


def _build_retry_context(
    tmp_dir: Path, src_dir: Path, docker_image: str, language: str,
    prev_install: str, prev_test: str, error_output: str,
    config_hint: dict | None,
) -> str:
    file_listing = _gather_config_files(src_dir)
    workspace_tree = _gather_workspace_tree(tmp_dir)

    parts = [
        f"Language: {language}",
        f"Docker image: {docker_image}",
        "",
        f"Previous install command: {prev_install or '(empty)'}",
        f"Previous test command: {prev_test}",
        "",
        f"Error output:\n```\n{error_output}\n```",
        "",
    ]
    if config_hint:
        parts.append(f"Reference config.json:\n```json\n{json.dumps(config_hint, indent=2)}\n```\n")
    parts.append(f"Project files:\n\n{file_listing}")
    if workspace_tree:
        parts.append(workspace_tree)
    return "\n".join(parts)


def _gather_workspace_tree(tmp_dir: Path) -> str:
    all_files = sorted(str(p.relative_to(tmp_dir)) for p in tmp_dir.rglob("*") if p.is_file())
    if not all_files:
        return ""
    return "--- workspace file tree (first 80) ---\n" + "\n".join(all_files[:80])


def _gather_config_files(src_dir: Path) -> str:
    parts: list[str] = []
    for name in _CONFIG_FILES:
        path = src_dir / name
        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")[:_MAX_FILE_CHARS]
            parts.append(f"--- {name} ---\n{content}")
    all_files = sorted(str(p.relative_to(src_dir)) for p in src_dir.rglob("*") if p.is_file())
    if all_files:
        parts.append("--- src/ file tree (first 50) ---\n" + "\n".join(all_files[:50]))
    return "\n\n".join(parts)


def _call_llm(provider: str, model: str, system_prompt: str, user_prompt: str) -> str:
    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=256,
            temperature=0,
        )
        return resp.choices[0].message.content.strip()
    elif provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        )
        msg = client.messages.create(
            model=model,
            max_tokens=256,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text.strip()
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def _parse_response(response: str, language: str) -> tuple[str, str]:
    lines = []
    for line in response.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        lines.append(line)
    if len(lines) >= 2:
        return lines[0], lines[1]
    elif len(lines) == 1:
        return "", lines[0]
    return _fallback(language)


def _fallback(language: str) -> tuple[str, str]:
    fallbacks = {
        "go": ("", "cd src && go test ./..."),
        "python": ("pip install -r src/requirements.txt", "PYTHONPATH=src pytest tests/"),
        "javascript": ("cd src && npm install", "cd src && npm test"),
        "java": ("apt-get update && apt-get install -y maven", "cd src && mvn test"),
        "cpp": ("cd src && make", "cd src && make test"),
    }
    return fallbacks.get(language, ("", "echo 'no test command'"))


def _post_process(install: str, test: str, src_dir: Path, language: str) -> tuple[str, str]:
    if language == "go" and "GO111MODULE=off" not in test:
        if not (src_dir / "go.mod").is_file():
            test = test.replace("go test", "GO111MODULE=off go test")
    return install, test
