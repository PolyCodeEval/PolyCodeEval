# Claude Code L1 接入使用说明

## 概述

L1 现在采用与 L0 一致的整仓语义：

- 模型在空 workspace 中生成完整项目仓库
- 生成结果按整个 `src/` 树回收
- 评测时从空 workspace 开始，整仓回填后只运行黑盒测试

对外结果 schema 已与 L0 评分逻辑对齐。

---

## 前提

确保 `.env` 里有：
```bash
ANTHROPIC_AUTH_TOKEN=<ANTHROPIC_AUTH_TOKEN>
ANTHROPIC_BASE_URL=https://yunwu.ai
```

Docker 会自动构建镜像 `cceval-l1:latest` 并启动容器 `cceval-l1-worker`。

---

## 生成命令

```bash
set -a && source .env && set +a

python scripts/L1_proxy/cc/run_cc_l1_batch.py \
  --task datasets/java/idcenter/tasks/L1_idcenter \
  --model claude-sonnet-4-6 \
  --output-dir output/cc_l1_run1
```

---

## 输出结构

```text
output/cc_l1_run1/
├── generated_outputs/
│   └── {lang}/{proj}/{task_name}/
│       └── {rel_path}
├── debug/
│   └── {lang}/{proj}/{task_name}/
│       ├── usage.json
│       ├── claude_response.json
│       └── _done
├── summary.json
└── failures.json
```

---

## 评测命令

```bash
set -a && source .env && set +a

python scripts/run_l1_eval.py \
  --task datasets/java/idcenter/tasks/L1_idcenter \
  --solver precomputed:output/cc_l1_run1/generated_outputs \
  --output output/cc_l1_run1_eval \
  --workers 4
```

---

## 工作原理

1. 创建空的 `src/`
2. 写入 `CLAUDE.md` 和 `prompt.md`
3. 可选注入 `reference/` 构建配置
4. 在容器中执行 Claude Code CLI
5. 回收 `src/` 下生成的整个项目树
6. 评测时整仓回填，再注入黑盒资源并运行测试

---

## 说明

- L1 评测不再区分白盒/黑盒入口，对外统一黑盒测试。
- `precomputed:` solver 的输出布局保持不变。
- `generated_outputs/{lang}/{proj}/{task}/{rel_path}` 保存的是整仓文件树，并会被 `run_l1_eval.py` 直接消费。
