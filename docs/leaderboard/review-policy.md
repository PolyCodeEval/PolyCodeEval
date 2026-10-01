# Review Policy

Community leaderboard entries are self-evaluated results submitted through GitHub
Pull Requests. Publication requires automated consistency checks and maintainer
review.

## Pull Request boundaries

One Pull Request adds one new directory under:

```text
community-results/pce-1.0/<level>/<github-user>/<submission-id>/
```

A community-result Pull Request may add:

- one `submission.json`;
- one native `evaluation/` directory;
- one optional `logs/` directory.

It may not modify:

- an existing community submission;
- benchmark tasks or tests;
- evaluator or aggregation code;
- website ranking logic;
- GitHub workflow definitions;
- maintainer baseline results.

Corrections to an accepted result use a separate Pull Request and retain the
history of the original submission.

## Automated checks

The submission check verifies:

1. the changed-file scope and single-submission rule;
2. the `submission.json` schema and directory identity;
3. benchmark version, level, task IDs, and task-path consistency;
4. unique task records and valid native JSON fields;
5. test mode and scoring mode consistency;
6. native `summary.json` values against submitted task files;
7. fixed-denominator aggregates and missing-task zero filling;
8. `full_quality` eligibility for L0/L1;
9. optional log extensions and size limits;
10. prohibited generated artifacts and common secret patterns.

The check reports:

- submitted, expected, and missing task counts;
- submission coverage;
- overall and per-language execution metrics;
- L0/L1 quality eligibility and quality metrics when available;
- differences between native and recomputed summaries;
- warnings about environment or metadata;
- validation errors that block merging.

Automated checks read evaluation files. They do not execute generated code and do
not rerun tests.

## Maintainer review

Maintainers review:

- method, model, submitter, and affiliation metadata;
- benchmark commit, test mode, and scoring mode;
- validation warnings and unusual score distributions;
- the absence of generated code and unrelated repository changes;
- representative `stdout`, `stderr`, `error`, and test-detail records;
- optional logs when they are needed to understand an anomaly;
- disclosed deviations or limitations.

Maintainers may request clarification, corrected metadata, removal of sensitive
content, or a new evaluation when the available evidence is insufficient.

## Provenance label

An accepted community entry is published as:

```text
Community self-evaluated · Maintainer-reviewed
```

This label means the participant ran the evaluator and maintainers reviewed the
submitted records. It does not claim independent reproduction or server-side
evaluation.

## Grounds for rejection or withdrawal

A result may be rejected, flagged, or withdrawn for:

- an invalid or unverifiable benchmark revision;
- inconsistent native records or aggregates;
- misleading method, model, or scoring metadata;
- generated code or prohibited large artifacts in the Pull Request;
- credentials, private data, or third-party confidential material;
- unauthorized modification of existing submissions or evaluation logic;
- licensing or conduct concerns;
- a confirmed evaluator defect that materially changes the score.

The repository history records the decision and any subsequent correction.
