# Submission JSON Reference

`submission.json` is the only metadata file that participants add to native
PolyCodeEval evaluation results. It uses UTF-8 JSON and schema version `2`.

## Complete example

```json
{
  "schemaVersion": "2",
  "benchmarkVersion": "pce-1.0",
  "level": "L3",
  "submissionName": "Method X with Model Y",
  "submitter": {
    "github": "example-user",
    "affiliation": "Example University"
  },
  "method": {
    "name": "Method X",
    "version": "1.0",
    "paperUrl": "https://example.org/paper",
    "codeUrl": "https://github.com/example/method-x"
  },
  "model": {
    "name": "Model Y",
    "version": "2026-09",
    "provider": "Example Provider"
  },
  "evaluation": {
    "polycodeevalCommit": "0123456789abcdef0123456789abcdef01234567",
    "testMode": "both",
    "scoringMode": "execution",
    "command": "python scripts/run_l3_eval.py --all --solver precomputed:/data/generated --tests both --output /data/results",
    "startedAt": "2026-09-10T08:00:00Z",
    "finishedAt": "2026-09-10T11:30:00Z",
    "environment": {
      "os": "Linux",
      "architecture": "x86_64",
      "python": "3.11.9",
      "docker": "27.0.3"
    }
  },
  "notes": "Optional information needed to interpret this run."
}
```

## Required fields

| Field | Type | Meaning | Ranking effect |
|---|---|---|---|
| `schemaVersion` | string | Submission metadata schema; currently `2` | Selects validation rules |
| `benchmarkVersion` | string | Immutable benchmark release; currently `pce-1.0` | Selects tasks and denominators |
| `level` | string | `L0`, `L1`, `L2`, or `L3` | Selects result schema and ranking track |
| `submissionName` | string | Human-readable run name | Display only |
| `submitter.github` | string | GitHub account responsible for the Pull Request | Provenance and result ownership |
| `method.name` | string | Generation method name | Configuration identity |
| `method.version` | string | Method release, commit, or stable revision label | Configuration identity |
| `model.name` | string | Evaluated model name | Configuration identity |
| `model.version` | string | Model snapshot, API version, or release label | Configuration identity |
| `evaluation.polycodeevalCommit` | string | PolyCodeEval Git commit used for evaluation | Reproducibility and review |
| `evaluation.testMode` | string | Executed test selection | Comparability and review |
| `evaluation.scoringMode` | string | Available score family | Selects eligible leaderboard views |

## Optional fields

| Field | Type | Meaning |
|---|---|---|
| `submitter.affiliation` | string | Organization associated with the submission |
| `method.paperUrl` | string | Public method paper |
| `method.codeUrl` | string | Public method implementation |
| `model.provider` | string | Model provider or hosting organization |
| `evaluation.command` | string | Evaluator command with secrets and private paths removed |
| `evaluation.startedAt` | string | ISO 8601 evaluation start time |
| `evaluation.finishedAt` | string | ISO 8601 evaluation finish time |
| `evaluation.packagedAt` | string | Packaging time recorded by the submission tool |
| `evaluation.workingTreeDirty` | boolean | Whether the evaluator checkout contained uncommitted changes when packaged |
| `evaluation.environment.os` | string | Operating system |
| `evaluation.environment.architecture` | string | CPU architecture, such as `x86_64` or `arm64` |
| `evaluation.environment.python` | string | Python version |
| `evaluation.environment.docker` | string | Docker version |
| `notes` | string | Concise information required to interpret the result |

Optional objects and optional string fields may be omitted. Empty optional strings
are also accepted. Do not add a second environment or evidence JSON file.

## Level-specific values

| Level | `evaluation.testMode` | `evaluation.scoringMode` |
|---|---|---|
| L0 | `blackbox` | `correctness_only` or `full_quality` |
| L1 | `blackbox` | `correctness_only` or `full_quality` |
| L2 | `both`, `whitebox`, `blackbox`, or `mixed` | `execution` |
| L3 | `both`, `whitebox`, `blackbox`, or `mixed` | `execution` |

The metadata value must match the native per-task results. A submission containing
multiple native test modes declares `mixed`. Each level still uses one permitted
scoring mode.

## Minimal L0/L1 example

```json
{
  "schemaVersion": "2",
  "benchmarkVersion": "pce-1.0",
  "level": "L0",
  "submissionName": "Agent A with Model B",
  "submitter": { "github": "example-user" },
  "method": { "name": "Agent A", "version": "abc1234" },
  "model": { "name": "Model B", "version": "2026-09" },
  "evaluation": {
    "polycodeevalCommit": "0123456789abcdef0123456789abcdef01234567",
    "testMode": "blackbox",
    "scoringMode": "correctness_only"
  }
}
```

## Minimal L2/L3 example

```json
{
  "schemaVersion": "2",
  "benchmarkVersion": "pce-1.0",
  "level": "L2",
  "submissionName": "Method A with Model B",
  "submitter": { "github": "example-user" },
  "method": { "name": "Method A", "version": "1.0" },
  "model": { "name": "Model B", "version": "2026-09" },
  "evaluation": {
    "polycodeevalCommit": "0123456789abcdef0123456789abcdef01234567",
    "testMode": "both",
    "scoringMode": "execution"
  }
}
```

## Validation rules

- Names are trimmed, non-empty strings.
- `submitter.github` matches the account directory in the Pull Request.
- URLs use HTTP(S) when supplied.
- Timestamps should use ISO 8601 for consistent public display.
- `polycodeevalCommit` identifies the revision actually used for evaluation.
- Commands contain no credentials, access tokens, or private filesystem paths.
- Metadata must describe one method, one model, one level, and one evaluation
  configuration.
