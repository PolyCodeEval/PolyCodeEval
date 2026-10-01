"""APISolver — calls LLM APIs (Anthropic / OpenAI) with the task prompt."""

from __future__ import annotations

from pathlib import Path

from . import Solver


class APISolver(Solver):

    def __init__(self, provider: str, model_id: str):
        self._provider = provider
        self._model_id = model_id

    @property
    def name(self) -> str:
        return f"{self._provider}/{self._model_id}"

    def solve(self, task_dir: Path) -> str:
        prompt = (task_dir / "prompt.md").read_text(encoding="utf-8")
        if self._provider == "anthropic":
            return self._call_anthropic(prompt)
        if self._provider == "openai":
            return self._call_openai(prompt)
        raise ValueError(f"Unsupported provider: {self._provider}")

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=self._model_id,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    def _call_openai(self, prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI()
        resp = client.chat.completions.create(
            model=self._model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
        )
        return resp.choices[0].message.content
