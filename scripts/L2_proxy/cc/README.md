# Claude Code L2 接入使用说明

## 概述

L2 是**单文件补全**级别：给模型完整仓库（挖空了目标文件的函数体），让它补全整个文件。

- 共 150 个任务，覆盖 python/java/go/cpp/javascript 五种语言
- 每个任务只有一个目标文件（`stub_info.file`）

---

## 前提

确保 `.env` 里有：
```
ANTHROPIC_AUTH_TOKEN=<ANTHROPIC_AUTH_TOKEN>
ANTHROPIC_BASE_URL=https://yunwu.ai
```

Docker 已运行（首次运行会自动构建镜像 `cceval-l2:latest` 并启动容器 `cceval-l2-worker`）。

---

## 生成命令

```bash
set -a && source .env && set +a

# 单个任务
python scripts/L2_proxy/cc/run_cc_l2_batch.py \
  --task datasets/python/hone/tasks/L2_hone \
  --model claude-sonnet-4-6 \
  --output-dir output/cc_l2_run1

# 多个任务（空格分隔）
python scripts/L2_proxy/cc/run_cc_l2_batch.py \
  --task datasets/python/hone/tasks/L2_hone \
          datasets/go/chi/tasks/L2_logger \
  --model claude-sonnet-4-6 \
  --output-dir output/cc_l2_run1

# 某个语言的所有 L2 任务
python scripts/L2_proxy/cc/run_cc_l2_batch.py \
  --language python \
  --model claude-sonnet-4-6 \
  --output-dir output/cc_l2_run1

# 全量（150 个任务），断点续跑
python scripts/L2_proxy/cc/run_cc_l2_batch.py \
  --all --model claude-sonnet-4-6 \
  --output-dir output/cc_l2_run1 --resume
```

---

## 输出结构

```
output/cc_l2_run1/
├── generated_outputs/
│   └── {lang}/{proj}/{task_name}.txt       # 生成的完整文件内容
├── debug/
│   └── {lang}/{proj}/{task_name}/
│       ├── usage.json           # token 用量
│       ├── claude_response.json # claude 完整 JSON 输出
│       └── _done                # 成功标记（--resume 依赖此文件）
├── summary.json                 # 总统计
└── failures.json                # 失败任务列表
```

`usage.json` 字段：
```json
{
  "input_tokens": 48823,
  "output_tokens": 19506,
  "cache_read_input_tokens": 0,
  "cache_creation_input_tokens": 12000,
  "total_tokens": 68329,
  "cost_usd": 0.12,
  "model": "claude-sonnet-4-6",
  "num_turns": 14,
  "duration_s": 44.6,
  "timestamp": "2026-06-09T17:00:00Z"
}
```

---

## 评测命令

生成完成后，用 `precomputed:` solver 接入现有 L2 评测框架：

```bash
set -a && source .env && set +a

python scripts/run_l2_eval.py \
  --task datasets/python/hone/tasks/L2_hone \
  --solver precomputed:output/cc_l2_run1/generated_outputs \
  --output output/cc_l2_run1_eval \
  --workers 4
```

`precomputed:` solver 期望路径：`{outputs_dir}/{lang}/{proj}/{task_name}.txt`，与 batch runner 输出的格式完全匹配。

---

## Docker 管理

```bash
# 查看状态
docker ps | grep cceval-l2

# 停止（下次运行自动重启）
docker stop cceval-l2-worker && docker rm cceval-l2-worker

# 强制重建镜像
docker rmi cceval-l2:latest
docker stop cceval-l2-worker && docker rm cceval-l2-worker
# 下次运行时自动重建
```

---

## 工作原理

1. `workspace.build()`：复制 oracle `src/`，用 `hollowed_files/` 覆盖目标文件（保留 stub 占位符）
2. 写 `CLAUDE.md`（约束 claude 直接编辑文件，不要询问）
3. 复制 `prompt.md` 到 workspace 根目录
4. `docker exec cceval-l2-worker claude -p "..." --permission-mode bypassPermissions --output-format json`
5. Claude 在 workspace 的 `src/` 里直接编辑目标文件
6. 读取修改后的文件内容，写入 `generated_outputs/`
