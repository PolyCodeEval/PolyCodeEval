# L1 评测器使用指南

## 快速开始

```bash
# 1. 生成 L1 任务（对单个项目）
python scripts/run_l1_slicer.py --project datasets/go/chi

# 2. 验证评测基础设施（oracle 模式，不调用任何模型 API）
python scripts/run_l1_eval.py \
  --task datasets/go/chi/tasks/L1_chi \
  --solver oracle

# 3. 用大模型 API 评测
python scripts/run_l1_eval.py --language go \
  --solver anthropic/claude-sonnet-4-6 --workers 4

# 4. 评测学术工具的预生成输出
python scripts/run_l1_eval.py --all \
  --solver precomputed:results/codellama_l1_outputs/ \
  --workers 8
```

---

## 与 L2/L3 的关键差异

| 维度 | L3（函数级） | L2（文件级） | L1（项目级） |
|:---|:---|:---|:---|
| **任务粒度** | 挖空单个函数体 | 挖空同一文件中所有非平凡函数体（≥3 个） | 挖空整个项目所有源文件的所有函数体 |
| **Solver 返回值** | 函数体字符串 | 整个文件内容字符串 | `dict[str, str]`（相对路径 → 文件内容） |
| **Backfill 方式** | 查找 stub 字符串，字节级替换 | 直接覆写整个目标文件 | 逐文件覆写所有目标文件 |
| **task.json stub_info** | 含 `body_start_byte`、`body_end_byte`、`stub` | 仅含 `file`、`lang`、`function_count` | 含 `lang`、`file_count`、`total_function_count` |
| **任务命名** | `L3_{file_stem}__{func_name}` | `L2_{file_stem}` | `L1_{project_name}` |
| **每项目任务数** | 多个（每个非平凡函数一个） | 多个（每个符合条件的文件一个） | **1 个**（整个项目一个任务） |
| **Prompt 策略** | 单文件骨架 + PRD 片段 + 依赖 + 调用者 | 单文件骨架 + PRD 片段 + 依赖 | PRD 全文 + 全项目骨架（无额外依赖） |

L1 与 L2/L3 完全物理隔离——`scripts/l1_evaluator/` 不引用 `scripts/l2_evaluator/` 或 `scripts/l3_evaluator/` 下的任何文件。

---

## 模块职责一览

| 文件 | 职责 |
|:---|:---|
| `task.py` | 单任务编排：workspace → solver → backfill → docker run → 写结果 |
| `workspace.py` | 临时工作区生命周期：创建空 workspace、整仓回填、注入黑盒资源、清理 |
| `runner.py` | Docker 测试执行，薄封装 `docker/runner_lib.py` |
| `scorer.py` | 聚合所有任务结果，输出 `summary.json` 和终端表格 |
| `solver/__init__.py` | `Solver` 抽象基类 + `make_solver()` 工厂函数 |
| `solver/oracle.py` | 从原始 src/ 读取所有文件完整内容（验证基础设施用） |
| `solver/api.py` | 调用 Anthropic / OpenAI API，解析多文件响应 |
| `solver/precomputed.py` | 读取学术工具预生成的输出目录 |

---

## 任务生成

### CLI

```
python scripts/run_l1_slicer.py [scope]
```

| 参数 | 说明 |
|:---|:---|
| `--project <path>` | 为单个项目生成 L1 任务 |
| `--language <lang>` | 为某语言下所有项目生成 |
| `--all` | 全部项目 |

### 生成逻辑

每个项目生成恰好 1 个 L1 任务（`L1_{project_name}`）。生成条件：项目中至少有 1 个函数。

对项目所有源文件：
- 有函数的文件：所有函数体替换为 stub，保留签名和结构
- 无函数的文件：原样复制到 `hollowed_files/`（保持目录结构完整）

### 生成的任务目录结构

```
datasets/{lang}/{project}/tasks/L1_{project_name}/
├── hollowed_files/
│   ├── chi.go                    # 骨架文件（所有函数挖空）
│   ├── context.go
│   ├── mux.go
│   ├── middleware/compress.go
│   └── ...（所有源文件，保留目录结构）
├── task.json              # 任务定义
├── run_config.json        # Docker 运行配置
└── prompt.md              # 模型输入提示词
```

### task.json 格式

```json
{
  "level": "L1",
  "target_dir": ".",
  "hollowed_files": ["chi.go", "context.go", "mux.go", "middleware/compress.go"],
  "context_from_src": [],
  "stub_info": {
    "lang": "go",
    "file_count": 53,
    "total_function_count": 95
  }
}
```

### prompt.md 策略

L1 的 prompt 与 L2/L3 有本质区别：

- **PRD 全文**：不是关键词匹配的片段，而是完整的 `docs/prd.md` 内容
- **全项目骨架**：所有源文件的挖空版本，模型看到完整项目结构
- **无额外依赖**：骨架本身就包含了全部跨文件依赖信息
- **返回格式约定**：`===FILE: relative/path===` 分隔符，每个文件的完整内容

---

## 评测 CLI 参数

```
python scripts/run_l1_eval.py [scope] --solver <spec> [options]
```

### 范围（互斥）

| 参数 | 说明 |
|:---|:---|
| `--task <path>` | 单个任务目录 |
| `--project <path>` | 某个项目下的 L1 任务 |
| `--language <lang>` | 某语言下所有项目的 L1 任务 |
| `--all` | 全部 L1 任务 |

任务发现通过读取 `task.json["level"] == "L1"` 过滤，不会误匹配 L2/L3 任务。

### Solver 规格

| 格式 | 说明 |
|:---|:---|
| `oracle` | 从原始 src/ 读取整个仓库树，用于验证基础设施 |
| `anthropic/<model_id>` | 调用 Anthropic Messages API |
| `openai/<model_id>` | 调用 OpenAI Chat Completions API |
| `precomputed:<path>` | 读取预生成的整仓输出目录 |

### 选项

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `--workers N` | 4 | 并发 Docker 容器数 |
| `--output <path>` | `results/l1_{solver}_{timestamp}/` | 结果输出目录 |

---

## Solver 接入

新增一个 solver 只需三步：

1. 在 `solver/` 下新建 `.py` 文件，继承 `Solver` ABC
2. 实现 `solve(task_dir) -> dict[str, str]`（返回 `{相对路径: 完整文件内容}` 字典，UTF-8 编码）和 `name` 属性
3. 在 `solver/__init__.py` 的 `make_solver()` 中添加解析分支

**与 L2/L3 Solver 的区别**：L3 的 `solve()` 返回纯函数体字符串，L2 返回单个文件内容字符串，L1 返回 `dict[str, str]` 多文件映射。

### API Solver 响应格式

模型需按以下格式返回多文件内容；评测器会把这些文件视为完整项目仓库的一部分：

```
===FILE: chi.go===
package chi

import "net/http"
...

===FILE: middleware/compress.go===
package middleware

import "compress/flate"
...
```

解析器使用正则匹配 `===FILE: path===` 分隔符。返回的所有文件都会被写回 `/workspace/src/<rel_path>`。

---

## 断点续跑

评测器在写入结果前会检查结果文件是否已存在。如果存在，直接跳过该任务。

重跑失败任务：删除对应的 `.json` 文件后重新运行即可。

```bash
# 删除所有失败的结果文件
cd results/l1_oracle_20260504/
grep -rl '"passed": false' . | xargs rm
# 重跑
python scripts/run_l1_eval.py --all --solver oracle --output results/l1_oracle_20260504/
```

---

## 结果解读

每个任务生成一个 JSON 文件，所有任务完成后自动生成 `summary.json`。

单独聚合已有结果（不重新评测）：

```python
from l1_evaluator.scorer import aggregate
from pathlib import Path
aggregate(Path("results/l1_oracle_20260504"))
```

---

## 常见问题

### 没有生成 L1 任务

```
Skipped: no non-trivial functions found
```

原因：该项目中没有任何函数可供挖空（源文件中无法解析出函数定义）。目前 56/57 个项目可生成 L1 任务。

### Docker 挂载失败

确认 Docker Desktop 正在运行，且 `/tmp` 目录在 Docker 的文件共享列表中。

### Docker 测试超时

默认 Python/Go/C++ 为 600 秒，Java/JavaScript 为 900 秒。L1 任务涉及整个项目的黑盒测试套件，大型项目可能需要更长时间。

### API 超时 / Token 限制

L1 任务的 prompt 包含整个项目骨架，可能非常长。`APISolver` 默认 `max_tokens=16384`。对于大型项目（如 chi 的 53 个文件），建议：
- 使用支持长上下文的模型
- 适当调大 `max_tokens`（修改 `solver/api.py`）

### 多文件响应解析失败

如果模型未按 `===FILE: path===` 格式返回，解析器会将缺失的文件填充为空字符串，导致测试失败。确保 prompt 中的格式说明清晰，或在 `solver/api.py` 中增加 system prompt 强化格式约束。
