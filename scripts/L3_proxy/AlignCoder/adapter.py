"""Bridge PolyCodeEval L3 tasks to the upstream AlignCoder pipeline.

Supports two generation modes:
  aligncoder/<hf-model>                  — local HuggingFace model (via Docker)
  aligncoder-openai/<model>              — AlignRetriever + OpenAI API (via Docker)
  aligncoder-anthropic/<model>           — AlignRetriever + Anthropic API (via Docker)

宿主机负责：任务准备（load_l3_example）、序列化、结果归一化
Docker 负责：AlignCoder 完整推理（query enhancement + 检索 + 生成）
"""

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
_ALIGNCODER_ROOT = _REPO_ROOT.parent / "L3works" / "AlignCoder"
_DEBUG_ROOT = _REPO_ROOT / "results" / "l3_aligncoder_debug"
_WORKSPACE_ROOT = _REPO_ROOT / "output" / "aligncoder_workspaces"
_CONTAINER_NAME = "aligncoder-worker"
_MODELS_ROOT = _REPO_ROOT.parent / "L3works" / "models"

_INFERENCE_SCRIPT_HOST = _THIS_FILE.parent / "aligncoder_inference.py"
_INFERENCE_SCRIPT_CONTAINER = "/workspace/aligncoder_inference.py"


class AlignCoderError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Spec parsing
# ---------------------------------------------------------------------------

def _parse_model_spec(model_spec: str) -> tuple[str, str, str]:
    """Return (provider, model_name, retriever_model)."""
    if model_spec.startswith("aligncoder-openai/"):
        return "openai", model_spec.removeprefix("aligncoder-openai/"), "AlignCoder/AlignRetriever"
    if model_spec.startswith("aligncoder-anthropic/"):
        return "anthropic", model_spec.removeprefix("aligncoder-anthropic/"), "AlignCoder/AlignRetriever"
    if model_spec.startswith("aligncoder/"):
        rest = model_spec.removeprefix("aligncoder/")
        if "+" in rest:
            generator_model, retriever_model = rest.split("+", 1)
        else:
            generator_model, retriever_model = rest, "AlignCoder/AlignRetriever"
        return "local", generator_model, retriever_model
    raise AlignCoderError(
        f"不支持的 solver spec: {model_spec!r}. "
        "使用 aligncoder/<hf-model>, aligncoder-openai/<model>, 或 aligncoder-anthropic/<model>."
    )


# ---------------------------------------------------------------------------
# Docker 容器管理
# ---------------------------------------------------------------------------

def _ensure_docker_container() -> None:
    """确保长期运行的 AlignCoder Docker 容器已启动。"""
    check = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={_CONTAINER_NAME}"],
        capture_output=True, text=True,
    )
    if check.stdout.strip():
        return  # 已在运行

    print(f"🐳 启动 AlignCoder Docker 容器 ({_CONTAINER_NAME})...")

    has_image = subprocess.run(
        ["docker", "images", "-q", "aligncoder:latest"],
        capture_output=True, text=True,
    ).stdout.strip()

    if not has_image:
        dockerfile = _THIS_FILE.parent / "Dockerfile"
        if not dockerfile.exists():
            raise AlignCoderError(f"Dockerfile 不存在: {dockerfile}")
        print("构建 AlignCoder Docker 镜像...")

        import os as _os, sys as _sys
        build_env = _os.environ.copy()
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
            "-t", "aligncoder:latest",
            str(_THIS_FILE.parent),
        ], cwd=str(_REPO_ROOT), env=build_env)
        if ret.returncode != 0:
            raise AlignCoderError("Docker 镜像构建失败")

    _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    ret = subprocess.run([
        "docker", "run", "-d",
        "--name", _CONTAINER_NAME,
        "--gpus", "all",
        "--shm-size", "16g",
        # 工作区：路径在宿主机和容器内完全相同，无需路径转换
        "-v", f"{_WORKSPACE_ROOT}:{_WORKSPACE_ROOT}",
        # AlignCoder 源码（只读）
        "-v", f"{_ALIGNCODER_ROOT}:/workspace/L3works/AlignCoder:ro",
        # HF 模型缓存（可写）
        "-v", f"{_MODELS_ROOT}:/workspace/models",
        "-e", "HUGGINGFACE_HUB_CACHE=/workspace/models",
        "-e", "TRANSFORMERS_CACHE=/workspace/models",
        "-e", "TRANSFORMERS_OFFLINE=1",
        "-e", "HF_DATASETS_OFFLINE=1",
        # 推理脚本（只读挂载）
        "-v", f"{_INFERENCE_SCRIPT_HOST}:{_INFERENCE_SCRIPT_CONTAINER}:ro",
        "aligncoder:latest",
        "tail", "-f", "/dev/null",
    ], capture_output=True, text=True)

    if ret.returncode != 0:
        raise AlignCoderError(f"容器启动失败: {ret.stderr}")

    print(f"✅ 容器已启动: {_CONTAINER_NAME}")
    print(f"停止命令: docker stop {_CONTAINER_NAME} && docker rm {_CONTAINER_NAME}\n")


def _run_in_docker(payload: dict) -> dict:
    """把序列化后的 Example 通过 stdin 传给容器，读取 stdout 的 JSON 结果。"""
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
        capture_output=True,
        text=True,
        env=os.environ,
    )

    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-80:])
        raise AlignCoderError(
            f"Docker 推理失败 (exit {result.returncode}):\n{stderr_tail}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AlignCoderError(
            f"Docker 推理结果解析失败: {e}\nstdout: {result.stdout[:500]}"
        )


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def generate_function_body(task_dir: Path, model_spec: str) -> str:
    if not _ALIGNCODER_ROOT.is_dir():
        raise AlignCoderError(f"AlignCoder 源码不存在: {_ALIGNCODER_ROOT}")

    provider, model_name, retriever_model = _parse_model_spec(model_spec)
    language = task_dir.parents[2].name

    # 在宿主机上准备临时工作区
    aligncoder_str = str(_ALIGNCODER_ROOT)
    if aligncoder_str not in sys.path:
        sys.path.insert(0, aligncoder_str)
    from l3_loader import load_l3_example  # type: ignore

    example, workspace_dir = load_l3_example(task_dir)

    try:
        payload = {
            "task_id": example.task_id,
            "file_path": example.file_path,
            "left_context": example.left_context,
            "right_context": example.right_context,
            "language": example.language,
            "related_files": [
                {
                    "file_path": f.file_path,
                    "description": f.description,
                    "code_content": f.code_content,
                    "language": f.language,
                    "_type": f._type,
                    "_api_block": getattr(f, "_api_block", False),
                }
                for f in example.related_files
            ],
            "retriever_model": retriever_model,
            "provider": provider,
            "model_name": model_name,
            # AlignCoder 专有参数
            "add_api_blocks": language in ("python", "java"),
            "number_sample": 4,
            "temperature1": 0.8,
            "top_p1": 0.95,
        }

        result = _run_in_docker(payload)
        raw_completion = result.get("completion", "")
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        draft_input_tokens = result.get("draft_input_tokens", 0)
        draft_output_tokens = result.get("draft_output_tokens", 0)
        retriever_approx_tokens = result.get("retriever_approx_tokens", 0)
        debug_info = result.get("debug", {})

    finally:
        shutil.rmtree(workspace_dir, ignore_errors=True)

    # Debug 输出
    debug_dir = _DEBUG_ROOT / task_dir.parents[2].name / task_dir.parents[1].name / task_dir.name
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "raw_completion.txt").write_text(raw_completion, encoding="utf-8")
    # round1: 草稿生成（Query Enhancement，第一次 GPT 调用）
    (debug_dir / "usage_round1.json").write_text(
        json.dumps({
            "input_tokens":  draft_input_tokens,
            "output_tokens": draft_output_tokens,
            "total_tokens":  draft_input_tokens + draft_output_tokens,
            "note": "draft generation (query enhancement)",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # round2: 正式生成（第二次 GPT 调用）
    (debug_dir / "usage_round2.json").write_text(
        json.dumps({
            "input_tokens":  input_tokens,
            "output_tokens": output_tokens,
            "total_tokens":  input_tokens + output_tokens,
            "note": "final generation",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # retriever: AlignRetriever 输入序列长度（近似 token 数，本地模型无计费）
    (debug_dir / "usage_retriever.json").write_text(
        json.dumps({
            "retriever_approx_tokens": retriever_approx_tokens,
            "note": "AlignRetriever local model, approx input sequence length / 4",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # 保存 AlignCoder 独有的中间输出
    if debug_info.get("prompt_text"):
        (debug_dir / "final_prompt.txt").write_text(debug_info["prompt_text"], encoding="utf-8")
    if debug_info.get("retrieved_blocks"):
        (debug_dir / "retrieved_blocks.json").write_text(
            json.dumps(debug_info["retrieved_blocks"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    # draft_candidates: query enhancement 生成的草稿候选答案
    draft_candidates = debug_info.get("draft_candidates", [])
    if draft_candidates:
        draft_text = "\n\n".join(
            f"=== candidate answer {i + 1} ===\n{c}"
            for i, c in enumerate(draft_candidates)
        )
        (debug_dir / "draft_completions.txt").write_text(draft_text, encoding="utf-8")

    # 归一化
    task_json = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    stub_info = task_json["stub_info"]
    cleaned = _fallback_clean_completion(raw_completion, stub_info.get("lang", ""))
    normalized = _normalize_function_body(task_dir, cleaned, stub_info)
    (debug_dir / "cleaned_completion.txt").write_text(normalized, encoding="utf-8")

    if not normalized:
        raise AlignCoderError("AlignCoder 生成的函数体为空")
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
        normalized = _normalize_python_body(body)
        if not normalized:
            return ""
        return normalized

    dedented = _normalize_brace_indentation(body).rstrip()
    hollowed_text = (task_dir / "hollowed_files" / stub_info["file"]).read_text(encoding="utf-8")
    stub_indent = _find_stub_indent(hollowed_text.splitlines(), stub_info.get("stub", ""))
    normalized_lines = []
    for line in dedented.splitlines():
        if not line.strip():
            normalized_lines.append("")
            continue
        normalized_lines.append(f"{stub_indent}{line}")
    return "\n".join(normalized_lines).rstrip()


def _normalize_python_body(body: str) -> str:
    dedented = textwrap.dedent(body).strip("\n")
    lines = dedented.splitlines()
    if not lines:
        return ""

    first_idx = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first_idx is None:
        return ""

    first_width = _indent_width(lines[first_idx])
    storage_base_width = 4
    normalized: list[str] = []
    for line in lines:
        if not line.strip():
            normalized.append("")
            continue
        width = _indent_width(line)
        relative_width = width - first_width
        stored_width = storage_base_width + relative_width
        if stored_width < 0:
            stored_width = 0
        normalized.append((" " * stored_width) + line.lstrip(" \t"))
    return "\n".join(normalized).rstrip()


def _find_stub_indent(lines: list[str], stub: str) -> str:
    for line in lines:
        if line.strip() == stub:
            return line[: len(line) - len(line.lstrip(" \t"))]
    return ""


def _normalize_brace_indentation(body: str, *, tabstop: int = 4) -> str:
    lines = body.strip("\n").splitlines()
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return ""
    min_width = min(_indent_width(line, tabstop) for line in non_empty)
    normalized: list[str] = []
    for line in lines:
        if not line.strip():
            normalized.append("")
            continue
        normalized.append(_strip_indent_width(line, min_width, tabstop))
    return "\n".join(normalized).rstrip()


def _indent_width(line: str, tabstop: int = 4) -> int:
    width = 0
    for ch in line:
        if ch == " ":
            width += 1
        elif ch == "\t":
            width += tabstop
        else:
            break
    return width


def _strip_indent_width(line: str, width: int, tabstop: int = 4) -> str:
    remaining = width
    idx = 0
    while idx < len(line) and remaining > 0:
        ch = line[idx]
        if ch == " ":
            remaining -= 1
            idx += 1
        elif ch == "\t":
            remaining -= tabstop
            idx += 1
        else:
            break
    return line[idx:]
