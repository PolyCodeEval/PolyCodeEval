# Dataset Construction

This directory contains the formal task-construction entry point for
PolyCodeEval.

## Main entry point

```bash
python scripts/construction/build_tasks.py --level L2 --language python
python scripts/construction/build_tasks.py --level L3 --all --with-llm-description --resume
```

`build_tasks.py` keeps the original slicer behavior for L0-L3 and adds an
integrated L2/L3 prompt-description step when `--with-llm-description` is set.
The final L2/L3 prompts are written directly to each task directory as
`prompt.md`; no separate post-generation prompt rewrite step is required.

## Modules

- `build_tasks.py`: unified construction CLI.
- `prompt_descriptions.py`: L2/L3 description requests, context extraction,
  final prompt rendering, and prompt metadata writing.

## Compatibility

The existing top-level slicer entry points are kept to avoid breaking old local
commands. New public workflows should use `scripts/construction/build_tasks.py`.
