# PolyCodeEval Website

This directory contains the static, English-language benchmark and leaderboard site published at
<https://polycodeeval.github.io/PolyCodeEval/>.

The site provides dataset, result, task, quality, statistical, token, prompt,
leaderboard, download, and evaluated-result submission pages. Submission
prechecks run entirely in the browser: native evaluator JSON and optional text
logs are inspected locally, and no submitted content is uploaded or executed.

## Source organization

Page-specific components, data loading, types, validation, and styles live in
`src/pages/<page>/`. Shared visual primitives and cross-page data contracts live
in `src/shared/`. Static snapshots follow the same feature-oriented structure
under `public/data/`. Python exporters are split by output feature under
`tools/exporters/`, with `tools/export_data.py` as the sole export entry point.

## Local development

```bash
npm ci
npm run dev
```

Vite serves the application under the same `/PolyCodeEval/` base path used by
GitHub Pages.

## Data snapshot

The browser reads compact JSON snapshots from `public/data/`. The snapshots are
derived from canonical experiment results and accepted community pull requests;
the website does not scan the full result archive at runtime.

Regenerate and verify the snapshot from the repository root:

```bash
python3 website/tools/export_data.py
python3 website/tools/validate_data.py
```

The validator checks the canonical configuration map, task counts, paired-analysis
scope, source links, and aggregate consistency. Generated snapshots should be
reviewed before they are committed.

## Verification

```bash
npm run check
npm run build
```

`npm run check` runs TypeScript validation, exporter unit tests, and snapshot
validation. The GitHub Pages workflow repeats these checks before deployment.
Browser tests are defined under `tests/e2e/` and run in the deployment workflow.

## Deployment

The workflow in `.github/workflows/deploy-pages.yml` builds the committed snapshot
and deploys `dist/` through GitHub Pages. Repository Pages settings must use
**GitHub Actions** as the source.
