from slicer.langs import LangConfig, register

config = register(LangConfig(
    name="python",
    ts_language="python",
    extensions=[".py"],
    function_node_types=["function_definition"],
    method_node_types=["function_definition"],
    body_field_name="body",
    stub="pass",
    exclude_patterns=["test_*.py", "*_test.py", "conftest.py"],
))
