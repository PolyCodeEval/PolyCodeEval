# PolyCodeEval

A multi-language, multi-granularity, multi-difficulty benchmark for evaluating LLM project-level code generation.

## Overview

PolyCodeEval evaluates code generation models across a three-dimensional space:

- **Multi-Granularity**: 4 levels from full project generation to single function completion
- **Multi-Difficulty**: Easy / Medium / Hard, quantified by code scale, topology complexity, stack breadth, and requirement abstraction
- **Multi-Language**: 5 languages spanning dynamic, static, and systems programming paradigms

All granularity levels are derived from the same Oracle repository. L0/L1 evaluate project-level generation, while L2/L3 evaluate sliced local generation by integrating generated artifacts back into the corresponding Oracle-derived project structure.

## Granularity Levels

| Level | Model Input | Generated Code | Primary Target |
|:---:|:---|:---|:---|
| **L0** | PRD only | Entire project from scratch | Coding agents and multi-agent frameworks |
| **L1** | PRD + project skeleton | Entire project | Project-level generation with skeleton constraints |
| **L2** | File-level task prompt + target file skeleton + related context | Complete single file | File-level completion |
| **L3** | Function-level task prompt + target signature + structured interface context | Function body | Function-level completion |

## Evaluation Modes (Settings)

Evaluation modes are an orthogonal dimension to granularity levels. They control what cross-file context is provided in the prompt, without changing the task definition:

| Mode | Context Provided | Purpose |
|:---:|:---|:---|
| `oracle-context` | Real cross-file dependencies (imports, callers, callees) | Upper-bound measurement — how well can the model perform with perfect context? |
| `no-context` | Target file/function only, no cross-file information | Lower-bound measurement — pure code generation ability without retrieval |
| `self-retrieval` | Repository file listing exposed; tool retrieves its own context | Measures the model/tool's retrieval + generation pipeline end-to-end |

Any granularity level (L1–L3) can be combined with any evaluation mode. L0 always operates in `no-context` mode (only PRD is given).

## Scoring

Four orthogonal dimensions with cross-validation between objective (C, H) and subjective (F, A) metrics:

| Dimension | Weight | Method |
|:---|:---:|:---|
| **Correctness** (C) | 0.40 | Automated testing (`pytest`, `JUnit5`, `Jest`, `go test`, `gtest`) in isolated Docker sandbox |
| **Faithfulness** (F) | 0.25 | LLM-as-a-Judge requirement coverage check against PRD |
| **Architecture** (A) | 0.25 | LLM-as-a-Judge design quality assessment (separation of concerns, extensibility, idiomatic practice) |
| **Health** (H) | 0.10 | Static analysis via language-specific linters + cyclomatic complexity |

**Score = 0.4C + 0.25F + 0.25A + 0.1H** (all dimensions scored 0–5)

## Language Support

| Language | Priority | Frameworks | Test Framework | Linter | Projects |
|:---|:---:|:---|:---|:---|:---:|
| Python | P0 | FastAPI / Django / Flask | `pytest` + `pytest-cov` | `flake8` / `pylint` / `mypy` / `radon` | 12 |
| Java | P0 | Spring Boot / Javalin | `JUnit5` + `Mockito` | `CheckStyle` / `PMD` / `SpotBugs` | 11 |
| JavaScript | P1 | Express / NestJS | `Jest` + `Supertest` | `ESLint` + `Prettier` | 11 |
| Go | P1 | Gin / Echo | `testing` + `testify` | `golangci-lint` | 12 |
| C++ | P2 | Tool/algorithm libraries | `Google Test` + `Google Mock` | `clang-format` / `cppcheck` / `clang-tidy` | 11 |
The public benchmark covers five languages. Full dataset statistics are reported in the paper and reproduced by scripts under `scripts/analysis/paper/`.

The framework uses a plugin architecture — each language implements four standardized interfaces (`Parser`, `Slicer`, `DockerSandbox`, `Linter`), all built on `tree-sitter` for unified AST parsing. Adding a new language requires no changes to the core framework.

All evaluation runs inside a single unified Docker image (`polycodeeval/unified:all`) that bundles every language environment — Python 3.11, GCC 12, Go 1.23, Java 8/11/17, and Node 14/18/20/22. The image is kept separate from the benchmark data; test suites are injected via volume mount at runtime.

## Project Structure

```
PolyCodeEval/
├── datasets/              # Lightweight metadata; full datasets are external
├── docker/                # Docker runner layer
│   ├── runner_lib.py      #   Shared utilities (image, cache, script building)
│   ├── build_images.py    #   Build the unified image
│   ├── scripts/
│   │   └── run_batch.py   #   Container-internal batch runner
│   └── images/
│       └── unified.Dockerfile  # All-language unified image
├── scripts/
│   ├── analysis/          # Paper table, figure, and significance scripts
│   ├── construction/      # Construction-pipeline notes
│   ├── coverage/          # Coverage parsing and reporting utilities
│   ├── prompt_ops/        # Active prompt-quality scoring code
│   ├── slicer/            # L2/L3 slicing and prompt-building utilities
│   └── run_*              # Generation, slicing, and evaluation entry points
├── finalresults/          # Final evaluation result JSON/CSV files for release
├── results/               # Local evaluation outputs and logs (git-ignored)
└── docs/                  # Public specifications, prompts, and usage guides
```

After dataset synchronization, each materialized project follows a standardized structure:

```
datasets/{lang}/{project_id}/
├── src/                   # Oracle source code (ground truth) + build entry points
├── tasks/                 # Pre-generated evaluation tasks (L1–L3)
│   └── {level}_{target}/
│       ├── task.json      #   Task definition and context references
│       └── hollowed/      #   Hollowed-out files (model input)
├── tests/                 # Test suite (never exposed to model)
├── docs/                  # PRD and architecture documents
│   ├── prd.md
│   └── architecture.md
└── config.json            # Runtime config (test commands, Docker image, etc.)
```

See [`datasets/README.md`](datasets/README.md) for the full data specification.

## Evaluation Workflow

1. **Generation**: Model receives the level-specific prompt and produces the requested artifact.
2. **Integration**: L0/L1 outputs are evaluated as project-level submissions; L2/L3 outputs are backfilled into the corresponding Oracle-derived project structure.
3. **Parallel Evaluation**: Four dimensions are assessed independently:
   - **C**: Tests run in Docker sandbox and report build success, full-pass rate, and related correctness metrics.
   - **F**: LLM judge compares generated code against PRD requirements
   - **A**: LLM judge reviews architecture quality
   - **H**: Static linters + complexity analyzers score code health
4. **Reporting**: Radar chart + per-dimension breakdown

## Getting Started

```bash
# Clone the repository
git clone https://github.com/your-org/PolyCodeEval.git
cd PolyCodeEval

# Fetch datasets from DockerHub (not tracked in git)
python docker/sync_datasets.py pull --all
# Or pull a single language: python docker/sync_datasets.py pull --language go

# Build the unified Docker image (Python + C++ + Go + Java + JS, all in one)
python docker/build_images.py

# Run all L0 blackbox tests in batch mode (single container, all projects)
python scripts/run_l0_eval.py --all --solver oracle --batch

# Run a single language
python scripts/run_l0_eval.py --language python --solver oracle --batch

# Run without batch mode (one container per task, parallel workers)
python scripts/run_l0_eval.py --all --solver oracle --workers 4

# Run L3 function-level evaluation (whitebox + blackbox by default)
python scripts/run_l3_eval.py --language go --solver oracle --workers 4

# Run L3 with whitebox tests only (legacy behavior)
python scripts/run_l3_eval.py --language go --solver oracle --tests whitebox
```

## Running Long Jobs with tmux

Evaluation runs can take hours. Use tmux to keep them alive after disconnecting.

```bash
# Start a new named session
tmux new-session -s eval

# Inside the session, run the evaluation
conda activate polycodeeval
python scripts/run_l3_eval.py --all --solver oracle --workers 8

# Detach from the session (keeps it running in background)
# Press: Ctrl+B, then D

# List running sessions
tmux ls

# Reattach to the session
tmux attach -t eval

# Run slicer and eval back-to-back in one session
tmux new-session -s pipeline -d
tmux send-keys -t pipeline "conda activate polycodeeval && python scripts/run_l3_slicer.py --all --skip-desc && python scripts/run_l3_eval.py --all --solver oracle --workers 8" Enter

# Split the window to monitor Docker while eval runs
tmux split-window -h -t eval
tmux send-keys -t eval "watch -n2 docker ps" Enter
```


Quick start:

```bash
docker build \
  -f docker/images/l3-oracle-smoke.Dockerfile \
  -t err404notfound/polycodeeval-l3-oracle-smoke:latest \
  .

python scripts/run_l3_eval.py \
  --task datasets/python/tinydb/tasks/L3_database____enter__ \
  --solver oracle \
  --docker-image err404notfound/polycodeeval-l3-oracle-smoke:latest
```



Projects are automatically classified into three tiers based on quantified metrics (LOC, dependency topology, stack breadth, requirement abstraction):

| Level | Files | Characteristics | Expected Pass Rate |
|:---:|:---:|:---|:---:|
| Easy | < 10 | Single responsibility, linear call graph, no external persistence | > 70% |
| Medium | 10–30 | Standard MVC architecture, single DB interaction | 40–70% |
| Hard | > 30 | Complex async/concurrency, deep call chains, circular dependencies | < 40% |

## License

TBD
