# L3 评测器使用指南

## 三种评测方式

### 方式一：实时推理评测（推荐）

推理与评测一体化，每个 task 调用一次 API，拿到结果后立即跑测试。

```bash
# OpenAI 兼容接口（支持云雾等第三方平台）
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://your-api-endpoint/v1"

python scripts/run_l3_eval.py --language go \
  --solver openai/gpt-4o --workers 4

# Anthropic 官方接口
export ANTHROPIC_API_KEY="your-api-key"

python scripts/run_l3_eval.py --language go \
  --solver anthropic/claude-sonnet-4-6 --workers 4
```

`openai/` 前缀的 solver 会读取 `OPENAI_BASE_URL` 环境变量，可以指向任何 OpenAI 兼容的第三方平台。

### 方式二：预计算推理 + 离线评测

先批量推理生成函数体文件，再统一评测。适合大规模跑分、推理和评测解耦的场景。

```bash
# 第一步：批量推理
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://your-api-endpoint/v1"

python -m scripts.l3_evaluator.infer \
    --prompts prompts/ \
    --output results/model_outputs \
    --model gpt-4o \
    --workers 8

# 第二步：评测
python scripts/run_l3_eval.py --language go \
  --solver precomputed:results/model_outputs \
  --workers 4
```

支持断点续跑：已存在的输出文件会自动跳过。

#### infer.py 参数

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `--prompts` | `prompts` | prompt 文件目录 |
| `--output` | `results/yunwu_outputs` | 输出目录，生成 `{lang}/{project}/{task}.txt` |
| `--model` | `gpt-3.5-turbo` | API 模型名称 |
| `--base-url` | `$OPENAI_BASE_URL` | API 地址 |
| `--api-key` | `$OPENAI_API_KEY` | API 密钥 |
| `--workers` | `4` | 并发请求数 |

### 方式三：Oracle 验证

使用标准答案验证评测框架本身的正确性，不调用任何模型 API。

```bash
python scripts/run_l3_eval.py --language go --solver oracle --workers 4
```

---

## 模块职责一览

| 文件 | 职责 |
|:---|:---|
| `infer.py` | 批量推理：调用 LLM API 生成预计算函数体输出 |
| `task.py` | 单任务编排：workspace → solver → backfill → docker run → 写结果 |
| `workspace.py` | 临时工作区生命周期：复制 src/、回填函数体、清理 |
| `runner.py` | Docker 测试执行：单次运行模式 & 长驻容器模式（`ProjectContainer`） |
| `scorer.py` | 聚合所有任务结果，输出 `summary.json` 和终端表格 |
| `solver/__init__.py` | `Solver` 抽象基类 + `make_solver()` 工厂函数 |
| `solver/oracle.py` | 从原始 src/ 读取真实函数体（验证基础设施用） |
| `solver/api.py` | 实时调用 Anthropic / OpenAI 兼容 API |
| `solver/precomputed.py` | 读取预生成的输出文件 |

---

## CLI 参数

```
python scripts/run_l3_eval.py [scope] --solver <spec> [options]
```

### 范围（互斥）

| 参数 | 说明 |
|:---|:---|
| `--task <path>` | 单个任务目录 |
| `--project <path>` | 某个项目下的所有任务 |
| `--language <lang>` | 某语言下所有项目的所有任务 |
| `--all` | 全部任务 |

### Solver 规格

| 格式 | 说明 |
|:---|:---|
| `oracle` | 从原始 src/ 读取答案，用于验证基础设施 |
| `anthropic/<model_id>` | 调用 Anthropic Messages API |
| `openai/<model_id>` | 调用 OpenAI 兼容 API（通过 `OPENAI_BASE_URL` 支持第三方平台） |
| `precomputed:<path>` | 读取预生成输出目录 |

### 选项

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `--workers N` | 4 | 并发项目数（同一项目内 task 串行共享容器） |
| `--output <path>` | `results/l3_{solver}_{timestamp}/` | 结果输出目录 |

---

## 评测加速

评测器使用长驻容器模式优化性能：

- 同一项目的所有 task 共享一个 Docker 容器
- `install_command` 只执行一次，编译产物跨 task 复用
- `--workers` 控制并行项目数，不同项目并行，同一项目内 task 串行
- tests/ 文件单次复制，自动检测并还原可能的污染

---

## 断点续跑

评测器在写入结果前会检查结果文件是否已存在。如果存在，直接跳过该任务。

重跑失败任务：删除对应的 `.json` 文件后重新运行即可。

```bash
# 删除所有失败的结果文件
cd results/l3_oracle_20260501/
grep -rl '"passed": false' . | xargs rm
# 重跑
python scripts/run_l3_eval.py --all --solver oracle --output results/l3_oracle_20260501/
```

---

## 结果格式

每个任务生成一个 JSON 文件，所有任务完成后自动生成 `summary.json`。

```json
{
  "task": "go/script/L3_script__Bytes",
  "solver": "openai/gpt-4o",
  "passed": true,
  "exit_code": 0,
  "duration_seconds": 3.9,
  "stdout": "...",
  "stderr": ""
}
```

单独聚合已有结果（不重新评测）：

```python
from l3_evaluator.scorer import aggregate
from pathlib import Path
aggregate(Path("results/l3_oracle_20260501"))
```

---

## Solver 接入

新增一个 solver 只需三步：

1. 在 `solver/` 下新建 `.py` 文件，继承 `Solver` ABC
2. 实现 `solve(task_dir) -> str`（返回纯函数体字符串）和 `name` 属性
3. 在 `solver/__init__.py` 的 `make_solver()` 中添加解析分支

---

## 常见问题

### Docker 挂载失败

确认 Docker Desktop 正在运行，且 `/tmp` 目录在 Docker 的文件共享列表中。

### API 超时

`APISolver` 使用 SDK 默认超时。如需调整，可在 `solver/api.py` 中修改 `client` 的 `timeout` 参数。

### Docker 测试超时

默认超时：Java 900 秒，其他语言 600 秒。如果项目测试套件较慢，可在 `task.py` 中调整。
