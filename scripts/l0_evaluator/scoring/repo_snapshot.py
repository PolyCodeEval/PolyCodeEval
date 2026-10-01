"""Snapshot and heuristic helpers for generated repositories."""

from __future__ import annotations

import json
import re
from pathlib import Path

TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".md",
    ".mjs",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}
IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "vendor",
}
BUILD_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "package.json",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "CMakeLists.txt",
    "Makefile",
    "manage.py",
}
KEY_FILE_PATTERNS = (
    "main.",
    "app.",
    "server.",
    "index.",
    "manage.py",
    "routes",
    "router",
    "controller",
    "service",
    "model",
    "repository",
    "handler",
    "api",
)
STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "must", "should",
    "would", "there", "their", "using", "used", "have", "has", "had", "will",
    "into", "when", "where", "your", "about", "under", "only", "need", "needs",
    "project", "requirements", "feature", "features", "constraint", "constraints",
}


def read_text_safe(path: Path, limit: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def build_file_tree(root: Path, *, max_files: int = 200) -> str:
    files = sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and not _is_ignored_path(path, root)
    )
    if not files:
        return "(empty repository)"
    shown = files[:max_files]
    suffix = ""
    if len(files) > max_files:
        suffix = f"\n... ({len(files) - max_files} more files omitted)"
    return "\n".join(shown) + suffix


def list_repo_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and not _is_ignored_path(path, root))


def _is_ignored_path(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        rel_parts = path.parts
    return any(part in IGNORED_DIR_NAMES for part in rel_parts[:-1])


def summarize_prompt_requirements(prompt_text: str, *, limit: int = 5000) -> str:
    marker = "# Project Requirements"
    if marker in prompt_text:
        prompt_text = prompt_text.split(marker, 1)[1]
    return prompt_text.strip()[:limit]


def collect_key_snippets(root: Path, *, max_files: int = 8, max_chars: int = 1800) -> list[dict]:
    candidates: list[tuple[int, Path]] = []
    for path in list_repo_files(root):
        rel = str(path.relative_to(root))
        score = 0
        if path.name in BUILD_FILES:
            score += 100
        lowered = rel.lower()
        if any(token in lowered for token in KEY_FILE_PATTERNS):
            score += 40
        score += min(path.stat().st_size if path.exists() else 0, 20000) // 500
        if path.suffix in TEXT_SUFFIXES:
            candidates.append((score, path))
    candidates.sort(key=lambda item: (-item[0], str(item[1])))

    snippets: list[dict] = []
    for _, path in candidates[:max_files]:
        text = read_text_safe(path, max_chars)
        if not text.strip():
            continue
        snippets.append({
            "path": str(path.relative_to(root)),
            "content": text,
        })
    return snippets


def detect_stack_profile(root: Path, language_hint: str) -> dict | None:
    files = list_repo_files(root)
    if not files:
        return None

    rels = [str(path.relative_to(root)) for path in files]
    content_index = {rel: read_text_safe(root / rel, 5000) for rel in rels if Path(rel).suffix in TEXT_SUFFIXES or Path(rel).name in BUILD_FILES}
    framework = ""
    build_system = ""
    persistence = ""
    frontend_presence = False
    app_style = "library"

    if language_hint == "python":
        build_system = "pyproject" if "pyproject.toml" in rels else "requirements" if "requirements.txt" in rels else "python"
        combined = "\n".join(content_index.values()).lower()
        pyproject = content_index.get("pyproject.toml", "").lower()
        requirements = content_index.get("requirements.txt", "").lower()
        if "django" in pyproject or "django" in requirements or "manage.py" in rels:
            framework = "django"
        elif "fastapi" in pyproject or "fastapi" in requirements:
            framework = "fastapi"
        elif "flask" in pyproject or "flask" in requirements:
            framework = "flask"
        else:
            framework = "python"
    elif language_hint == "go":
        build_system = "go-mod" if "go.mod" in rels else "go"
        go_mod = content_index.get("go.mod", "").lower()
        module_line = ""
        for line in go_mod.splitlines():
            line = line.strip()
            if line.startswith("module "):
                module_line = line
                break
        framework_tokens = {
            "github.com/go-chi/chi": "chi",
            "github.com/gin-gonic/gin": "gin",
            "github.com/labstack/echo": "echo",
            "github.com/spf13/cobra": "cobra",
            "github.com/gofiber/fiber": "fiber",
        }
        for needle, candidate in framework_tokens.items():
            if needle in go_mod or needle in module_line:
                framework = candidate
                break
        framework = framework or "go"
    elif language_hint == "java":
        build_system = "maven" if "pom.xml" in rels else "gradle" if any(name in rels for name in ("build.gradle", "build.gradle.kts")) else "java"
        build_text = "\n".join(content_index.get(name, "") for name in ("pom.xml", "build.gradle", "build.gradle.kts")).lower()
        if "spring-boot" in build_text or "springframework" in build_text:
            framework = "spring-boot"
        else:
            framework = "java"
    elif language_hint == "javascript":
        build_system = "npm" if "package.json" in rels else "javascript"
        package_json = content_index.get("package.json", "").lower()
        if "\"next\"" in package_json or "\"next\":" in package_json:
            framework = "next.js"
        elif "\"react\"" in package_json or "\"react\":" in package_json:
            framework = "react"
        elif "\"express\"" in package_json or "\"express\":" in package_json:
            framework = "express"
        elif "@nestjs" in package_json or "\"nestjs\"" in package_json:
            framework = "nestjs"
        else:
            framework = "javascript"
    elif language_hint == "cpp":
        build_system = "cmake" if "CMakeLists.txt" in rels else "make" if "Makefile" in rels else "cpp"
        framework = "cpp"
    else:
        build_system = language_hint
        framework = language_hint

    lowered_tree = "\n".join(rels).lower()
    if any(token in lowered_tree for token in ("templates/", "static/", "frontend/", "pages/", "components/")):
        frontend_presence = True
    if any(token in lowered_tree for token in ("api/", "routes/", "router/", "controllers/", "handlers/")):
        app_style = "service"
    elif any(token in lowered_tree for token in ("cmd/", "cli", "command")):
        app_style = "cli"
    elif frontend_presence:
        app_style = "web-app"

    combined = "\n".join(content_index.values()).lower()
    for db_name in ("postgres", "postgresql", "mysql", "sqlite", "mongodb", "redis"):
        if db_name in combined:
            persistence = db_name
            break

    non_empty = bool(framework or build_system or app_style)
    if not non_empty:
        return None
    return {
        "language": language_hint,
        "framework": framework or language_hint,
        "app_style": app_style,
        "build_system": build_system or language_hint,
        "persistence": persistence or "unknown",
        "frontend_presence": frontend_presence,
        "confidence": 0.8 if framework or build_system else 0.4,
    }


def keyword_candidates(text: str, *, limit: int = 8) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_/-]{2,}", text.lower())
    unique: list[str] = []
    for token in tokens:
        if token in STOP_WORDS:
            continue
        if token not in unique:
            unique.append(token)
        if len(unique) >= limit:
            break
    return unique


def find_evidence(root: Path, requirement_text: str, *, max_items: int = 3) -> list[dict]:
    keywords = keyword_candidates(requirement_text)
    if not keywords:
        return []

    scored: list[tuple[int, str, str]] = []
    for path in list_repo_files(root):
        if path.suffix not in TEXT_SUFFIXES and path.name not in BUILD_FILES:
            continue
        rel = str(path.relative_to(root))
        text = read_text_safe(path, 8000)
        haystack = f"{rel}\n{text}".lower()
        score = sum(3 if keyword in rel.lower() else 1 for keyword in keywords if keyword in haystack)
        if score <= 0:
            continue
        excerpt = text[:600]
        for keyword in keywords:
            idx = text.lower().find(keyword)
            if idx >= 0:
                start = max(0, idx - 120)
                end = min(len(text), idx + 280)
                excerpt = text[start:end]
                break
        scored.append((score, rel, excerpt.strip()))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"path": rel, "excerpt": excerpt}
        for _, rel, excerpt in scored[:max_items]
    ]


def dump_json_block(data: dict | list) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
