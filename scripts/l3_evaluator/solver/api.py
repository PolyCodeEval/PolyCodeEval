"""APISolver — calls LLM APIs (Anthropic / OpenAI-compatible) with the task prompt."""

from __future__ import annotations

import os
import re
from pathlib import Path

from . import Solver


def _clean_code(content: str) -> str:
    """Strip markdown code fences and extract raw code."""
    pattern = re.compile(r"^```[\w]*\n(.*)```", re.DOTALL | re.MULTILINE)
    match = pattern.search(content.strip())
    if match:
        content = match.group(1)
    return content.replace("```", "").strip()


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
            return _clean_code(self._call_anthropic(prompt))
        return _clean_code(self._call_openai(prompt))

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=self._model_id,
            max_tokens=4096,
            system=(
                "You are an expert programmer. Complete the body of the function described in the prompt. "
                "Return ONLY the function body code. "
                "Do NOT include the function signature. "
                "Do NOT wrap the code in markdown formatting."
            ),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return msg.content[0].text

    def _call_openai(self, prompt: str) -> str:
        from openai import OpenAI

        base_url = os.environ.get("OPENAI_BASE_URL")
        api_key = os.environ.get("OPENAI_API_KEY")
        client = OpenAI(**({"base_url": base_url} if base_url else {}),
                        **({"api_key": api_key} if api_key else {}))
        resp = client.chat.completions.create(
            model=self._model_id,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert programmer. Complete the body of the function described in the prompt. "
                        "Return ONLY the function body code. "
                        "Do NOT include the function signature. "
                        "Do NOT wrap the code in markdown formatting."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=4096,
            temperature=0.2,
        )
        return resp.choices[0].message.content
