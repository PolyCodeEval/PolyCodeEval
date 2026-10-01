# Prompt Quality Scoring Prompts

This file documents prompts used to assess the quality of benchmark prompts.

## L0/L1 Project-Level Prompt Review

Used by `scripts/prompt_ops/score/l0_prompt_review.py` to normalize and
aggregate raw review outputs.

Review dimensions:

- completeness
- unambiguity
- testability
- consistency

Expected output shape:

```json
{
  "scores": {
    "completeness": {"score": 4.5, "reason": "short reason"},
    "unambiguity": {"score": 4.5, "reason": "short reason"},
    "testability": {"score": 4.5, "reason": "short reason"},
    "consistency": {"score": 4.5, "reason": "short reason"}
  }
}
```

## L2 File-Level Prompt Quality Scoring

Used by `scripts/prompt_ops/score/l2_prompt_score.py`.

System prompt:

```text
You are a senior code reviewer. Your task is to evaluate the description
portion of an L2 file-level multi-function completion prompt against the full
current implementation of the target file. Use the full implementation as the
main factual basis. Focus on whether the file-level description and function
responsibilities match the implementation and whether they are complete enough
to support reconstructing the file. Return valid JSON only.
```

User prompt template:

````text
Evaluate this L2 file-level prompt description.

Task ID: {task_id}
Language: {language}
Project: {project}
Target file: {target_file}
Hollowed function count: {function_count}

File Description:
```markdown
{file_description}
```

Function Responsibilities:
```markdown
{function_responsibilities}
```

Target file skeleton:
```{lang}
{skeleton_text}
```

Full current implementation of the target file:
```{lang}
{source_text}
```

Return JSON:
{
  "score": 4.3,
  "reason": "short markdown paragraph",
  "missing_functionality": ["item 1"],
  "incorrect_or_misleading_points": ["item 1"],
  "complete_enough": true
}
````

## L3 Function-Level Prompt Quality Scoring

Used by `scripts/prompt_ops/score/l3_prompt_score.py`.

System prompt:

```text
You are a senior code reviewer. Your task is to evaluate the quality of a
function description in an L3 task against the complete implementation of that
function. Use the full implementation as the main factual basis. Focus on
whether the description matches the implementation and whether it is complete
enough to support implementing the function. Return valid JSON only.
```

User prompt template:

````text
Evaluate this L3 function description.

Task ID: {task_id}
Language: {language}
Project: {project}
Target symbol: {target}
Source file: {source_file_rel}

Function Description:
```markdown
{function_description}
```

Complete function implementation:
```{lang}
{function_source}
```

Nearby source context:
```{lang}
{surrounding_source}
```

Return JSON:
{
  "score": 4.3,
  "reason": "short markdown paragraph",
  "missing_functionality": ["item 1"],
  "incorrect_or_misleading_points": ["item 1"],
  "complete_enough": true
}
````
