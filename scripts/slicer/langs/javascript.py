from slicer.langs import LangConfig, register

config = register(LangConfig(
    name="javascript",
    ts_language="javascript",
    extensions=[".js", ".ts"],
    function_node_types=["function_declaration"],
    method_node_types=["method_definition"],
    body_field_name="body",
    stub="throw new Error('not implemented')",
    exclude_patterns=["*.test.js", "*.spec.js", "*.test.ts", "*.spec.ts"],
))
