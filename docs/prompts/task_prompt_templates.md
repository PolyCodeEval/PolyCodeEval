# Task Prompt Templates

This file documents the task prompts that are written as `prompt.md` inside
PolyCodeEval task directories.

## L0 Project-Level Generation

Used by `scripts/slicer/l0_task_builder.py`.

```text
# Task

You are given a product requirements document for a {language} project.
Generate the complete project source code from scratch, including build
configuration files.
Return your answer as a sequence of file sections, each starting with:

===FILE: relative/path/to/file===

followed by the complete file content. Do not wrap files in markdown fences.
Do not generate test files.

# Project Requirements

{prd_text}
```

## L1 Project-Level Generation With Skeleton

Used by `scripts/slicer/project_task_builder.py`.

```text
# Task

You are given the skeleton of a {language} project with {total_func_count}
function bodies replaced by `{stub}`.
Implement every stubbed function. Return your answer as a sequence of file
sections, each starting with a delimiter line:

===FILE: relative/path/to/file===

followed by the complete file content.
Do not wrap individual files in markdown fences.

# Project Requirements

{prd_text}

# Project Skeleton

## {relative_path}

{hollowed_file_content}
```

## L2 File-Level Completion

The original local construction path is implemented in
`scripts/slicer/file_task_builder.py`. The formal construction path in
`scripts/construction/prompt_descriptions.py` writes the same task target with
additional generated description sections.

Final prompt structure:

```text
# Task

Generate the complete contents of `{source_file_rel}`.
The file skeleton below shows the structure with function bodies replaced by
stubs. Fill in all function bodies and return the entire file.

# File Description

- {file-level behavior bullet}

# Function Responsibilities

## {hollowed_function_signature}

- {function responsibility bullet}

# Related Context

## Target File (Skeleton)

### {source_file_rel}

{skeleton_text}

## Hollowed Function Signatures

- `{signature}`
```

## L3 Function-Level Completion

Used by `scripts/slicer/prompt_builder.py` and the formal construction path in
`scripts/construction/prompt_descriptions.py`.

Final prompt structure:

```text
# Task
Complete the body of the `{func_name}` function.
Return only the function body. Do not change the signature.

# Function Description

- {function behavior bullet}

# Related Context

## Signature

{signature}

## Inputs / Outputs

- Input parameter: `{parameter}`
- Output format: returns `{return_type}`.

## Called Function Signatures

### {path} - {symbol}

{called_function_signature}
```

