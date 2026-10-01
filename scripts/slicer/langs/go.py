from slicer.langs import LangConfig, register

config = register(LangConfig(
    name="go",
    ts_language="go",
    extensions=[".go"],
    function_node_types=["function_declaration"],
    method_node_types=["method_declaration"],
    body_field_name="body",
    stub='panic("not implemented")',
    exclude_patterns=["*_test.go"],
))
