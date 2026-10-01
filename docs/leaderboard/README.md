# PolyCodeEval Community Leaderboard

The PolyCodeEval community leaderboard accepts results that participants generate
and evaluate on their own machines. A participant runs the official evaluator,
preserves its native output, adds one `submission.json`, and opens a GitHub Pull
Request. Optional text logs may accompany the result.

PolyCodeEval does not receive generated source code and does not run community
submissions on a server. Published community entries therefore carry the
provenance label **Self-evaluated, maintainer-reviewed**. Maintainer review covers
the submission format, metric consistency, benchmark identity, and declared
metadata. It does not certify an independent rerun.

## Submission at a glance

```text
Download PolyCodeEval
  -> generate code locally
  -> run the official evaluator locally
  -> preserve the native evaluation directory
  -> add submission.json
  -> validate the package
  -> open a Pull Request
  -> pass automated checks and maintainer review
  -> appear on the leaderboard
```

The Pull Request adds one directory:

```text
community-results/
  pce-1.0/
    L3/
      example-user/
        method-x-model-y/
          submission.json
          evaluation/
            summary.json
            cpp/
            go/
            java/
            javascript/
            python/
          logs/                 # optional
```

The `evaluation/` directory is a copy of the output directory produced by the
official evaluator. Per-task JSON files remain unchanged. The only additional
required file is `submission.json`.

Generated projects, generated target files, generated function bodies, model
response archives, datasets, dependencies, and build caches must not be included.

## Benchmark tracks

| Level | Evaluation unit | Release denominator | Scoring mode |
|---|---|---:|---|
| L0 | Complete project | 58 | `correctness_only` or `full_quality` |
| L1 | Complete project generated with a supplied skeleton | 58 | `correctness_only` or `full_quality` |
| L2 | Completed target file | 150 | `execution` |
| L3 | Completed target function body | 2,324 | `execution` |

Partial submissions are accepted. Every public score uses the complete release
denominator. Missing tasks receive zero for build success, full pass, execution
or correctness, and applicable quality dimensions.

## Documentation

- [Submitting results](submitting-results.md): end-to-end local evaluation,
  packaging, validation, and Pull Request workflow.
- [Submission JSON reference](submission-json-reference.md): the single required
  metadata file, field definitions, and examples.
- [Native result format](native-result-format.md): native L0/L1 and L2/L3 result
  directories and fields.
- [Ranking policy](ranking-policy.md): metrics, fixed denominators, partial
  submissions, ordering, and provenance.
- [Review policy](review-policy.md): automated validation and maintainer review.
- [Privacy checklist](privacy-checklist.md): required checks before publishing
  evaluator output and logs.
- [Troubleshooting](troubleshooting.md): common validation and Pull Request
  failures.

## Public-data warning

Everything added through a Pull Request becomes public and remains visible in Git
history. Native evaluator results can contain `stdout`, `stderr`, commands, test
names, and diagnostic details. Submitters must inspect these fields and optional
logs before opening a Pull Request.
