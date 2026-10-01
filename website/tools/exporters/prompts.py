"""Export the curated prompt catalog."""

from __future__ import annotations

import re
from typing import Any

from .common import PROMPT_DOCS, source_link


PROMPT_SOURCES = {
    "task_prompt_templates.md": None,
    "description_generation_prompts.md": {
        "L2 File Description Generation", "L3 Function Description Generation", "Compatibility L3 Description Generation",
    },
    "generation_method_prompts.md": {
        "L0 Agent Generation", "L1 Agent Generation", "L2 Agent Generation", "L2 Direct API Generation",
        "L3 Direct API Generation", "L3 RepoCoder Generation", "L3 HCP-Coder Generation", "L3 AlignCoder Generation",
    },
    "project_evaluation_prompts.md": None,
    "prompt_quality_scoring_prompts.md": None,
}


def fenced_blocks(text: str) -> list[str]:
    pattern = re.compile(r"^(`{3,})(?:[A-Za-z0-9_+-]+)?\s*\n(.*?)^\1\s*$", re.M | re.S)
    return [match.group(2).rstrip() for match in pattern.finditer(text)]


def h2_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        fence_match = re.match(r"(`{3,})", stripped)
        if fence_match:
            ticks = fence_match.group(1)
            if fence is None:
                fence = ticks
            elif len(ticks) >= len(fence):
                fence = None
        heading = re.match(r"^##\s+(.+?)\s*$", line.rstrip("\n")) if fence is None else None
        if heading:
            if current is not None:
                sections.append(current)
            current = (heading.group(1).strip(), [])
        elif current is not None:
            current[1].append(line)
    if current is not None:
        sections.append(current)
    return [(title, "".join(lines)) for title, lines in sections]


def build_prompt_catalog() -> dict[str, Any]:
    entries = []
    for filename, allowed in PROMPT_SOURCES.items():
        path = PROMPT_DOCS / filename
        text = path.read_text(encoding="utf-8")
        for title, section in h2_sections(text):
            if allowed is not None and title not in allowed:
                continue
            blocks = fenced_blocks(section)
            if not blocks:
                continue
            category = (
                "Task construction" if filename == "task_prompt_templates.md" else
                "Description generation" if filename == "description_generation_prompts.md" else
                "Generation" if filename == "generation_method_prompts.md" else
                "Evaluation" if filename == "project_evaluation_prompts.md" else
                "Prompt quality"
            )
            entries.append({
                "id": re.sub(r"[^a-z0-9]+", "-", f"{filename[:-3]}-{title}".lower()).strip("-"),
                "title": title,
                "category": category,
                "blocks": blocks,
                "sourceLink": source_link(path),
            })
    return {"entryCount": len(entries), "entries": entries}
