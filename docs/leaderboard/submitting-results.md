# Submitting Results

This guide describes how to publish a self-evaluated PolyCodeEval result through
a GitHub Pull Request. Run generation and evaluation locally. Submit the native
evaluation output, one `submission.json`, and optional text logs. Never submit
generated code.

## 1. Complete generation locally

Generate the artifacts required by one PolyCodeEval level and retain them outside
the community-results directory. Generated artifacts are inputs to the evaluator
only.

One submission represents exactly one combination of:

- benchmark version;
- task level;
- generation method and method version;
- model and model version;
- evaluation configuration.

Use a separate submission for every level or configuration.

## 2. Run the official evaluator

Use the evaluator's `--output` option to create a dedicated result directory.
The following commands show the common precomputed-solver form:

```bash
python scripts/run_l0_eval.py \
  --all \
  --solver precomputed:/path/to/generated-artifacts \
  --output /path/to/evaluation-output
```

```bash
python scripts/run_l1_eval.py \
  --all \
  --solver precomputed:/path/to/generated-artifacts \
  --output /path/to/evaluation-output
```

```bash
python scripts/run_l2_eval.py \
  --all \
  --solver precomputed:/path/to/generated-artifacts \
  --tests both \
  --output /path/to/evaluation-output
```

```bash
python scripts/run_l3_eval.py \
  --all \
  --solver precomputed:/path/to/generated-artifacts \
  --tests both \
  --output /path/to/evaluation-output
```

Add `--correctness-only` to L0 or L1 when Faithfulness, Architecture, and Health
are not being computed. L0 and L1 always use functional black-box tests. L2 and
L3 accept `both`, `whitebox`, or `blackbox` through `--tests`; record the selected
mode in `submission.json`.

The evaluator writes:

```text
evaluation-output/
  summary.json
  <language>/
    <project>/
      <task>.json
```

Do not rename task files or edit evaluator fields after the run.

## 3. Create submission.json

Create the single additional required file beside `evaluation/`. The metadata
identifies the participant, method, model, benchmark, evaluator revision, and
scoring mode. See [Submission JSON reference](submission-json-reference.md) for
the complete schema.

The minimum L3 example is:

```json
{
  "schemaVersion": "2",
  "benchmarkVersion": "pce-1.0",
  "level": "L3",
  "submissionName": "Method X with Model Y",
  "submitter": { "github": "example-user" },
  "method": { "name": "Method X", "version": "1.0" },
  "model": { "name": "Model Y", "version": "2026-09" },
  "evaluation": {
    "polycodeevalCommit": "0123456789abcdef0123456789abcdef01234567",
    "testMode": "both",
    "scoringMode": "execution"
  }
}
```

## 4. Assemble the Pull Request directory

Copy the native evaluator output without changing its contents:

```text
community-results/
  pce-1.0/
    <level>/
      <github-user>/
        <submission-id>/
          submission.json
          evaluation/
            summary.json
            <language>/<project>/<task>.json
          logs/                              # optional
```

Directory rules:

- `<level>` is exactly `L0`, `L1`, `L2`, or `L3`.
- `<github-user>` matches `submitter.github`.
- `<submission-id>` uses lowercase ASCII letters, numbers, and hyphens.
- `evaluation/` contains only the native result directory.
- `logs/` contains optional text evidence and may be omitted.

## 5. Validate before publishing

Use the Submit Results page to select a ZIP containing the structure above. The
browser reads files locally, recomputes metrics, reports missing tasks, and checks
the metadata. Browser inspection does not upload or execute files.

Review the validation report and the fixed-denominator score. A partial result is
valid; every missing task receives zero in the public ranking.

## 6. Inspect public content

Before opening a Pull Request:

- read every `submission.json` field;
- inspect `summary.json` and representative task results;
- search `stdout`, `stderr`, `error`, commands, and optional logs for secrets;
- remove optional logs that add no audit value;
- confirm that generated code, datasets, dependencies, and build products are
  absent.

Use the [privacy checklist](privacy-checklist.md) for the final review.

## 7. Open the Pull Request

Fork the repository, create a branch, add one new submission directory, and open
a Pull Request. A submission Pull Request must not modify existing community
results, evaluator code, website logic, or workflow definitions.

Suggested title:

```text
[Leaderboard][L3] Method X with Model Y
```

Include the following in the Pull Request description:

- benchmark version and level;
- method and model;
- submitted task count;
- scoring and test modes;
- known deviations from the declared evaluation command;
- confirmation that generated code and credentials are absent.

Automated checks validate the directory, task identities, native fields,
recomputed aggregates, optional logs, and changed-file scope. A maintainer then
reviews the result. Accepted community entries are labeled **Self-evaluated,
maintainer-reviewed**.
