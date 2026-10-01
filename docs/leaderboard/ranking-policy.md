# Ranking Policy

## 1. Tracks and provenance

PolyCodeEval maintains separate leaderboards for L0, L1, L2, and L3. Each track
provides an overall view and per-language views. Scores from different task
levels are not combined.

Entries have one of two provenance labels:

- **Maintainer baseline**: a result produced and preserved by the PolyCodeEval
  maintainers.
- **Community self-evaluated**: a result produced and evaluated by a participant,
  then accepted through a maintainer-reviewed Pull Request.

The provenance label does not change metric computation. A maintainer-reviewed
community result has passed repository validation and metadata review. It has not
necessarily been rerun by the maintainers.

## 2. Fixed benchmark denominators

Release `pce-1.0` defines the following denominators:

| Level | Expected tasks |
|---|---:|
| L0 | 58 |
| L1 | 58 |
| L2 | 150 |
| L3 | 2,324 |

Partial submissions are eligible for publication. The leaderboard reports both
submission coverage and fixed-denominator metrics:

```text
submission coverage = submitted valid task IDs / expected task IDs
```

Every missing task contributes:

```text
build success        = 0
full pass            = 0
test-pass ratio      = 0
execution score      = 0
correctness          = 0
quality dimensions   = 0, when full_quality applies
```

The submitted-task summary remains available for audit. It never replaces the
fixed-denominator score used for ranking.

## 3. L0 and L1 execution metrics

Correctness is derived from parsed functional tests and reported on the `[0, 5]`
scale:

```text
correctness = 5 * tests_passed / tests_total
```

When no tests are parsed, full-quality evaluation follows the task-level `passed`
state and assigns `5` to a successful task. The correctness-only execution path
assigns `0` because no parsed functional-test evidence is available.

The execution view reports:

- **Full-pass rate**: tasks with `passed = true` divided by the fixed denominator.
- **Build-success rate**: tasks with an accepted successful build status, a
  task-level pass, or parsed passing tests, divided by the fixed denominator.
- **Average correctness**: sum of task correctness values divided by the fixed
  denominator.
- **Conditional test-pass ratio**: arithmetic mean of task test-pass ratios among
  submitted build-successful tasks. This diagnostic metric is displayed
  separately from fixed-denominator metrics.

L0 and L1 accept two scoring modes:

- `correctness_only`: publishes execution metrics and skips the judge-dependent
  Faithfulness and Architecture dimensions and the static-analysis Health
  dimension.
- `full_quality`: publishes execution metrics and the four-dimensional quality
  result. Every submitted task must contain complete Correctness, Faithfulness,
  Architecture, and Health values. Missing benchmark tasks contribute zero to the
  fixed-denominator quality aggregates.

For `full_quality`, the native evaluator computes:

```text
overall = 0.40 * Correctness
        + 0.25 * Faithfulness
        + 0.25 * Architecture
        + 0.10 * Health
```

All dimensions use the `[0, 5]` scale. The quality view is separate from the
default execution ranking.

## 4. L2 and L3 execution metrics

For one submitted task:

```text
compile_score = 0.5 if compile_passed else 0.0
test_score    = 0.5 * test_pass_ratio if compile_passed else 0.0
score         = compile_score + test_score
```

The leaderboard reports:

- **Full-pass rate**: tasks with `full_passed = true` divided by the fixed
  denominator.
- **Build-success rate**: tasks with `compile_passed = true` divided by the fixed
  denominator.
- **Execution score**: sum of task `score` values divided by the fixed
  denominator.
- **Conditional test-pass ratio**: arithmetic mean of `test_pass_ratio` among
  submitted build-successful tasks. This value describes test behavior after a
  successful build and does not receive zero-filled missing tasks.

The evaluator marks a task as build-successful when the underlying command passes
or parseable tests are observed. `full_passed` follows the evaluator's task-level
`passed` result.

## 5. Default ordering

Within one benchmark version, level, and language scope, the execution ranking is
ordered by:

1. full-pass rate, descending;
2. average correctness for L0/L1 or execution score for L2/L3, descending;
3. build-success rate, descending;
4. immutable submission identifier, ascending.

The L0/L1 full-quality view is ordered by:

1. overall score, descending;
2. Correctness, descending;
3. Faithfulness, descending;
4. Architecture, descending;
5. Health, descending;
6. immutable submission identifier, ascending.

Ordering uses unrounded values. Displayed values may be rounded.

## 6. Comparable configurations

Every entry displays its benchmark version, PolyCodeEval commit, test mode,
scoring mode, method version, and model version. Environment differences do not
automatically prevent publication. Material differences may receive a review
note so readers can interpret comparability.

`correctness_only` entries appear only in the L0/L1 execution view.
`full_quality` entries appear in both execution and quality views. L2/L3 entries
use `execution`.

## 7. Corrections and withdrawal

Maintainers may flag or withdraw a result when its metadata is misleading, its
native records are inconsistent, the declared benchmark version is incorrect, or
the submission violates repository policy. Corrections use a new Pull Request so
that prior files and review history remain visible.
