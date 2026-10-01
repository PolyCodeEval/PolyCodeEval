"""Thin RepoCoder proxy solver for PolyCodeEval L3."""

from __future__ import annotations

from pathlib import Path

from L3_proxy.RepoCoder.adapter import generate_function_body

from . import Solver


class RepoCoderProxySolver(Solver):

    def __init__(self, model_spec: str):
        self._model_spec = model_spec

    @property
    def name(self) -> str:
        return self._model_spec

    def solve(self, task_dir: Path) -> str:
        return generate_function_body(task_dir, self._model_spec)
