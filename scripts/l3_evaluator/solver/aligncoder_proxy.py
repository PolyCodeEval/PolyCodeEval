"""Thin shim: delegates to L3_proxy/AlignCoder/adapter.generate_function_body."""

from __future__ import annotations

from pathlib import Path

from . import Solver


class AlignCoderProxySolver(Solver):
    def __init__(self, model_spec: str) -> None:
        self._model_spec = model_spec

    @property
    def name(self) -> str:
        return self._model_spec

    def solve(self, task_dir: Path) -> str:
        from L3_proxy.AlignCoder.adapter import generate_function_body
        return generate_function_body(task_dir, self._model_spec)
