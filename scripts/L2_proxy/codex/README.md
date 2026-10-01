# Codex CLI L2 接入使用说明

## 概述

L2 是单文件补全级别：给模型完整仓库上下文（目标文件为 hollowed skeleton），让 agent 直接编辑目标文件并输出完整文件内容。

这套接入对齐 `scripts/L2_proxy/cc/` 的设计，但使用 Codex CLI：

- 使用 Codex CLI agent 非交互执行
- 在临时 workspace 中写入 `CODEX.md`
- 复制 `prompt.md`
- 让 Codex 直接编辑 `src/{target_file}`
- 读取修改后的完整文件，写入 `generated_outputs/`

当前仅支持模型：`gpt-5.4`

---

## 前提

确保 `.env` 或当前 shell 至少提供：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...   # 可选；使用 OpenAI 兼容平台时提供
```

Docker 会自动构建镜像 `cceval-codex-l2:latest` 并启动容器 `cceval-codex-l2-worker`。

---

## 生成命令

```bash
set -a && source .env && set +a

# 单个任务
python scripts/L2_proxy/codex/run_codex_l2_batch.py \
  --task datasets/python/hone/tasks/L2_hone \
  --model gpt-5.4 \
  --output-dir output/codex_l2_run1

# 全量，断点续跑
python scripts/L2_proxy/codex/run_codex_l2_batch.py \
  --all \
  --model gpt-5.4 \
  --output-dir output/codex_l2_run1 \
  --resume
```

---

## 输出结构

```text
output/codex_l2_run1/
├── generated_outputs/
│   └── {lang}/{proj}/{task_name}.txt
├── debug/
│   └── {lang}/{proj}/{task_name}/
│       ├── usage.json
│       ├── codex_response.json
│       └── _done
├── summary.json
└── failures.json
```

---

## 评测命令

```bash
set -a && source .env && set +a

python scripts/run_l2_eval.py \
  --task datasets/python/hone/tasks/L2_hone \
  --solver precomputed:output/codex_l2_run1/generated_outputs \
  --output output/codex_l2_run1_eval \
  --workers 4
```

---

## 工作原理

1. `workspace.build()`：复制 oracle `src/`，用 `hollowed_files/` 覆盖目标文件
2. 写入 `CODEX.md`
3. 复制 `prompt.md`
4. 在容器中执行 `codex exec`
5. Codex 在 workspace 的 `src/` 中直接编辑目标文件
6. 读取修改后的完整文件内容，写入 `generated_outputs/`

---

## 与 cc 的差异

- `cc` 使用 Claude Code CLI；这里使用 Codex CLI 的 `codex exec`
- 认证环境变量改为 `OPENAI_API_KEY` / `OPENAI_BASE_URL`
- debug 原始响应文件名为 `codex_response.json`
- token usage 从 Codex JSONL 事件流中聚合得到，`cost_usd` 默认不保证可用
- `--model` 仅支持 `gpt-5.4`

---

## Docker 管理

```bash
docker ps | grep cceval-codex-l2

docker stop cceval-codex-l2-worker && docker rm cceval-codex-l2-worker
```
