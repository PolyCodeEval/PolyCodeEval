from __future__ import annotations

import json
import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

from slicer.langs import LangConfig, get_lang_config


@dataclass
class ProjectContext:
    project_dir: Path
    config: dict
    language: str
    lang_config: LangConfig
    source_roots: list[Path]
    source_files: list[Path] = field(default_factory=list)
    explicit_files: list[Path] = field(default_factory=list)  # individual files from source_dirs


def load_project(project_dir: str | Path) -> ProjectContext:
    project_dir = Path(project_dir).resolve()
    config_path = project_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"config.json not found in {project_dir}")

    with open(config_path) as f:
        config = json.load(f)

    language = config["language"]
    lang_config = get_lang_config(language)

    source_dirs = config.get("source_dirs", ["src"])
    source_roots, explicit_files = _resolve_source_dirs(project_dir, source_dirs)
    source_files = _collect_source_files(source_roots, lang_config) + explicit_files
    source_files = sorted(set(source_files))

    return ProjectContext(
        project_dir=project_dir,
        config=config,
        language=language,
        lang_config=lang_config,
        source_roots=source_roots,
        source_files=source_files,
        explicit_files=explicit_files,
    )


def _resolve_source_dirs(
    project_dir: Path, source_dirs: list[str]
) -> tuple[list[Path], list[Path]]:
    resolved_dirs = []
    resolved_files = []
    for sd in source_dirs:
        # Try as directory — prefer src/ variant if direct path has no source files
        candidate = project_dir / sd
        candidate_src = project_dir / "src" / sd
        if candidate.is_dir() and candidate_src.is_dir():
            # Pick whichever has more files (src/ variant wins ties)
            direct_count = sum(1 for _ in candidate.rglob("*") if _.is_file())
            src_count = sum(1 for _ in candidate_src.rglob("*") if _.is_file())
            resolved_dirs.append(candidate_src if src_count >= direct_count else candidate)
            continue
        if candidate.is_dir():
            resolved_dirs.append(candidate)
            continue
        if candidate_src.is_dir():
            resolved_dirs.append(candidate_src)
            continue
        # Try as individual file (common in C++ configs)
        candidate = project_dir / sd
        if candidate.is_file():
            resolved_files.append(candidate)
            continue
        candidate = project_dir / "src" / sd
        if candidate.is_file():
            resolved_files.append(candidate)
            continue
        print(f"  [WARN] source_dir '{sd}' not found, skipping")
    # If only individual files were found, add their parent dirs as source roots
    if not resolved_dirs and resolved_files:
        parents = sorted(set(f.parent for f in resolved_files))
        resolved_dirs = parents
    return resolved_dirs, resolved_files


EXCLUDED_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".tox", ".venv", "venv",
    "vendor", "dist", "build", ".next", "coverage", "test", "tests",
    "__tests__", "test_data", "testdata", "tasks",
    "cjs", "esm",
})

EXCLUDED_FILE_PATTERNS = [
    "*.min.js", "*.min.css", "*.bundle.js", "*.map",
    "*.min.mjs", "*.bundle.mjs",
]


def _collect_source_files(
    source_roots: list[Path], lang_config: LangConfig
) -> list[Path]:
    files = []
    for root in source_roots:
        for ext in lang_config.extensions:
            for path in root.rglob(f"*{ext}"):
                if not path.is_file():
                    continue
                if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
                    continue
                if _is_excluded(path.name, lang_config.exclude_patterns):
                    continue
                if _is_excluded(path.name, EXCLUDED_FILE_PATTERNS):
                    continue
                files.append(path)
    return sorted(files)


def _is_excluded(filename: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(filename, p) for p in patterns)


def discover_projects(
    datasets_root: Path, language: str | None = None
) -> list[Path]:
    projects = []
    for config_path in sorted(datasets_root.rglob("config.json")):
        if config_path.parent.parent.parent != datasets_root:
            continue
        if language:
            with open(config_path) as f:
                cfg = json.load(f)
            if cfg.get("language") != language:
                continue
        projects.append(config_path.parent)
    return projects
