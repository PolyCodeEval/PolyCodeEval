# Prompt Documentation

This directory documents the prompt templates used by the released
PolyCodeEval construction, generation, evaluation, and prompt-quality
assessment scripts.

## Files

- `task_prompt_templates.md`
  - Documents the L0-L3 task prompts written into each task directory as
    `prompt.md`.
  - Used by:
    - `scripts/slicer/l0_task_builder.py`
    - `scripts/slicer/project_task_builder.py`
    - `scripts/slicer/file_task_builder.py`
    - `scripts/slicer/prompt_builder.py`
    - `scripts/construction/prompt_descriptions.py`

- `description_generation_prompts.md`
  - Documents the L2/L3 construction-time prompts used to generate natural
    language task descriptions from Oracle implementations.
  - Used by:
    - `scripts/construction/prompt_descriptions.py`

- `prompt_quality_scoring_prompts.md`
  - Documents the prompts used to score prompt quality for L0/L1, L2, and L3.
  - Used by:
    - `scripts/prompt_ops/score/l0_prompt_review.py`
    - `scripts/prompt_ops/score/l2_prompt_score.py`
    - `scripts/prompt_ops/score/l3_prompt_score.py`

- `project_evaluation_prompts.md`
  - Documents L0/L1 project-level evaluation prompts for faithfulness,
    architecture, architecture-reference lookup, and command inference.
  - Used by:
    - `scripts/l0_evaluator/scoring/prompts.py`
    - `scripts/l0_evaluator/command_inferrer.py`

- `generation_method_prompts.md`
  - Documents generation-method and proxy-integration prompts used by released
    generation adapters.
  - Used by:
    - `scripts/L0_proxy/*/adapter.py`
    - `scripts/L1_proxy/*/adapter.py`
    - `scripts/L2_proxy/*/adapter.py`
    - `scripts/L2_proxy/direct/run_l2_direct_batch.py`
    - `scripts/L3_proxy/DirectAPI/run_api_batch.py`
    - `scripts/L3_proxy/RepoCoder/adapter.py`
    - `scripts/L3_proxy/HCPCoder/hcpcoder_inference.py`
    - `scripts/L3_proxy/AlignCoder/aligncoder_inference.py`

## Scope

These documents describe prompt templates and their intended use. They do not
contain task-specific Oracle source code or generated model outputs.
