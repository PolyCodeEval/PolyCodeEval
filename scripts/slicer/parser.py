from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from tree_sitter_languages import get_language, get_parser

from slicer.langs import LangConfig

MIN_BODY_LINES = 10

TRIVIAL_NAMES = frozenset({
    "__init__", "__str__", "__repr__", "__len__", "__hash__", "__eq__",
    "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__bool__",
    "setUp", "tearDown", "setUpClass", "tearDownClass",
    "toString", "hashCode", "equals",
    "String", "main",
})


def _clean_docstring(raw: str) -> str:
    """Strip quote delimiters from Python docstrings."""
    s = raw.strip()
    for delim in ('"""', "'''", '"', "'"):
        if s.startswith(delim) and s.endswith(delim) and len(s) >= len(delim) * 2:
            s = s[len(delim):-len(delim)]
            break
    return s.strip()


def _clean_doc_comment(raw: str) -> str | None:
    """Strip comment markers from Javadoc/JSDoc/Go/C++ doc comments."""
    lines = raw.splitlines()
    cleaned = []
    for line in lines:
        line = line.strip()
        line = re.sub(r"^(/\*+|///|//|\*+/?)\s*", "", line)
        line = line.rstrip("*/").strip()
        if line:
            cleaned.append(line)
    result = "\n".join(cleaned).strip()
    return result if result else None


@dataclass
class FunctionInfo:
    name: str
    file: Path
    start_byte: int
    end_byte: int
    body_start_byte: int
    body_end_byte: int
    start_line: int
    end_line: int
    body_lines: int
    is_trivial: bool
    docstring_end_byte: int | None = None
    doc_comment: str | None = None
    signature: str | None = None


class SymbolExtractor:
    def __init__(self, lang_config: LangConfig):
        self.lang_config = lang_config
        self.language = get_language(lang_config.ts_language)
        self.parser = get_parser(lang_config.ts_language)

    def extract_functions(self, file_path: Path) -> list[FunctionInfo]:
        source = file_path.read_bytes()
        tree = self.parser.parse(source)
        node_types = set(
            self.lang_config.function_node_types
            + self.lang_config.method_node_types
        )
        functions = []
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            if node.type in node_types:
                info = self._parse_function_node(node, file_path, source)
                if info is not None:
                    functions.append(info)
            stack.extend(node.children)
        return functions

    def _parse_function_node(
        self, node, file_path: Path, source: bytes
    ) -> FunctionInfo | None:
        name = self._extract_function_name(node, source)
        if name is None:
            return None

        body_node = node.child_by_field_name(self.lang_config.body_field_name)
        if body_node is None:
            return None

        body_lines = body_node.end_point[0] - body_node.start_point[0] + 1
        is_trivial = body_lines < MIN_BODY_LINES or name in TRIVIAL_NAMES

        docstring_end = self._find_docstring_end(body_node, source)
        doc_comment = self._extract_doc_comment(node, source, docstring_end)

        # 提取完整签名（从函数开始到函数体开始）
        signature_bytes = source[node.start_byte:body_node.start_byte]
        signature = signature_bytes.decode("utf-8", errors="replace").strip()

        # 清理签名：去掉函数体开始的 { 或 :
        if signature.endswith("{"):
            signature = signature[:-1].rstrip()
        if signature.endswith(":"):
            signature = signature[:-1].rstrip()

        return FunctionInfo(
            name=name,
            file=file_path,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            body_start_byte=body_node.start_byte,
            body_end_byte=body_node.end_byte,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            body_lines=body_lines,
            is_trivial=is_trivial,
            docstring_end_byte=docstring_end,
            doc_comment=doc_comment,
            signature=signature,
        )

    @staticmethod
    def _extract_function_name(node, source: bytes) -> str | None:
        """Extract function name from node, handling C++ declarator patterns."""
        # Direct name field (Python, Java, Go, JS)
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")

        # C/C++: name is inside declarator → function_declarator → identifier/qualified_identifier
        declarator = node.child_by_field_name("declarator")
        if declarator is None:
            return None

        # Walk down to find the deepest identifier
        def find_name(n):
            # function_declarator wraps the name and params
            if n.type == "function_declarator":
                decl = n.child_by_field_name("declarator")
                if decl:
                    return find_name(decl)
            # qualified_identifier: Class::method — take the last identifier
            if n.type == "qualified_identifier":
                for child in reversed(n.children):
                    if child.type == "identifier" or child.type == "destructor_name":
                        return source[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
            if n.type in ("identifier", "field_identifier"):
                return source[n.start_byte:n.end_byte].decode("utf-8", errors="replace")
            # pointer_declarator, reference_declarator
            if n.type in ("pointer_declarator", "reference_declarator"):
                decl = n.child_by_field_name("declarator")
                if decl:
                    return find_name(decl)
            return None

        return find_name(declarator)

    @staticmethod
    def _find_docstring_end(body_node, source: bytes) -> int | None:
        if body_node.child_count == 0:
            return None
        first_child = body_node.children[0]
        if first_child.type == "expression_statement":
            if first_child.child_count > 0 and first_child.children[0].type == "string":
                return first_child.end_byte
        if first_child.type == "comment":
            return first_child.end_byte
        return None

    @staticmethod
    def _extract_doc_comment(node, source: bytes, docstring_end_byte: int | None) -> str | None:
        # For Python: extract docstring text from body
        if docstring_end_byte is not None:
            body_field = node.child_by_field_name("body")
            if body_field and body_field.child_count > 0:
                first = body_field.children[0]
                if first.type == "expression_statement" and first.child_count > 0:
                    str_node = first.children[0]
                    if str_node.type == "string":
                        raw = source[str_node.start_byte:str_node.end_byte].decode("utf-8", errors="replace")
                        return _clean_docstring(raw)

        # For all languages: look for comment nodes immediately before the function node
        # Skip over annotations/modifiers that may sit between the doc comment and the function
        comment_types = {"comment", "block_comment", "doc_comment", "line_comment"}
        skip_types = {"marker_annotation", "annotation", "modifiers", "decorator"}
        collected = []
        sibling = node.prev_sibling
        while sibling is not None:
            if sibling.type in comment_types:
                text = source[sibling.start_byte:sibling.end_byte].decode("utf-8", errors="replace")
                collected.insert(0, text)
                sibling = sibling.prev_sibling
            elif sibling.type in skip_types or not sibling.is_named:
                sibling = sibling.prev_sibling
            else:
                break

        if not collected:
            return None
        return _clean_doc_comment("\n".join(collected))

    def find_callees(self, func: FunctionInfo, source: bytes) -> list[str]:
        code_start = func.docstring_end_byte or func.body_start_byte
        body_source = source[code_start:func.body_end_byte]
        tree = self.parser.parse(body_source)
        callees = set()
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            if node.type in ("call", "call_expression"):
                func_node = node.child_by_field_name("function")
                if func_node is not None:
                    text = body_source[func_node.start_byte:func_node.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    parts = text.rsplit(".", 1)
                    callees.add(parts[-1])
                    if len(parts) > 1:
                        callees.add(parts[0])
            stack.extend(node.children)
        return sorted(callees)

    def find_callers(
        self, func_name: str, all_files: list[Path]
    ) -> list[FunctionInfo]:
        callers = []
        needle = func_name.encode()
        for fpath in all_files:
            source = fpath.read_bytes()
            if needle not in source:
                continue
            functions = self.extract_functions(fpath)
            for fn in functions:
                body = source[fn.body_start_byte:fn.body_end_byte]
                if needle not in body:
                    continue
                if self._has_call_to(body, func_name):
                    callers.append(fn)
        return callers

    def _has_call_to(self, body: bytes, func_name: str) -> bool:
        tree = self.parser.parse(body)
        target = func_name.encode()
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            if node.type in ("call", "call_expression"):
                func_node = node.child_by_field_name("function")
                if func_node is not None:
                    text = body[func_node.start_byte:func_node.end_byte]
                    parts = text.rsplit(b".", 1)
                    if parts[-1] == target:
                        return True
            stack.extend(node.children)
        return False

    def find_symbol_definition(
        self, symbol_name: str, all_files: list[Path]
    ) -> tuple[Path, int, int] | None:
        definition_types = set(
            self.lang_config.function_node_types
            + self.lang_config.method_node_types
            + ["class_definition", "class_declaration",
               "struct_specifier", "type_declaration", "type_spec"]
        )
        needle = symbol_name.encode()
        for fpath in all_files:
            source = fpath.read_bytes()
            if needle not in source:
                continue
            tree = self.parser.parse(source)
            stack = [tree.root_node]
            while stack:
                node = stack.pop()
                if node.type in definition_types:
                    name_node = node.child_by_field_name("name")
                    if name_node is not None:
                        name = source[name_node.start_byte:name_node.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                        if name == symbol_name:
                            return (fpath, node.start_byte, node.end_byte)
                stack.extend(node.children)
        return None
