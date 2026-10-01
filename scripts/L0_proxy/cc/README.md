# Claude Code L0 接入使用说明

## 概述

L0 是**从零生成项目**级别：只给模型 PRD（产品需求文档），让它从零生成完整可运行项目。

- 共 58 个任务，覆盖 python/java/go/cpp/javascript 五种语言
- 没有 oracle 源码参考，workspace 从空目录开始
- 评测只跑黑盒测试（blackbox），外加 LLM judge 评分（Faithfulness/Architecture/Health）

---

## 前提

确保 `.env` 里有：
```
ANTHROPIC_AUTH_TOKEN=<ANTHROPIC_AUTH_TOKEN>
ANTHROPIC_BASE_URL=https://yunwu.ai
OPENAI_API_KEY=...        # L0 评测需要（LLM judge 用 gpt 模型）
OPENAI_BASE_URL=...
```

Docker 会自动构建镜像 `cceval-l0:latest` 并启动容器 `cceval-l0-worker`（与 L1/L2 独立，可同时跑）。

---

## 生成命令

```bash
set -a && source .env && set +a

# 单个任务
python scripts/L0_proxy/cc/run_cc_l0_batch.py \
  --task datasets/python/chakin/tasks/L0_chakin \
  --model claude-sonnet-4-6 \
  --output-dir output/cc_l0_run1

# 多个任务
python scripts/L0_proxy/cc/run_cc_l0_batch.py \
  --task datasets/python/chakin/tasks/L0_chakin \
          datasets/go/gobreaker/tasks/L0_gobreaker \
          datasets/cpp/base64pp/tasks/L0_base64pp \
  --model claude-sonnet-4-6 \
  --output-dir output/cc_l0_run1

# 全量（58 个任务），断点续跑
python scripts/L0_proxy/cc/run_cc_l0_batch.py \
  --all --model claude-sonnet-4-6 \
  --output-dir output/cc_l0_run1 --resume
```

---

## 输出结构

```
output/cc_l0_run1/
├── generated_outputs/
│   └── {lang}/{proj}/{task_name}/
│       └── {rel_path}            # src/ 下所有生成的文件（不含 src/ 前缀）
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

# 单任务评测
python scripts/run_l0_eval.py \
  --task datasets/python/chakin/tasks/L0_chakin \
  --solver precomputed:output/cc_l0_run1/generated_outputs \
  --output output/cc_l0_run1_eval \
  --judge-model gpt-5.4

# 全量评测
python scripts/run_l0_eval.py \
  --all \
  --solver precomputed:output/cc_l0_run1/generated_outputs \
  --output output/cc_l0_run1_eval \
  --judge-model gpt-5.4 \
  --workers 4
```

L0 评测是四维评分：`Score = 0.4*C + 0.25*F + 0.25*A + 0.1*H`

- **C (Correctness)**：黑盒测试通过率（0-5）
- **F (Faithfulness)**：PRD 覆盖度，LLM judge 评分
- **A (Architecture)**：代码架构质量，LLM judge 评分
- **H (Health)**：静态分析健康度

---

## Docker 管理

```bash
# 查看状态
docker ps | grep cceval-l0

# 停止
docker stop cceval-l0-worker && docker rm cceval-l0-worker
```

---

## 工作原理

1. `workspace.build()`：创建空 `src/` 目录
2. 写 `CLAUDE.md`（要求用 Write 工具创建文件，不要文字输出）
3. 复制 `prompt.md` 到 workspace，追加 `run_config.json` 里的测试命令作为提示
4. `docker exec cceval-l0-worker claude -p "..."`，claude 从零在 `src/` 里创建所有文件
5. 读取 `src/` 下所有文件，写入 `generated_outputs/`
6. **Fallback**：若 claude 以文字输出（`===FILE: path===` 格式）而非工具写文件，自动解析并回写到磁盘

---

## 各语言路径约束（重要）

L0 生成的代码必须满足以下路径约束，否则黑盒测试无法运行。这些约束在 prompt.md 里**已明确说明**，模型理论上能正确生成。

### Python
- `requirements.txt` 必须在 `src/` 根目录
- 测试用 `PYTHONPATH=/workspace/src pytest /workspace/blackbox_tests/`，所以模块直接在 `src/` 下即可，无需特定子目录结构
- **无硬编码路径约束，宽容度最高**

### Java
- 必须生成标准 Gradle 项目结构（`build.gradle`、`settings.gradle`、`src/main/java/...`）
- 黑盒测试会把 `.java` 测试文件复制到 `tests/src/test/java/`（依赖 workspace 里从 oracle 复制来的 `tests/` 目录）并运行 `gradle test`
- 包结构（package 声明）必须与 prompt 里描述的类结构一致

### Go
- `go.mod` 必须在 `src/` 根目录，module path 必须与 blackbox 测试的 import 路径一致
- **v2 子包的文件必须声明 `package gobreaker`，不能声明 `package v2`**（Go module `/v2` 后缀不改变包名）
- blackbox 测试将 `*_test.go` 复制到 `src/` 和 `src/v2/` 后执行 `go test ./...`

### C++
- 头文件**必须**在 `src/base64pp/include/base64pp/base64pp.h`（路径硬编码在 blackbox 编译命令里）
- 实现**必须**在 `src/base64pp/base64pp.cpp`（路径硬编码在 blackbox 编译命令里）
- prompt 里已明确说明这两个路径

### JavaScript (TypeScript)
- 源码（`src/mitt.ts`）编译后的产物必须在 `src/dist/mitt.js`
- `package.json` 应包含 `bundle` 脚本（或 install_command 的 fallback 能成功）
- blackbox 测试通过 `require('../../dist/mitt.js')` 加载编译产物
- **注意**：install_command 里有 `npm run bundle`，若 L0 生成的 `package.json` 没有此脚本会导致安装步骤失败（已知框架问题）
