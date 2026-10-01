"""Solver abstraction for L1 project-level evaluation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class Solver(ABC):
    """Given an L1 task directory, produce complete content for all hollowed files."""

    @abstractmethod
    def solve(self, task_dir: Path) -> dict[str, str]:
        """Returns {rel_path: complete_file_content} for all hollowed files."""
        ...

    @property
    @abstractmethod
    def name(self) -> str: ...


def make_solver(spec: str) -> Solver:
    """Parse a solver spec string and return the corresponding Solver instance.

    Supported formats:
      oracle                            -> OracleSolver
      anthropic/<model_id>              -> APISolver(provider="anthropic", ...)
      openai/<model_id>                 -> APISolver(provider="openai", ...)
      precomputed:<path/to/outputs/>    -> PrecomputedSolver(outputs_dir=...)
    """
    if spec == "oracle":
        from .oracle import OracleSolver
        return OracleSolver()

    if spec.startswith("precomputed:"):
        from .precomputed import PrecomputedSolver
        return PrecomputedSolver(Path(spec.removeprefix("precomputed:")))

    if "/" in spec:
        provider, model_id = spec.split("/", 1)
        if provider in ("anthropic", "openai"):
            from .api import APISolver
            return APISolver(provider=provider, model_id=model_id)

    raise ValueError(f"Unknown solver spec: {spec!r}")
