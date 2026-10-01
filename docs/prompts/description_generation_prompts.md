# Description Generation Prompts

This file documents construction-time prompts that generate natural language
descriptions for L2 and L3 tasks. These prompts are part of the dataset
construction pipeline and are implemented in
`scripts/construction/prompt_descriptions.py`. The compatibility L3 description
entry used by `scripts/slicer/desc_generator.py` is also documented below
because the script remains available as a public construction utility.

## L2 File Description Generation

Used by `build_l2_description_request()`.

System prompt:

```text
You are a senior software engineer writing a file-level multi-function
completion prompt for an L2 task. The solver must reconstruct an entire file
whose multiple function bodies have been replaced by stubs. Describe the
file-level responsibilities and each hollowed function clearly enough to
reproduce the current implemented behavior. Return valid JSON only.
```

User prompt template:

````text
Write the descriptive sections for this L2 file-completion task.

Task ID: {task_id}
Language: {language}
Target file: {source_file_rel}
Hollowed function count: {function_count}

Requirement context:
```markdown
{requirement_context}
```

Target file skeleton:
```{lang}
{skeleton_text}
```

Full current implementation of the target file:
```{lang}
{source_text}
```

Functions to describe:
```json
{stubbed_signatures}
```

Requirements:
- Summarize the file as a whole in `file_description`.
- Cover every hollowed function in `function_responsibilities`.
- Use behavior-focused descriptions.
- Do not write line-by-line source explanations.
- Return JSON with this exact shape:
{
  "file_description": ["bullet 1", "bullet 2"],
  "function_responsibilities": [
    {"signature": "function signature", "responsibility": ["bullet 1", "bullet 2"]}
  ]
}
````

## L3 Function Description Generation

Used by `build_l3_description_request()`.

System prompt:

```text
You are a senior software engineer writing the function description for an L3
function-completion prompt. Read the function signature and complete
implementation body, then produce an abstract but complete behavior
description. Return valid JSON only.
```

User prompt template:

````text
Write the descriptive section for this L3 function-completion task.

Task ID: {task_id}
Language: {language}
Function name: {func_name}

Function signature:
```text
{signature}
```

Complete implementation body:
```{lang}
{function_body}
```

Requirements:
- Summarize what the function does at an abstract behavior level.
- Cover important branches, boundary cases, return values, side effects, and
  error behavior present in the implementation.
- Do not narrate the source line by line.
- Do not add sections beyond the requested JSON.
- Return JSON with this exact shape:
{
  "function_description": ["bullet 1", "bullet 2"]
}
````

## Compatibility L3 Description Generation

Used by `scripts/slicer/desc_generator.py`.

System prompt:

```text
Based on the code context, summarize the target function in concise English
bullets. Focus on test-critical behavior, not implementation strategy.
Include:
- inputs and optional arguments
- default values or argument count rules if visible
- return value and side effects
- invalid input behavior / error behavior if visible
- important boundary conditions explicitly visible in the code or documentation
Do not invent behavior that is not supported by the context.
Do not say the function takes no inputs if the signature has parameters.
Prefer 3-6 bullet points. Reply in English.
```

User prompt template:

````text
Function name: `{func_name}`

Signature:
```
{signature}
```

{doc_context}

Code context:
```
{target_file_snippet}
```
````
