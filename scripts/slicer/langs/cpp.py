from slicer.langs import LangConfig, register

config = register(LangConfig(
    name="cpp",
    ts_language="cpp",
    extensions=[".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hxx"],
    function_node_types=["function_definition"],
    method_node_types=["function_definition"],
    body_field_name="body",
    stub="/* not implemented */",
    exclude_patterns=[],
))
