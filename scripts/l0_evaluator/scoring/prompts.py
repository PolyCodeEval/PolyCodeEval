"""Prompt builders for L0 scoring."""

from __future__ import annotations

from .repo_snapshot import dump_json_block


def build_faithfulness_prompt(
    *,
    prompt_excerpt: str,
    file_tree: str,
    requirements: list[dict],
) -> tuple[str, str]:
    system = (
        "You are a strict software project evaluator. "
        "Judge requirement coverage against a generated repository. "
        "Return valid JSON only."
    )
    user = f"""Evaluate requirement faithfulness for this generated repository.

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
{dump_json_block(requirements)}
```

For each requirement, classify status as exactly one of:
- implemented
- partial
- missing
- unclear

Use the provided evidence only. Do not invent evidence.

Return JSON with this exact shape:
{{
  "requirements": [
    {{
      "id": "F001",
      "status": "implemented",
      "reason": "short reason"
    }}
  ],
  "review": {{
    "implemented_summary": "markdown paragraph",
    "missing_list": ["item 1"],
    "critical_constraint_misses": ["item 1"]
  }}
}}
"""
    return system, user


def build_codex_faithfulness_analysis_prompt(
    *,
    prompt_excerpt: str,
    file_tree: str,
    requirements: list[dict],
) -> str:
    return f"""你现在在一个评分工作区中。

请读取并核对以下内容：
- `prompt.md`: 原始任务描述
- `repo/`: 待评仓库
- `task.json`: 辅助任务元信息

All judgments must be grounded in repository contents that are actually visible in the workspace.
Do not speculate.
You may use the summaries below to navigate more quickly, but your final decision must be based on the actual contents of `prompt.md` and `repo/`.

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
{dump_json_block(requirements)}
```

评分任务：
1. Evaluate each requirement one by one.
2. The `status` for every requirement must be exactly one of:
   - implemented
   - partial
   - missing
   - unclear
3. Mark a requirement as `implemented` only when there is explicit repository evidence.
4. Do not treat similar naming or similar keywords as sufficient evidence of implementation.

只返回 JSON：
{{
  "requirements": [
    {{
      "id": "F001",
      "status": "implemented",
      "reason": "short reason"
    }}
  ],
  "review": {{
    "implemented_summary": "markdown paragraph",
    "missing_list": ["item 1"],
    "critical_constraint_misses": ["item 1"]
  }}
}}
"""


def build_architecture_reference_prompt(
    *,
    prompt_excerpt: str,
    file_tree: str,
    stack_profile: dict,
) -> tuple[str, str]:
    system = (
        "You are an expert software architect using web search when available. "
        "Find architecture references for a project and return valid JSON only."
    )
    user = f"""Use the project requirements, inferred stack, and repository file tree below.
Find good architecture references for a similar project built with the same stack.

Requirements summary:
```text
{prompt_excerpt}
```

Inferred stack:
```json
{dump_json_block(stack_profile)}
```

Repository file tree:
```text
{file_tree}
```

Return JSON only with this exact shape:
{{
  "relevance_ok": true,
  "reference_sources": [
    {{
      "title": "source title",
      "url": "https://..."
    }}
  ],
  "reference_architecture_summary": "short markdown summary",
  "reference_checklist": [
    "check item 1",
    "check item 2"
  ],
  "notes": "short reason if references are weak"
}}

If you cannot find a good architecture reference, set "relevance_ok" to false and keep arrays empty.
"""
    return system, user


def build_architecture_judge_prompt(
    *,
    prompt_excerpt: str,
    file_tree: str,
    stack_profile: dict,
    snippets: list[dict],
    reference_mode: str,
    reference_sources: list[dict],
    reference_architecture_summary: str,
    reference_checklist: list[str],
) -> tuple[str, str]:
    system = (
        "You are a senior software architecture reviewer. "
        "Score repository architecture with explicit subscores. "
        "Return valid JSON only."
    )
    user = f"""Evaluate the generated repository architecture.

Reference mode: {reference_mode}

Requirements summary:
```text
{prompt_excerpt}
```

Repository file tree:
```text
{file_tree}
```

Inferred stack:
```json
{dump_json_block(stack_profile)}
```

Key file snippets:
```json
{dump_json_block(snippets)}
```

Reference sources:
```json
{dump_json_block(reference_sources)}
```

Reference architecture summary:
```text
{reference_architecture_summary}
```

Reference checklist:
```json
{dump_json_block(reference_checklist)}
```

Return JSON only:
{{
  "subscores": {{
    "structure_reasonableness": 4.2,
    "stack_alignment": 4.0,
    "reference_alignment": 4.1
  }},
  "review": {{
    "stack_inference": "markdown paragraph",
    "mode_explanation": "markdown paragraph",
    "strengths": ["item 1"],
    "issues": ["item 1"],
    "stack_mismatches": ["item 1"],
    "reference_gaps": ["item 1"]
  }}
}}

Scoring rubric:
- structure_reasonableness: clarity of separation, layering, repository organization.
- stack_alignment: whether the structure matches the inferred stack's typical practices.
- reference_alignment: compare against online references when available; otherwise self-reference based on expert judgment.

Important scoring rule:
- Every subscore must be on a 0-5 scale, not 0-1.
- Use one decimal place when needed.
"""
    return system, user


def build_codex_architecture_analysis_prompt(
    *,
    prompt_excerpt: str,
    file_tree: str,
    stack_profile: dict,
    snippets: list[dict],
) -> str:
    return f"""你现在在一个评分工作区中。

请读取并评估以下内容：
- `prompt.md`: 原始任务描述
- `repo/`: 待评仓库
- `task.json`: 辅助任务元信息

You must evaluate architecture quality according to the real repository structure in the workspace.
The summaries below are only provided to help navigation, while the final judgment must be grounded in the actual files under `repo/`.

Requirements summary:
```text
{prompt_excerpt}
```

Repository file tree:
```text
{file_tree}
```

Inferred stack:
```json
{dump_json_block(stack_profile)}
```

Key file snippets:
```json
{dump_json_block(snippets)}
```

评分任务：
1. Evaluate whether the repository structure is clear and reasonable.
2. Evaluate whether it follows common engineering practices for the language and stack.
3. Evaluate whether build configuration, entry points, and layering are well coordinated.
4. Do not treat repository size or file count as direct evidence of better architecture.

只返回 JSON：
{{
  "subscores": {{
    "structure_reasonableness": 4.2,
    "stack_alignment": 4.0,
    "reference_alignment": 4.1
  }},
  "review": {{
    "stack_inference": "markdown paragraph",
    "mode_explanation": "markdown paragraph",
    "strengths": ["item 1"],
    "issues": ["item 1"],
    "stack_mismatches": ["item 1"],
    "reference_gaps": ["item 1"]
  }}
}}
"""
