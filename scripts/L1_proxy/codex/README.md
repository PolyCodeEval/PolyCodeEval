# Codex L1 接入使用说明

## 概述

L1 现在采用与 L0 一致的整仓语义：

- 模型在空 workspace 中生成完整项目仓库
- 生成结果按整个 `src/` 树回收
- 评测时从空 workspace 开始，整仓回填后只运行黑盒测试

默认模型：`gpt-5.4`

---

## 前提

确保 `.env` 或当前 shell 至少提供：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...   # 可选；使用 OpenAI 兼容平台时提供
```

Docker 会自动构建镜像 `cceval-codex-l1:latest` 并启动容器 `cceval-codex-l1-worker`。

---

## 生成命令

```bash
set -a && source .env && set +a

python scripts/L1_proxy/codex/run_codex_l1_batch.py \
  --task datasets/python/chakin/tasks/L1_chakin \
  --model gpt-5.4 \
  --output-dir output/codex_l1_run1
```

---

## 输出结构

```text
output/codex_l1_run1/
├── generated_outputs/
│   └── {lang}/{proj}/{task_name}/
│       └── {rel_path}
├── debug/
│   └── {lang}/{proj}/{task_name}/
│       ├── usage.json
│       ├── codex_response.json
│       └── _done
├── summary.json
└── failures.json
```

`generated_outputs/` 下保存的是模型生成的完整仓库文件树，而不是仅目标文件列表。

---

## 评测命令

```bash
set -a && source .env && set +a

python scripts/run_l1_eval.py \
  --task datasets/python/chakin/tasks/L1_chakin \
  --solver precomputed:output/codex_l1_run1/generated_outputs \
  --output output/codex_l1_run1_eval \
  --correctness-only
```

---

## 工作原理

1. 创建空的 `src/`
2. 写入 `prompt.md`、`CODEX.md`
3. 可选注入 `reference/` 中的构建配置
4. 在容器中执行 `codex exec`
5. 回收 `src/` 下生成的整个项目树
6. 评测时整仓回填，再注入黑盒资源并运行测试

---

## 资源注入规则

生成阶段 Codex 能看到：

- `prompt.md`
- `CODEX.md`
- 空的 `src/`
- 可选 `reference/`

不会注入：

- `blackbox_tests/`
- `tests/` fixture
- oracle 源码实现文件

---

## 与 cc 的差异

- `cc` 使用 Claude Code CLI；这里使用 Codex CLI 的 `codex exec`
- 认证环境变量改为 `OPENAI_API_KEY` / `OPENAI_BASE_URL`
- debug 原始响应文件名为 `codex_response.json`
- token usage 从 Codex JSONL 事件流中聚合得到
