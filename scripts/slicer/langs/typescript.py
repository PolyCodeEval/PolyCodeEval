from slicer.langs import LangConfig, register

config = register(LangConfig(
    name="typescript",
    ts_language="typescript",
    extensions=[".ts"],
    function_node_types=["function_declaration"],
    method_node_types=["method_definition"],
    body_field_name="body",
    stub="throw new Error('not implemented')",
    exclude_patterns=["*.test.ts", "*.spec.ts"],
))
