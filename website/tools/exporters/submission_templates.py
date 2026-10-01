"""Generate the public result-submission schema, template, and starter kit."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .common import ROOT
from .leaderboard import RELEASE_VERSION


def _template() -> dict:
    return {
        "schemaVersion": "2",
        "benchmarkVersion": RELEASE_VERSION,
        "level": "L3",
        "submissionName": "",
        "submitter": {"github": "", "affiliation": ""},
        "method": {"name": "", "version": "", "paperUrl": "", "codeUrl": ""},
        "model": {"name": "", "version": "", "provider": ""},
        "evaluation": {
            "polycodeevalCommit": "",
            "testMode": "both",
            "scoringMode": "execution",
            "command": "",
            "startedAt": "",
            "finishedAt": "",
            "environment": {"os": "", "architecture": "", "python": "", "docker": ""},
        },
        "notes": "",
    }


README = """# PolyCodeEval Result Submission Kit

Submit locally evaluated results through a GitHub pull request.

1. Generate code and run the official PolyCodeEval evaluator locally.
2. Keep the evaluator output unchanged below `evaluation/`.
3. Complete `submission.json` or use `scripts/submission/prepare_submission.py`.
4. Add optional public logs below `logs/`.
5. Validate the package on the website or with `validate_submission.py`.

Package layout:

```text
submission.json
evaluation/
  summary.json
  <language>/<project>/<task>.json
logs/  # optional
```

Generated code is not part of a community result submission. Partial result sets
are accepted; missing benchmark tasks receive zero in fixed-denominator ranking.
"""


def build_submission_assets(data_dir: Path, release: dict) -> list[Path]:
    del release
    target = data_dir / "submit"
    target.mkdir(parents=True, exist_ok=True)
    schema_path = target / "submission-schema.json"
    template_path = target / "submission-template.json"
    kit_path = target / "result-submission-kit.zip"
    source_schema = ROOT / "scripts" / "submission" / "submission.schema.json"
    schema = json.loads(source_schema.read_text(encoding="utf-8"))
    schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    template_path.write_text(json.dumps(_template(), indent=2) + "\n", encoding="utf-8")
    with ZipFile(kit_path, "w", ZIP_DEFLATED) as bundle:
        bundle.writestr("submission.json", json.dumps(_template(), indent=2) + "\n")
        bundle.writestr("README.md", README)
        bundle.writestr("evaluation/summary.json", "{}\n")
        bundle.writestr("logs/.gitkeep", "")
    return [schema_path, template_path, kit_path]
