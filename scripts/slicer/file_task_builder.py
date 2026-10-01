"""L2 file-level task builder — generates one evaluation task per eligible source file."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from slicer.parser import SymbolExtractor, FunctionInfo
from slicer.hollower import hollow_all_functions
from slicer.project import ProjectContext


def is_eligible_for_l2(
    src_file: Path, functions: list[FunctionInfo],
) -> bool:
    non_trivial = [f for f in functions if not f.is_trivial]
    if len(non_trivial) < 3:
        return False
    return True


def build_l2_tasks(ctx: ProjectContext) -> int:
    extractor = SymbolExtractor(ctx.lang_config)
    tasks_dir = ctx.project_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)

    # Collect eligible files first to detect stem collisions
    eligible: list[tuple[Path, list[FunctionInfo]]] = []
    stem_count: dict[str, int] = {}
    for src_file in ctx.source_files:
        functions = extractor.extract_functions(src_file)
        if not is_eligible_for_l2(src_file, functions):
            continue
        non_trivial = [f for f in functions if not f.is_trivial]
        eligible.append((src_file, non_trivial))
        stem_count[src_file.stem] = stem_count.get(src_file.stem, 0) + 1

    count = 0
    for src_file, non_trivial in eligible:
        task_name = _make_task_name(src_file, ctx.source_roots, stem_count)
        _build_one_l2_task(src_file, non_trivial, ctx, extractor, tasks_dir, task_name)
        count += 1

    return count


def _make_task_name(src_file: Path, source_roots: list[Path], stem_count: dict[str, int]) -> str:
    """Generate a unique L2 task directory name.

    Uses plain stem (L2_{stem}) when unique within the project.
    Falls back to relative path (L2_{dir}__{stem}) when stems collide.
    """
    if stem_count.get(src_file.stem, 1) <= 1:
        return f"L2_{src_file.stem}"
    rel = _resolve_rel_path(src_file, source_roots)
    if rel:
        # e.g. "middleware/compress.go" -> "L2_middleware__compress_go"
        # Keep extension to distinguish .cpp/.h with same stem
        name = Path(rel).as_posix().replace("/", "__").replace(".", "_")
        return f"L2_{name}"
    return f"L2_{src_file.stem}"


def _build_one_l2_task(
    src_file: Path,
    non_trivial: list[FunctionInfo],
    ctx: ProjectContext,
    extractor: SymbolExtractor,
    tasks_dir: Path,
    task_name: str,
) -> None:
    task_dir = tasks_dir / task_name

    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)

    source = src_file.read_bytes()
    hollowed_source = hollow_all_functions(
        source, non_trivial, ctx.lang_config.stub, ctx.language,
    )

    hollowed_file_rel = _resolve_rel_path(src_file, ctx.source_roots)
    context_files = _collect_context_files(src_file, ctx)

    hollowed_files_dir = task_dir / "hollowed_files"
    if hollowed_file_rel:
        dest = hollowed_files_dir / hollowed_file_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(hollowed_source)

    task_json = {
        "level": "L2",
        "target": hollowed_file_rel or src_file.name,
        "hollowed_files": [hollowed_file_rel] if hollowed_file_rel else [],
        "context_from_src": sorted(set(context_files)),
        "stub_info": {
            "file": hollowed_file_rel or src_file.name,
            "lang": ctx.language,
            "function_count": len(non_trivial),
        },
    }
    _write_json(task_dir / "task.json", task_json)

    run_config = {
        "docker_image": ctx.config.get("docker_image", ""),
        "install_command": ctx.config.get("install_command", ""),
        "test_command": ctx.config.get("test_command", ""),
        "src_dir": "../../src",
        "hollowed_files": [hollowed_file_rel] if hollowed_file_rel else [],
    }
    _write_json(task_dir / "run_config.json", run_config)

    prompt = _build_l2_prompt(
        src_file, hollowed_source, ctx, extractor, hollowed_file_rel,
    )
    (task_dir / "prompt.md").write_text(prompt, encoding="utf-8")


def _resolve_rel_path(src_file: Path, source_roots: list[Path]) -> str | None:
    for root in source_roots:
        try:
            return str(src_file.relative_to(root))
        except ValueError:
            continue
    return None


def _collect_context_files(src_file: Path, ctx: ProjectContext) -> list[str]:
    context = []
    for root in ctx.source_roots:
        for f in ctx.source_files:
            if f == src_file:
                continue
            try:
                context.append(str(f.relative_to(root)))
            except ValueError:
                continue
    return context


def _build_l2_prompt(
    src_file: Path,
    hollowed_source: bytes,
    ctx: ProjectContext,
    extractor: SymbolExtractor,
    hollowed_file_rel: str | None,
) -> str:
    display_path = hollowed_file_rel or src_file.name
    hollowed_text = hollowed_source.decode("utf-8", errors="replace")

    sections: list[str] = []
    sections.append(
        f"# Task\n\n"
        f"Generate the complete contents of `{display_path}`.\n"
        f"The file skeleton below shows the structure with function bodies replaced by stubs. "
        f"Fill in all function bodies and return the entire file.\n"
    )

    prd_excerpt = _extract_prd_excerpt(ctx.project_dir, src_file.stem)
    if prd_excerpt:
        sections.append(f"# Requirement Context\n\n{prd_excerpt}\n")

    sections.append(
        f"# Target File (Skeleton)\n\n"
        f"## {display_path}\n\n```\n{hollowed_text}\n```\n"
    )

    dep_snippets = _collect_dependency_snippets(src_file, ctx, extractor)
    if dep_snippets:
        parts = [f"## {rel}\n\n```\n{code}\n```" for rel, code in dep_snippets]
        sections.append("# Dependencies\n\n" + "\n\n".join(parts) + "\n")

    return "\n".join(sections)


def _extract_prd_excerpt(project_dir: Path, module_name: str) -> str:
    prd_path = project_dir / "docs" / "prd.md"
    if not prd_path.exists():
        return ""
    prd_text = prd_path.read_text(encoding="utf-8", errors="replace")
    keywords = {module_name.lower()}
    paragraphs = prd_text.split("\n\n")
    matched = [p.strip() for p in paragraphs if any(kw in p.lower() for kw in keywords)]
    return "\n\n".join(matched) if matched else ""


def _collect_dependency_snippets(
    src_file: Path,
    ctx: ProjectContext,
    extractor: SymbolExtractor,
    max_deps: int = 3,
) -> list[tuple[str, str]]:
    source = src_file.read_bytes()
    all_funcs = extractor.extract_functions(src_file)
    callee_names: set[str] = set()
    for func in all_funcs:
        callee_names.update(extractor.find_callees(func, source))

    other_files = [f for f in ctx.source_files if f != src_file]
    snippets: list[tuple[str, str]] = []
    seen_files: set[Path] = set()

    for symbol in sorted(callee_names):
        result = extractor.find_symbol_definition(symbol, other_files)
        if result is None:
            continue
        fpath, _, _ = result
        if fpath in seen_files:
            continue
        seen_files.add(fpath)
        rel = _resolve_rel_path(fpath, ctx.source_roots) or fpath.name
        code = fpath.read_text(encoding="utf-8", errors="replace")
        snippets.append((rel, code))
        if len(snippets) >= max_deps:
            break

    snippets.sort(key=lambda t: len(t[1]))
    return snippets


def _write_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
