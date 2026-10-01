"""Extract function bodies from L2 generated files and store in L3 format.

Usage:
    python scripts/l2_to_l3_extract/extract.py \
        --models l2_direct_full_sonnet l2_direct_full_gpt54 \
        --output All_answers/L2toL3
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import tree_sitter
import tree_sitter_python
import tree_sitter_java
import tree_sitter_go
import tree_sitter_javascript
import tree_sitter_cpp
import tree_sitter_typescript

from index_builder import build_l2_index, build_l3_index

REPO_ROOT = Path(__file__).resolve().parents[2]

# --- Tree-sitter setup for each language ---

LANG_MODULES = {
    "python": tree_sitter_python,
    "java": tree_sitter_java,
    "go": tree_sitter_go,
    "javascript": tree_sitter_javascript,
    "cpp": tree_sitter_cpp,
    "typescript": tree_sitter_typescript,
}

FUNCTION_NODE_TYPES = {
    "python": ["function_definition"],
    "java": ["method_declaration", "constructor_declaration"],
    "go": ["function_declaration", "method_declaration"],
    "javascript": ["function_declaration", "method_definition"],
    "cpp": ["function_definition"],
    "typescript": ["function_declaration", "method_definition"],
}

BODY_FIELD = {
    "python": "body",
    "java": "body",
    "go": "body",
    "javascript": "body",
    "cpp": "body",
    "typescript": "body",
}


@dataclass
class ExtractedFunction:
    name: str
    body_start_byte: int
    body_end_byte: int
    start_byte: int
    func_start_col: int  # column where the function definition starts


def _get_parser(lang: str) -> tree_sitter.Parser:
    if lang == "typescript":
        language = tree_sitter.Language(tree_sitter_typescript.language_typescript())
    else:
        module = LANG_MODULES[lang]
        language = tree_sitter.Language(module.language())
    return tree_sitter.Parser(language)


def _extract_function_name(node, source: bytes, lang: str) -> str | None:
    """Extract function name from a tree-sitter node."""
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")

    # C/C++: name inside declarator
    declarator = node.child_by_field_name("declarator")
    if declarator is None:
        return None

    def find_name(n):
        if n.type == "function_declarator":
            decl = n.child_by_field_name("declarator")
            if decl:
                return find_name(decl)
        if n.type == "qualified_identifier":
            for child in reversed(n.children):
                if child.type in ("identifier", "destructor_name"):
                    return source[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
        if n.type in ("identifier", "field_identifier"):
            return source[n.start_byte:n.end_byte].decode("utf-8", errors="replace")
        if n.type in ("pointer_declarator", "reference_declarator"):
            decl = n.child_by_field_name("declarator")
            if decl:
                return find_name(decl)
        return None

    return find_name(declarator)


def extract_functions(source: bytes, lang: str) -> list[ExtractedFunction]:
    """Parse source with tree-sitter and return all function definitions."""
    parser = _get_parser(lang)
    tree = parser.parse(source)
    node_types = set(FUNCTION_NODE_TYPES[lang])
    body_field = BODY_FIELD[lang]
    functions: list[ExtractedFunction] = []

    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in node_types:
            name = _extract_function_name(node, source, lang)
            if name is None:
                stack.extend(node.children)
                continue
            body_node = node.child_by_field_name(body_field)
            if body_node is None:
                stack.extend(node.children)
                continue
            functions.append(ExtractedFunction(
                name=name,
                body_start_byte=body_node.start_byte,
                body_end_byte=body_node.end_byte,
                start_byte=node.start_byte,
                func_start_col=node.start_point[1],
            ))
        stack.extend(node.children)

    functions.sort(key=lambda f: f.start_byte)
    return functions


def format_python_body(source: bytes, func: ExtractedFunction) -> str:
    """Extract Python function body, dedenting to remove only the def-level indent.

    The evaluator's _format_python_backfill adds def_width spaces to each line.
    So the stored body should have indentation = body_indent - def_indent.
    For a standard method (def at col 4, body at col 8): stored body has 4 spaces.
    """
    raw_body = source[func.body_start_byte:func.body_end_byte].decode("utf-8")
    lines = raw_body.splitlines()
    if not lines:
        return ""

    # Compute column of body_start_byte
    line_start = source.rfind(b"\n", 0, func.body_start_byte)
    body_col = func.body_start_byte - (line_start + 1) if line_start >= 0 else func.body_start_byte

    # def_col is where the function keyword starts
    def_col = func.func_start_col

    # Prepend body_col to line 0 so all lines have consistent absolute indent
    lines[0] = " " * body_col + lines[0]

    # Remove only the def_col portion of indent (keeping body-relative indent)
    if def_col > 0:
        stripped = []
        for line in lines:
            if not line.strip():
                stripped.append("")
            else:
                # Remove up to def_col spaces from the start
                remaining = def_col
                idx = 0
                while idx < len(line) and remaining > 0 and line[idx] == " ":
                    idx += 1
                    remaining -= 1
                stripped.append(line[idx:])
        return "\n".join(stripped)
    else:
        return "\n".join(lines)


def format_brace_body(source: bytes, func: ExtractedFunction) -> str:
    """Extract brace-language function body (including braces)."""
    raw_body = source[func.body_start_byte:func.body_end_byte].decode("utf-8")
    return raw_body


def extract_and_save(
    l2_output_file: Path,
    lang: str,
    project: str,
    target_file: str,
    parser_lang: str,
    l3_index: dict[tuple[str, str, str, str], str],
    output_dir: Path,
) -> dict:
    """Extract functions from one L2 file and save matched ones as L3 .txt files."""
    stats = {"extracted": 0, "not_found": 0, "parse_failed": False, "matched_tasks": []}

    try:
        source = l2_output_file.read_bytes()
    except Exception as e:
        stats["parse_failed"] = True
        stats["error"] = str(e)
        return stats

    try:
        functions = extract_functions(source, parser_lang)
    except Exception as e:
        stats["parse_failed"] = True
        stats["error"] = f"tree-sitter parse error: {e}"
        return stats

    seen_names: set[str] = set()
    for func in functions:
        if func.name in seen_names:
            continue
        seen_names.add(func.name)

        key = (lang, project, target_file, func.name)
        l3_task_name = l3_index.get(key)
        if l3_task_name is None:
            stats["not_found"] += 1
            continue

        if parser_lang == "python":
            body_text = format_python_body(source, func)
        else:
            body_text = format_brace_body(source, func)

        out_path = output_dir / "generated_code" / lang / project / f"{l3_task_name}.txt"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body_text, encoding="utf-8")
        stats["extracted"] += 1
        stats["matched_tasks"].append(l3_task_name)

    return stats


def run_extraction(models: list[str], output_base: Path, datasets_dir: Path, l2_base: Path):
    """Run the full extraction pipeline."""
    print("Building indexes from datasets...")
    l2_index = build_l2_index(datasets_dir)
    l3_index = build_l3_index(datasets_dir)
    print(f"  L2 index: {len(l2_index)} tasks")
    print(f"  L3 index: {len(l3_index)} functions")

    for model in models:
        print(f"\n{'='*60}")
        print(f"Processing model: {model}")
        print(f"{'='*60}")

        model_input_dir = l2_base / model / "generated_outputs"
        model_output_dir = output_base / model

        if not model_input_dir.is_dir():
            print(f"  WARNING: Input dir not found: {model_input_dir}")
            continue

        report = {
            "model": model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "l2_files_processed": 0,
            "l2_files_parse_failed": 0,
            "l3_tasks_expected": 0,
            "l3_tasks_extracted": 0,
            "l3_tasks_not_found": 0,
            "by_language": {},
            "by_project": {},
            "parse_failures": [],
            "unmatched_functions": [],
        }

        for (lang, project, l2_task_name), l2_info in sorted(l2_index.items()):
            l2_file = model_input_dir / lang / project / f"{l2_task_name}.txt"
            if not l2_file.exists():
                continue

            expected_l3 = [
                (k, v) for k, v in l3_index.items()
                if k[0] == lang and k[1] == project and k[2] == l2_info.target_file
            ]
            report["l3_tasks_expected"] += len(expected_l3)

            stats = extract_and_save(
                l2_output_file=l2_file,
                lang=lang,
                project=project,
                target_file=l2_info.target_file,
                parser_lang=l2_info.parser_lang,
                l3_index=l3_index,
                output_dir=model_output_dir,
            )

            report["l2_files_processed"] += 1

            if stats["parse_failed"]:
                report["l2_files_parse_failed"] += 1
                report["parse_failures"].append({
                    "file": f"{lang}/{project}/{l2_task_name}.txt",
                    "error": stats.get("error", "unknown"),
                })
            else:
                report["l3_tasks_extracted"] += stats["extracted"]
                report["l3_tasks_not_found"] += stats["not_found"]

            lang_stats = report["by_language"].setdefault(lang, {
                "l2_files": 0, "l3_expected": 0, "l3_extracted": 0, "parse_failures": 0
            })
            lang_stats["l2_files"] += 1
            lang_stats["l3_expected"] += len(expected_l3)
            lang_stats["l3_extracted"] += stats["extracted"]
            if stats["parse_failed"]:
                lang_stats["parse_failures"] += 1

            proj_key = f"{lang}/{project}"
            proj_stats = report["by_project"].setdefault(proj_key, {
                "l2_files": 0, "l3_expected": 0, "l3_extracted": 0
            })
            proj_stats["l2_files"] += 1
            proj_stats["l3_expected"] += len(expected_l3)
            proj_stats["l3_extracted"] += stats["extracted"]

        if report["l3_tasks_expected"] > 0:
            report["extraction_rate"] = round(
                report["l3_tasks_extracted"] / report["l3_tasks_expected"], 4
            )
        else:
            report["extraction_rate"] = 0.0

        report_path = model_output_dir / "extraction_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n  Results for {model}:")
        print(f"    L2 files processed: {report['l2_files_processed']}")
        print(f"    L2 parse failures:  {report['l2_files_parse_failed']}")
        print(f"    L3 tasks expected:  {report['l3_tasks_expected']}")
        print(f"    L3 tasks extracted: {report['l3_tasks_extracted']}")
        print(f"    Extraction rate:    {report['extraction_rate']:.1%}")
        print(f"    Report: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract function bodies from L2 generated files into L3 format"
    )
    parser.add_argument(
        "--models", nargs="+",
        default=["l2_direct_full_sonnet", "l2_direct_full_gpt54"],
        help="L2 model directories to process",
    )
    parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / "All_answers" / "L2toL3",
        help="Output base directory",
    )
    parser.add_argument(
        "--datasets", type=Path, default=REPO_ROOT / "datasets",
        help="Datasets directory",
    )
    parser.add_argument(
        "--l2-base", type=Path, default=REPO_ROOT / "All_answers" / "L2",
        help="L2 results base directory",
    )
    args = parser.parse_args()

    run_extraction(
        models=args.models,
        output_base=args.output,
        datasets_dir=args.datasets,
        l2_base=args.l2_base,
    )


if __name__ == "__main__":
    main()
