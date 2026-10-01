from __future__ import annotations

from slicer.parser import FunctionInfo


def hollow_function(source: bytes, func: FunctionInfo, stub: str, lang: str) -> bytes:
    if lang == "python":
        replacement = _python_stub_with_docstring(source, func, stub)
    elif lang in ("cpp", "c"):
        body = source[func.body_start_byte:func.body_end_byte]
        replacement = _braced_stub(body, stub)
    else:
        body = source[func.body_start_byte:func.body_end_byte]
        replacement = _braced_stub(body, stub)

    return source[:func.body_start_byte] + replacement + source[func.body_end_byte:]


def hollow_all_functions(
    source: bytes, functions: list[FunctionInfo], stub: str, lang: str
) -> bytes:
    sorted_funcs = sorted(functions, key=lambda f: f.body_start_byte, reverse=True)
    for func in sorted_funcs:
        source = hollow_function(source, func, stub, lang)
    return source


def _python_stub(body: bytes, stub: str) -> bytes:
    first_line = body.split(b"\n", 1)[0]
    indent = len(first_line) - len(first_line.lstrip())
    if indent == 0:
        indent = 4
    return (" " * indent + stub).encode("utf-8")


def _python_stub_with_docstring(source: bytes, func: FunctionInfo, stub: str) -> bytes:
    # Infer indent from the def/class line: find the line containing start_byte
    def_line_start = source.rfind(b"\n", 0, func.start_byte) + 1
    def_line = source[def_line_start:func.start_byte + 50].split(b"\n", 1)[0]
    def_indent = len(def_line) - len(def_line.lstrip())
    body_indent = def_indent + 4
    stub_bytes = (" " * body_indent + stub).encode("utf-8")

    if func.docstring_end_byte is not None:
        docstring_part = source[func.body_start_byte:func.docstring_end_byte]
        return docstring_part + b"\n" + stub_bytes
    else:
        return stub_bytes


def _braced_stub(body: bytes, stub: str) -> bytes:
    return ("{\n    " + stub + "\n}").encode("utf-8")
