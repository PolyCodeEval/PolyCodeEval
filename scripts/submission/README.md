# PolyCodeEval Result Submission Tools

These tools package results that contributors have already generated and evaluated locally. They never package generated code and never run an evaluator.

## Package format

```text
submission.json
evaluation/
  summary.json
  <language>/<project>/<task>.json
logs/                                      # optional
```

`evaluation/` is copied byte-for-byte from the output passed to an evaluator's `--output` option. The only additional required file is `submission.json`. Its complete schema is in `submission.schema.json`.

## Prepare a submission

```bash
python scripts/submission/prepare_submission.py \
  --results results/my_l3_run \
  --output community-results/pce-1.0/L3/my-user/my-method-model \
  --level L3 \
  --submission-name "My method with My model" \
  --github-user my-user \
  --method "My method" \
  --method-version "1.0" \
  --model "My model" \
  --model-version "2026-09"
```

The command records the current PolyCodeEval commit, working-tree state, operating system, architecture, Python version, Docker version, inferred test mode, and inferred scoring mode in `submission.json`. It creates both the PR-ready directory and a sibling ZIP. Run it in the environment used for evaluation so the recorded environment remains meaningful.

For L0/L1, use `--scoring-mode correctness_only` when only Correctness was evaluated. Fully populated C/F/A/H results are inferred as `full_quality`. L2/L3 always use `execution`.

Optional logs can be included with `--logs <directory>`. Supported extensions are `.log`, `.txt`, `.json`, and `.jsonl`; each file is limited to 5 MB and all logs together to 20 MB. Logs do not affect ranking.

## Validate and aggregate

```bash
python scripts/submission/validate_submission.py path/to/submission
python scripts/submission/validate_submission.py path/to/submission.zip --json
python scripts/submission/aggregate_submission.py path/to/submission --output aggregate.json
```

Validation discovers canonical task IDs from `datasets/<language>/<project>/tasks/`. It checks native result paths and fields, score formulas, the evaluator-produced summary, logs, forbidden code artifacts, and probable secrets.

Official denominators are fixed at L0=58, L1=58, L2=150, and L3=2,324. Partial submissions are accepted; every missing task contributes zero to fixed-denominator rates and averages. The original `summary.json` is checked against the submitted task files, while the aggregate command reports fixed-denominator leaderboard metrics.

## `submission.json` fields

- `schemaVersion`, `benchmarkVersion`, `level`, and `submissionName` identify the submission.
- `submitter.github` is the contributor's GitHub username; `affiliation` is optional.
- `method.name` and `method.version` are required; paper and code URLs are optional.
- `model.name` and `model.version` are required; provider is optional.
- `evaluation.polycodeevalCommit`, `testMode`, and `scoringMode` define the evaluation configuration.
- `evaluation.environment` records the local runtime. Command and timestamps are optional.
- `notes` is optional and does not affect ranking.

Do not submit API keys, credentials, `.env` files, generated repositories, generated target files, function bodies, datasets, dependencies, or build caches.
