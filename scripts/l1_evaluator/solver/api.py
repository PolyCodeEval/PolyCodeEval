"""APISolver — calls LLM APIs (Anthropic / OpenAI) with the task prompt."""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import Solver


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _parse_multi_file_response(response: str) -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = re.compile(r"===FILE:\s*(.+?)===\n(.*?)(?=\n===FILE:|\Z)", re.DOTALL)
    for m in pattern.finditer(response):
        rel_path = m.group(1).strip()
        content = m.group(2).rstrip("\n")
        result[rel_path] = content
    return result


class APISolver(Solver):

    def __init__(self, provider: str, model_id: str):
        self._provider = provider
        self._model_id = model_id

    @property
    def name(self) -> str:
        return f"{self._provider}/{self._model_id}"

    def solve(self, task_dir: Path) -> dict[str, str]:
        prompt = (task_dir / "prompt.md").read_text(encoding="utf-8")
        if self._provider == "anthropic":
            raw = self._call_anthropic(prompt)
        elif self._provider == "openai":
            raw = self._call_openai(prompt)
        else:
            raise ValueError(f"Unsupported provider: {self._provider}")
        return _parse_multi_file_response(raw)

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=self._model_id,
            max_tokens=16384,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    def _call_openai(self, prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI()
        resp = client.chat.completions.create(
            model=self._model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=16384,
        )
        return resp.choices[0].message.content
