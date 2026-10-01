# Prompt Operations

This package keeps the active prompt-quality evaluation code.

## Active modules

- `score/l0_prompt_review.py`: L0/L1 project-level prompt-review ingestion and aggregation helpers.
- `score/l2_prompt_score.py`: prompt-quality scoring for L2 file-level tasks.
- `score/l3_prompt_score.py`: prompt-quality scoring for L3 function-level tasks.

## Construction-time prompt generation

L2/L3 prompt-description generation is part of the formal construction
pipeline in `scripts/construction/`. It is not maintained as a separate
post-processing step.
