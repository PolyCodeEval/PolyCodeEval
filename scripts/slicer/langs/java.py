from slicer.langs import LangConfig, register

config = register(LangConfig(
    name="java",
    ts_language="java",
    extensions=[".java"],
    function_node_types=["method_declaration"],
    method_node_types=["method_declaration", "constructor_declaration"],
    body_field_name="body",
    stub="throw new UnsupportedOperationException();",
    exclude_patterns=["*Test.java", "*Tests.java"],
))
