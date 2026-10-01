# Coverage Utilities

This package contains coverage parsing and reporting helpers used by
PolyCodeEval.

## Main utilities

- `runner.py`: project-level coverage runner.
- `per_task_pct.py`: language-specific helpers for per-file and per-function
  coverage percentages.
- `report_per_task_coverage.py`: builds per-task coverage reports under
  `finalresults/coverage_report/` from existing coverage summaries and
  artifacts.

Example:

```bash
python scripts/coverage/report_per_task_coverage.py --all
python scripts/coverage/report_per_task_coverage.py --language python
```
