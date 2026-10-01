# L2 Direct Generator

直接调用 LLM 生成整个 L2 目标文件，然后输出到 `precomputed` 兼容目录。

## 用法

```bash
set -a && source .env && set +a

python scripts/L2_proxy/direct/run_l2_direct_batch.py \
  --task datasets/go/chi/tasks/L2_recoverer \
  --model anthropic/claude-sonnet-4-6 \
  --output-dir output/l2_direct_run1

python scripts/L2_proxy/direct/run_l2_direct_batch.py \
  --all \
  --model openai/gpt-4o-mini \
  --output-dir output/l2_direct_run1 \
  --resume
```

## 输出结构

```text
output/l2_direct_run1/
├── generated_outputs/{lang}/{proj}/{task}.txt
├── debug/{lang}/{proj}/{task}/
│   ├── prompt.txt
│   ├── raw_response.txt
│   ├── task.json
│   ├── usage.json
│   └── _done
├── summary.json
└── failures.json
```

## 评测

```bash
python scripts/run_l2_eval.py \
  --task datasets/go/chi/tasks/L2_recoverer \
  --solver precomputed:output/l2_direct_run1/generated_outputs \
  --output output/l2_direct_run1_eval
```
