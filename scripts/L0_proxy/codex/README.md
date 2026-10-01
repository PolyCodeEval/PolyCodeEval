# Codex L0 接入使用说明

## 概述

L0 是**从零生成项目**级别：只给模型 PRD，让 agent 在空 workspace 中创建完整项目。

这套接入对齐 `scripts/L0_proxy/cc/` 的设计：

- 使用 Codex CLI agent 非交互执行
- 在临时 workspace 中写入 `prompt.md`
- 可选注入 oracle 构建配置到 `reference/`
- 回收 `src/` 中所有生成文件到 `generated_outputs/`

默认模型：`gpt-5.4`

---

## 前提

确保 `.env` 或当前 shell 至少提供：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...   # 可选；使用 OpenAI 兼容平台时提供
```

Docker 会自动构建镜像 `cceval-codex-l0:latest` 并启动容器 `cceval-codex-l0-worker`。

---

## 生成命令

```bash
set -a && source .env && set +a

# 单个任务
python scripts/L0_proxy/codex/run_codex_l0_batch.py \
  --task datasets/python/chakin/tasks/L0_chakin \
  --output-dir output/codex_l0_run1

# 指定模型
python scripts/L0_proxy/codex/run_codex_l0_batch.py \
  --task datasets/java/image-similarity/tasks/L0_image-similarity \
  --model gpt-5.4 \
  --output-dir output/codex_l0_run1

# 全量，断点续跑
python scripts/L0_proxy/codex/run_codex_l0_batch.py \
  --all \
  --output-dir output/codex_l0_run1 \
  --resume
```

---

## 输出结构

```text
output/codex_l0_run1/
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

---

## 评测命令

```bash
set -a && source .env && set +a

python scripts/run_l0_eval.py \
  --task datasets/python/chakin/tasks/L0_chakin \
  --solver precomputed:output/codex_l0_run1/generated_outputs \
  --output output/codex_l0_run1_eval \
  --judge-model gpt-5.4
```

---

## 工作原理

1. `workspace.build()` 创建空 `src/`
2. 写入 `CODEX.md` 和 `prompt.md`
3. 从 `run_config.json` 提取测试环境提示，追加到 `prompt.md`
4. 从 oracle `src/` 复制白名单构建配置到 `reference/`
5. 在容器中执行 `codex exec`
6. 回收 `src/` 下生成文件，输出到 `generated_outputs/`

---

## 资源注入规则

生成阶段会给 Codex 看到这些额外内容：

- `prompt.md`
- `CODEX.md`
- 可选 `reference/`

`reference/` 只包含白名单构建配置：

- Python: `requirements.txt`, `setup.py`, `setup.cfg`, `pyproject.toml`
- Java: `build.gradle`, `settings.gradle`, `pom.xml`, `gradle/`, `.mvn`
- Go: `go.mod`, `go.sum`
- C++: `CMakeLists.txt`, `Makefile`, `meson.build`
- JavaScript/TypeScript: `package.json`, `tsconfig.json`, `tsconfig.build.json`

不会注入：

- `blackbox_tests/`
- `tests/` fixture
- oracle 源码实现文件

---

## 与 cc 的差异

- `cc` 使用 Claude Code CLI；这里使用 Codex CLI 的 `codex exec`
- 认证环境变量改为 `OPENAI_API_KEY` / `OPENAI_BASE_URL`
- debug 原始响应文件名为 `codex_response.json`
- token usage 从 Codex JSONL 事件流中聚合得到，`cost_usd` 默认不保证可用

---

## Docker 管理

```bash
docker ps | grep cceval-codex-l0

docker stop cceval-codex-l0-worker && docker rm cceval-codex-l0-worker
```
