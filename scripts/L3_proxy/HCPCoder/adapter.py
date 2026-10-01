"""Bridge PolyCodeEval L3 tasks to HCP-Coder pipeline (host-side)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]
_HCPCODER_ROOT = _REPO_ROOT.parent / "L3works" / "HCP-Coder"
_DEBUG_ROOT = _REPO_ROOT / "results" / "l3_hcpcoder_debug"
_WORKSPACE_ROOT = _REPO_ROOT / "output" / "hcpcoder_workspaces"
_CONTAINER_NAME = "hcpcoder-worker"
_INFERENCE_SCRIPT_HOST = _THIS_FILE.parent / "hcpcoder_inference.py"
_INFERENCE_SCRIPT_CONTAINER = "/workspace/hcpcoder_inference.py"


class HCPCoderError(RuntimeError):
    pass


def _parse_model_spec(model_spec: str) -> tuple[str, str]:
    if model_spec.startswith("hcpcoder-openai/"):
        return "openai", model_spec.removeprefix("hcpcoder-openai/")
    if model_spec.startswith("hcpcoder-anthropic/"):
        return "anthropic", model_spec.removeprefix("hcpcoder-anthropic/")
    raise HCPCoderError(
        f"Unsupported spec: {model_spec!r}. "
        "Use hcpcoder-openai/<model> or hcpcoder-anthropic/<model>."
    )


def _ensure_docker_container() -> None:
    check = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={_CONTAINER_NAME}"],
        capture_output=True, text=True,
    )
    if check.stdout.strip():
        return

    print(f"Starting HCP-Coder Docker container ({_CONTAINER_NAME})...")

    has_image = subprocess.run(
        ["docker", "images", "-q", "hcpcoder:latest"],
        capture_output=True, text=True,
    ).stdout.strip()

    if not has_image:
        dockerfile = _THIS_FILE.parent / "Dockerfile"
        if not dockerfile.exists():
            raise HCPCoderError(f"Dockerfile not found: {dockerfile}")
        print("Building Docker image hcpcoder:latest...")

        import sys as _sys
        build_env = os.environ.copy()
        if _sys.platform == "darwin":
            proxy = "http://host.docker.internal:7897"
            build_env["HTTP_PROXY"] = "http://127.0.0.1:7897"
            build_env["HTTPS_PROXY"] = "http://127.0.0.1:7897"
        else:
            proxy = "http://172.19.135.130:5000"

        ret = subprocess.run([
            "docker", "build",
            "--build-arg", f"HTTP_PROXY={proxy}",
            "--build-arg", f"HTTPS_PROXY={proxy}",
            "-f", str(dockerfile),
            "-t", "hcpcoder:latest",
            str(_THIS_FILE.parent),
        ], cwd=str(_REPO_ROOT), env=build_env)
        if ret.returncode != 0:
            raise HCPCoderError("Docker image build failed")

    _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    ret = subprocess.run([
        "docker", "run", "-d",
        "--name", _CONTAINER_NAME,
        "-v", f"{_WORKSPACE_ROOT}:{_WORKSPACE_ROOT}",
        "-v", f"{_HCPCODER_ROOT}:/workspace/L3works/HCP-Coder:ro",
        "-v", f"{_INFERENCE_SCRIPT_HOST}:{_INFERENCE_SCRIPT_CONTAINER}:ro",
        "hcpcoder:latest",
        "tail", "-f", "/dev/null",
    ], capture_output=True, text=True)

    if ret.returncode != 0:
        raise HCPCoderError(f"Container start failed: {ret.stderr}")

    print(f"Container started: {_CONTAINER_NAME}")
    print(f"Stop: docker stop {_CONTAINER_NAME} && docker rm {_CONTAINER_NAME}\n")


def _run_in_docker(payload: dict) -> dict:
    _ensure_docker_container()

    env_args: list[str] = []
    for var in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY",
                "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        if os.environ.get(var):
            env_args += ["-e", var]

    cmd = [
        "docker", "exec", "-i",
        *env_args,
        _CONTAINER_NAME,
        "python", _INFERENCE_SCRIPT_CONTAINER,
    ]

    result = subprocess.run(
        cmd,
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True, text=True,
        env=os.environ,
    )

    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-80:])
        raise HCPCoderError(
            f"Docker inference failed (exit {result.returncode}):\n{stderr_tail}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise HCPCoderError(
            f"Docker output parse error: {e}\nstdout: {result.stdout[:500]}"
        )


def generate_function_body(task_dir: Path, model_spec: str) -> str:
    if not _HCPCODER_ROOT.is_dir():
        raise HCPCoderError(f"HCP-Coder source not found: {_HCPCODER_ROOT}")

    provider, model_name = _parse_model_spec(model_spec)
    language = task_dir.parents[2].name

    hcpcoder_str = str(_HCPCODER_ROOT)
    if hcpcoder_str not in sys.path:
        sys.path.insert(0, hcpcoder_str)
    from l3_loader import load_l3_example  # type: ignore

    payload_data, workspace_dir = load_l3_example(task_dir)

    try:
        payload = {
            **payload_data,
            "provider": provider,
            "model_name": model_name,
        }
        result = _run_in_docker(payload)
        raw_completion = result.get("completion", "")
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        embedding_tokens = result.get("embedding_tokens", 0)
        debug_info = result.get("debug", {})
    finally:
        shutil.rmtree(workspace_dir, ignore_errors=True)

    debug_dir = _DEBUG_ROOT / task_dir.parents[2].name / task_dir.parents[1].name / task_dir.name
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "raw_completion.txt").write_text(raw_completion, encoding="utf-8")
    (debug_dir / "usage_round1.json").write_text(
        json.dumps({
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "embedding_tokens": embedding_tokens,
            "total_tokens": input_tokens + output_tokens + embedding_tokens,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if debug_info.get("prompt_text"):
        (debug_dir / "final_prompt.txt").write_text(debug_info["prompt_text"], encoding="utf-8")
    if debug_info.get("cross_file_files"):
        (debug_dir / "cross_file_files.json").write_text(
            json.dumps(debug_info["cross_file_files"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    task_json = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    stub_info = task_json["stub_info"]
    cleaned = _fallback_clean_completion(raw_completion, stub_info.get("lang", ""))
    normalized = _normalize_function_body(task_dir, cleaned, stub_info)
    (debug_dir / "cleaned_completion.txt").write_text(normalized, encoding="utf-8")

    if not normalized:
        raise HCPCoderError("HCP-Coder generated empty function body")
    return normalized


# ---------------------------------------------------------------------------
# Output normalization
# ---------------------------------------------------------------------------

def _fallback_clean_completion(raw_completion: str, lang: str) -> str:
    cleaned = textwrap.dedent(raw_completion).strip()
    if not cleaned:
        return ""
    fenced = re.match(r"^```[\w+-]*\n([\s\S]*?)\n```$", cleaned)
    if fenced:
        cleaned = textwrap.dedent(fenced.group(1)).strip()
    if lang == "python":
        match = re.search(r"^\s*def\s+\w+\s*\(.*?\)\s*:\s*\n([\s\S]*)$", cleaned, re.MULTILINE)
        if match:
            return textwrap.dedent(match.group(1)).strip()
        return cleaned
    stripped = cleaned.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped[1:-1].strip()
    return stripped


def _normalize_function_body(task_dir: Path, body: str, stub_info: dict) -> str:
    if not body:
        return body
    lang = stub_info.get("lang", "")
    if lang == "python":
        return _normalize_python_body(body)
    dedented = _normalize_brace_indentation(body).rstrip()
    hollowed_text = (task_dir / "hollowed_files" / stub_info["file"]).read_text(encoding="utf-8")
    stub_indent = _find_stub_indent(hollowed_text.splitlines(), stub_info.get("stub", ""))
    lines = []
    for line in dedented.splitlines():
        lines.append("" if not line.strip() else f"{stub_indent}{line}")
    return "\n".join(lines).rstrip()


def _normalize_python_body(body: str) -> str:
    dedented = textwrap.dedent(body).strip("\n")
    lines = dedented.splitlines()
    if not lines:
        return ""
    first_idx = next((i for i, l in enumerate(lines) if l.strip()), None)
    if first_idx is None:
        return ""
    first_width = _indent_width(lines[first_idx])
    normalized = []
    for line in lines:
        if not line.strip():
            normalized.append("")
            continue
        rel = _indent_width(line) - first_width
        normalized.append(" " * max(0, 4 + rel) + line.lstrip(" \t"))
    return "\n".join(normalized).rstrip()


def _find_stub_indent(lines: list[str], stub: str) -> str:
    for line in lines:
        if line.strip() == stub:
            return line[: len(line) - len(line.lstrip(" \t"))]
    return ""


def _normalize_brace_indentation(body: str, *, tabstop: int = 4) -> str:
    lines = body.strip("\n").splitlines()
    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        return ""
    min_width = min(_indent_width(l, tabstop) for l in non_empty)
    return "\n".join(
        "" if not l.strip() else _strip_indent_width(l, min_width, tabstop)
        for l in lines
    ).rstrip()


def _indent_width(line: str, tabstop: int = 4) -> int:
    w = 0
    for ch in line:
        if ch == " ": w += 1
        elif ch == "\t": w += tabstop
        else: break
    return w


def _strip_indent_width(line: str, width: int, tabstop: int = 4) -> str:
    rem, idx = width, 0
    while idx < len(line) and rem > 0:
        ch = line[idx]
        if ch == " ": rem -= 1; idx += 1
        elif ch == "\t": rem -= tabstop; idx += 1
        else: break
    return line[idx:]
