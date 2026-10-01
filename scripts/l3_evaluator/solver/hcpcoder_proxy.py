from pathlib import Path
from scripts.l3_evaluator.solver import Solver


class HCPCoderProxySolver(Solver):
    def __init__(self, model_spec: str) -> None:
        self._model_spec = model_spec

    @property
    def name(self) -> str:
        return self._model_spec

    def solve(self, task_dir: Path) -> str:
        from scripts.L3_proxy.HCPCoder.adapter import generate_function_body
        return generate_function_body(task_dir, self._model_spec)
