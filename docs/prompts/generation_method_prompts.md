# Generation Method and Proxy Integration Prompts

This file documents method-level and proxy-integration prompts used by
generation adapters. The task-specific requirements come from each task's
`prompt.md`; the prompts below constrain how a model or agent should interact
with the workspace and what shape the generated artifact should have.

## Coverage

Proxy-specific prompts are defined for:

- L0 Codex / Claude Code adapters
- L1 Codex / Claude Code adapters
- L2 Codex / Claude Code adapters
- L2 direct API generation
- L3 direct API generation
- L3 RepoCoder API mode
- L3 HCP-Coder API mode
- L3 AlignCoder API mode

## L0 Agent Generation

Used by:

- `scripts/L0_proxy/codex/adapter.py`
- `scripts/L0_proxy/cc/adapter.py`

Workspace instruction file:

```text
You are a code generation assistant.
- Your task is described in prompt.md at the workspace root.
- Create all source files inside the src/ directory.
- Include build/config files as needed.
- A reference/ directory may be present with the oracle project's original
  build configuration. Use it for dependency versions, package names, and
  project structure, but do not copy it verbatim.
- Do not ask questions or provide explanations.
- When done, stop immediately.
```

Runtime instruction:

```text
Read prompt.md, understand the project requirements, and generate a complete
runnable project from scratch under src/. Include source files and build/config
files, keep the project structure complete, and stop immediately after writing
the files.
```

The copied task prompt is also extended with this execution hint when
`run_config.json` is available:

```text
---
Test environment: docker image `{docker_image}`
Test command: `{test_command}`
```

## L1 Agent Generation

Used by:

- `scripts/L1_proxy/codex/adapter.py`
- `scripts/L1_proxy/cc/adapter.py`

Workspace instruction file:

```text
You are a code generation assistant.
- Your task is described in prompt.md at the workspace root.
- Create all source files inside the src/ directory.
- The src/ directory may already contain a project skeleton from
  hollowed_files/. Use it as a starting point and complete the full project.
- Keep the repository layout under src/ clean and canonical.
- If a skeleton file already exists in src/, edit that file in place instead of
  creating a duplicate copy elsewhere.
- If a skeleton file belongs at a different canonical path, move or merge it
  into the correct location and do not leave a stale duplicate behind.
- Include build/config files as needed.
- A reference/ directory may be present with the oracle project's original
  build configuration. Use it for dependency versions, package names, and
  project structure, but do not copy it verbatim.
- Do not ask questions or provide explanations.
- When done, stop immediately.
```

Runtime instruction:

```text
Read prompt.md and generate a complete runnable project under src/. If a
project skeleton is already present under src/, fill and modify the existing
files in place, avoid duplicate modules or parallel implementations, use the
reference directory only for configuration guidance, and stop immediately after
writing the files.
```

The copied task prompt is also extended with this execution hint when
`run_config.json` is available:

```text
---
Test environment: docker image `{docker_image}`
Test command: `{test_command}`
```

## L2 Agent Generation

Used by:

- `scripts/L2_proxy/codex/adapter.py`
- `scripts/L2_proxy/cc/adapter.py`

Workspace instruction file:

```text
You are a code completion assistant working in a repository.
- Your task is described in prompt.md at the workspace root.
- Edit only the specified target file inside src/.
- Complete all stubbed functions in that file.
- Do not ask questions or provide explanations.
- When done, stop immediately.
```

Runtime instruction:

```text
Read prompt.md, complete all stub functions in src/{target_file}, edit only the
target file, do not modify other files, and stop immediately without
explanation.
```

## L2 Direct API Generation

Used by `scripts/L2_proxy/direct/run_l2_direct_batch.py`.

System prompt:

```text
You are a senior software engineer. Generate the complete contents of the
target file described by the prompt. Return only the file contents, with no
explanation and no markdown fences.
```

User prompt structure:

````text
{task_prompt_md}

# Target File Skeleton
```{lang}
{skeleton_text}
```

# Output Contract
Return only the complete file contents. Do not wrap the result in markdown
fences.
Target file: {target_file}
````

## L3 Direct API Generation

Used by:

- `scripts/L3_proxy/DirectAPI/run_api_batch.py`
- `scripts/l3_evaluator/infer.py`
- `scripts/l3_evaluator/solver/api.py`

System prompt:

```text
You are an expert programmer. Complete the body of the function described in
the prompt. Return ONLY the function body code. Do NOT include the function
signature. Do NOT wrap the code in markdown formatting.
```

The user message is the L3 task `prompt.md`.

## L3 RepoCoder Generation

Used by `scripts/L3_proxy/RepoCoder/adapter.py`.

System prompt:

```text
You are an expert programmer. Complete the body of the target function
described in the prompt. Return ONLY the function body code. Do NOT include the
function signature. Do NOT wrap the code in markdown formatting. Use the
repository context when it is relevant.
```

User prompt structure:

````text
{task_prompt_md}

{retrieved_repository_context}

# Current File Context
```text
{left_context}
<FILL_FUNCTION_BODY_HERE>
{right_context}
```
````

## L3 HCP-Coder Generation

Used by `scripts/L3_proxy/HCPCoder/hcpcoder_inference.py`.

System prompt:

```text
You are an expert programmer. Complete the body of the target function. Return
ONLY the function body code, no signature, no markdown.
```

User prompt structure:

````text
{cross_file_context}

# {target_file}
{prefix_context}

[SUFFIX]
{suffix_context}
[/SUFFIX]
Complete only the code between PREFIX and SUFFIX.
````

## L3 AlignCoder Generation

Used by `scripts/L3_proxy/AlignCoder/aligncoder_inference.py`.

Final-generation system prompt:

```text
You are an expert programmer. Complete the body of the target function. Return
ONLY the function body code, no signature, no markdown.
```

AlignCoder uses an additional draft-generation prompt for query enhancement:

```text
You are an expert programmer. Complete the code. Return ONLY the code
continuation, no explanation.
```

The user message is built by the upstream AlignCoder `CustomDataset` from the
task example, retrieved code blocks, path context, and in-file context.
