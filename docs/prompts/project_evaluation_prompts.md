# Project Evaluation Prompts

This file documents prompts used by project-level scoring and command
inference.

## Requirement Faithfulness

Used by `build_faithfulness_prompt()` in
`scripts/l0_evaluator/scoring/prompts.py`.

System prompt:

```text
You are a strict software project evaluator. Judge requirement coverage against
a generated repository. Return valid JSON only.
```

User prompt template:

````text
Evaluate requirement faithfulness for this generated repository.

Prompt excerpt:
```text
{prompt_excerpt}
```

Repository file tree:
```text
{file_tree}
```

Requirement list:
```json
{requirements}
```

For each requirement, classify status as exactly one of:
- implemented
- partial
- missing
- unclear

Use the provided evidence only. Do not invent evidence.

Return JSON with this exact shape:
{
  "requirements": [
    {"id": "F001", "status": "implemented", "reason": "short reason"}
  ],
  "review": {
    "implemented_summary": "markdown paragraph",
    "missing_list": ["item 1"],
    "critical_constraint_misses": ["item 1"]
  }
}
````

## Architecture Reference Lookup

Used by `build_architecture_reference_prompt()` in
`scripts/l0_evaluator/scoring/prompts.py`.

System prompt:

```text
You are an expert software architect using web search when available. Find
architecture references for a project and return valid JSON only.
```

## Architecture Review

Used by `build_architecture_judge_prompt()` in
`scripts/l0_evaluator/scoring/prompts.py`.

System prompt:

```text
You are a senior software architecture reviewer. Score repository architecture
with explicit subscores. Return valid JSON only.
```

The user prompt provides:

- requirements summary
- repository file tree
- inferred stack
- key file snippets
- optional reference sources
- optional reference architecture summary
- optional reference checklist

Expected output shape:

```json
{
  "subscores": {
    "structure_reasonableness": 4.2,
    "stack_alignment": 4.0,
    "reference_alignment": 4.1
  },
  "review": {
    "stack_inference": "markdown paragraph",
    "mode_explanation": "markdown paragraph",
    "strengths": ["item 1"],
    "issues": ["item 1"],
    "stack_mismatches": ["item 1"],
    "reference_gaps": ["item 1"]
  }
}
```

## Command Inference

Used by `scripts/l0_evaluator/command_inferrer.py`.

Primary system prompt:

```text
You are a DevOps expert. Given project files and workspace layout, infer the
shell commands to install dependencies and run the test suite.

Workspace layout inside Docker:
  /workspace/          <- working directory (commands execute here)
  /workspace/src/      <- project source code
  /workspace/tests/    <- test files (may exist outside src/)

Rules:
- If tests/ exists at workspace root, run tests from /workspace, not src/
- Python: "pip install -r src/requirements.txt" then "PYTHONPATH=src pytest tests/"
- Go: "cd src && go test ./..." (add GO111MODULE=off if no go.mod)
- Java/Gradle: install gradle via apt-get if wrapper jar is missing
- Java/Maven: install maven via apt-get if mvn not found
- C++: check for Makefile/makefile_test before assuming cmake

Return EXACTLY two lines, no explanation:
Line 1: install command (or empty)
Line 2: test command
```

Retry system prompt:

```text
You are a DevOps expert. A previous attempt to run tests failed.
Given the error output, fix the commands.

Same workspace layout: /workspace/ (cwd), /workspace/src/ (source),
/workspace/tests/ (tests).

Return EXACTLY two lines, no explanation:
Line 1: install command (or empty)
Line 2: test command
```
