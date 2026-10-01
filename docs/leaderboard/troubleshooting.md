# Troubleshooting Result Submissions

## The validator cannot find submission.json

Place `submission.json` at the root of the submission directory, beside
`evaluation/`:

```text
<submission-id>/
  submission.json
  evaluation/
```

Do not place an additional parent directory inside the validation ZIP.

## An obsolete environment.json or evidence.json is reported

Remove it. All declared environment information belongs in
`submission.json.evaluation`. Logs require no index file.

## The package contains outputs or generated artifacts

The leaderboard receives evaluated results only. Remove generated repositories,
completed target files, function bodies, model responses, and any `outputs/`
directory. Keep those artifacts locally for your own reproduction records.

## A task path does not match its task field

For a task field such as:

```text
python/chakin/L0_chakin
```

the result path must be:

```text
evaluation/python/chakin/L0_chakin.json
```

Preserve language, project, task name, case, punctuation, and underscores exactly
as emitted by the evaluator.

## The native summary differs from task records

Run the evaluator's aggregation step again on the same output directory. Common
causes include an interrupted run, copying results from multiple configurations,
editing a task JSON, or retaining stale files from an earlier run.

Use a clean output directory for each method, model, level, test mode, and scoring
mode.

## The result has fewer tasks than the release

Partial submissions are valid. The leaderboard displays submission coverage and
uses the full release denominator. Every missing task receives zero. No placeholder
task JSON is required.

Expected counts for `pce-1.0` are:

| Level | Tasks |
|---|---:|
| L0 | 58 |
| L1 | 58 |
| L2 | 150 |
| L3 | 2,324 |

## L0/L1 full_quality is rejected

Every submitted task must have numeric values for Correctness, Faithfulness,
Architecture, and Health, plus a numeric `overall_score`. Use
`correctness_only` when only functional tests were scored.

In correctness-only native results, Faithfulness, Architecture, and Health are
normally null. Such records are valid for the execution leaderboard.

## L2/L3 score consistency fails

Check the native fields against:

```text
compile_score = 0.5 if compile_passed else 0.0
test_score    = 0.5 * test_pass_ratio if compile_passed else 0.0
score         = compile_score + test_score
full_passed   = passed
```

Rerun aggregation with the same evaluator revision. The validator tolerates
native numeric rounding and rejects material differences.

## Test or scoring modes are mixed

One submission must describe one evaluation configuration. L0/L1 use
`testMode: "blackbox"` and either `correctness_only` or `full_quality`. L2/L3 use
`scoringMode: "execution"` and one consistent test mode: `both`, `whitebox`, or
`blackbox`.

Separate mixed runs into independent submissions.

## Logs exceed repository limits

Keep no more than 5 MB per optional log and 20 MB across `logs/`. Remove redundant
output. Per-task `stdout`, `stderr`, and `test_details` already remain in native
results.

## A secret scanner reports a credential

Stop publication, rotate the credential, remove it from branch history, and rerun
the evaluation in a sanitized environment when the value appears in a native task
record. A deletion commit alone does not remove a secret from Git history.

## The Pull Request changes disallowed files

Create a clean branch and add one new directory under `community-results/` only.
Do not combine a result submission with documentation, evaluator, website, or
workflow changes.

## The GitHub account does not match

The path component `<github-user>` and `submitter.github` must identify the Pull
Request author. If a maintainer submits on another person's behalf, explain the
delegation in the Pull Request and in `notes`.
