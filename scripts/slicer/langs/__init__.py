from dataclasses import dataclass, field


@dataclass(frozen=True)
class LangConfig:
    name: str
    ts_language: str
    extensions: list[str]
    function_node_types: list[str]
    method_node_types: list[str]
    body_field_name: str
    stub: str
    exclude_patterns: list[str] = field(default_factory=list)


LANG_REGISTRY: dict[str, LangConfig] = {}


def register(cfg: LangConfig) -> LangConfig:
    LANG_REGISTRY[cfg.name] = cfg
    return cfg


def get_lang_config(language: str) -> LangConfig:
    if language not in LANG_REGISTRY:
        from slicer.langs import python, go, javascript, java, cpp, typescript  # noqa: F401
    return LANG_REGISTRY[language]
