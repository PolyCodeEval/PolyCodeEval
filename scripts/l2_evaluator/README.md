# L2 评测器使用指南

## 快速开始

```bash
# 1. 生成 L2 任务（对单个项目）
python scripts/run_l2_slicer.py --project datasets/go/chi

# 2. 验证评测基础设施（oracle 模式，不调用任何模型 API）
python scripts/run_l2_eval.py \
  --task datasets/go/chi/tasks/L2_context \
  --solver oracle

# 3. 用大模型 API 评测
python scripts/run_l2_eval.py --language go \
  --solver anthropic/claude-sonnet-4-6 --workers 4

# 4. 评测学术工具的预生成输出
python scripts/run_l2_eval.py --all \
  --solver precomputed:results/codellama_l2_outputs/ \
  --workers 8
```

---

## 与 L3 的关键差异

| 维度 | L3（函数级） | L2（文件级） |
|:---|:---|:---|
| **任务粒度** | 挖空单个函数体 | 挖空同一文件中所有非平凡函数体（≥3 个） |
| **Solver 返回值** | 函数体字符串 | 整个文件内容字符串 |
| **Backfill 方式** | 查找 stub 字符串，字节级替换 | 直接覆写整个目标文件 |
| **task.json stub_info** | 含 `body_start_byte`、`body_end_byte`、`stub` | 仅含 `file`、`lang`、`function_count` |
| **任务命名** | `L3_{file_stem}__{func_name}` | `L2_{file_stem}` |
| **文件选择** | 每个非平凡函数生成一个任务 | 每个符合条件的文件生成一个任务 |

L2 与 L3 完全物理隔离——`scripts/l2_evaluator/` 不引用 `scripts/l3_evaluator/` 下的任何文件。

---

## 模块职责一览

| 文件 | 职责 |
|:---|:---|
| `task.py` | 单任务编排：workspace → solver → backfill → docker run → 写结果 |
| `workspace.py` | 临时工作区生命周期：复制 src/、覆盖 hollowed_files/、整文件回填、清理 |
| `runner.py` | Docker 测试执行，薄封装 `docker/runner_lib.py` |
| `scorer.py` | 聚合所有任务结果，输出 `summary.json` 和终端表格 |
| `solver/__init__.py` | `Solver` 抽象基类 + `make_solver()` 工厂函数 |
| `solver/oracle.py` | 从原始 src/ 读取完整文件内容（验证基础设施用） |
| `solver/api.py` | 调用 Anthropic / OpenAI API |
| `solver/precomputed.py` | 读取学术工具预生成的输出文件 |

---

## 任务生成

### CLI

```
python scripts/run_l2_slicer.py [scope]
```

| 参数 | 说明 |
|:---|:---|
| `--project <path>` | 为单个项目生成 L2 任务 |
| `--language <lang>` | 为某语言下所有项目生成 |
| `--all` | 全部项目 |

### 文件选择标准

一个源文件被纳入 L2 任务需同时满足：

1. 非测试文件、非配置文件（由 `LangConfig.exclude_patterns` 和 `EXCLUDED_DIRS` 过滤）
2. **非平凡函数数量 ≥ 3**（`FunctionInfo.is_trivial` 判定：函数体 < 10 行或名称为 `__init__`/`toString` 等）

### 生成的任务目录结构

```
datasets/{lang}/{project}/tasks/L2_{file_stem}/
├── hollowed_files/
│   └── {relative_path}    # 所有非平凡函数体被替换为 stub 的骨架文件
├── task.json              # 任务定义
├── run_config.json        # Docker 运行配置
└── prompt.md              # 模型输入提示词
```

### task.json 格式

```json
{
  "level": "L2",
  "target": "context.go",
  "hollowed_files": ["context.go"],
  "context_from_src": ["chi.go", "mux.go"],
  "stub_info": {
    "file": "context.go",
    "lang": "go",
    "function_count": 4
  }
}
```

---

## 评测 CLI 参数

```
python scripts/run_l2_eval.py [scope] --solver <spec> [options]
```

### 范围（互斥）

| 参数 | 说明 |
|:---|:---|
| `--task <path>` | 单个任务目录 |
| `--project <path>` | 某个项目下的所有 L2 任务 |
| `--language <lang>` | 某语言下所有项目的所有 L2 任务 |
| `--all` | 全部 L2 任务 |

任务发现通过读取 `task.json["level"] == "L2"` 过滤，不会误匹配 L3 任务。

### Solver 规格

| 格式 | 说明 |
|:---|:---|
| `oracle` | 从原始 src/ 读取完整文件内容，用于验证基础设施 |
| `anthropic/<model_id>` | 调用 Anthropic Messages API |
| `openai/<model_id>` | 调用 OpenAI Chat Completions API |
| `precomputed:<path>` | 读取预生成输出目录 |

### 选项

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `--workers N` | 4 | 并发 Docker 容器数 |
| `--output <path>` | `results/l2_{solver}_{timestamp}/` | 结果输出目录 |

---

## Solver 接入

新增一个 solver 只需三步：

1. 在 `solver/` 下新建 `.py` 文件，继承 `Solver` ABC
2. 实现 `solve(task_dir) -> str`（返回完整文件内容字符串，UTF-8 编码，不含 markdown 包裹）和 `name` 属性
3. 在 `solver/__init__.py` 的 `make_solver()` 中添加解析分支

**与 L3 Solver 的区别**：L3 的 `solve()` 返回纯函数体（不含函数签名），L2 的 `solve()` 返回整个文件内容（含 import、签名、函数体等完整结构）。

---

## 断点续跑

评测器在写入结果前会检查结果文件是否已存在。如果存在，直接跳过该任务。

重跑失败任务：删除对应的 `.json` 文件后重新运行即可。

```bash
# 删除所有失败的结果文件
cd results/l2_oracle_20260503/
grep -rl '"passed": false' . | xargs rm
# 重跑
python scripts/run_l2_eval.py --all --solver oracle --output results/l2_oracle_20260503/
```

---

## 结果解读

每个任务生成一个 JSON 文件，所有任务完成后自动生成 `summary.json`。

单独聚合已有结果（不重新评测）：

```python
from l2_evaluator.scorer import aggregate
from pathlib import Path
aggregate(Path("results/l2_oracle_20260503"))
```

---

## 常见问题

### 没有生成任何 L2 任务

```
Generated 0 L2 tasks
```

原因：该项目中没有任何源文件同时满足两个条件（≥3 个非平凡函数、非测试文件）。可以检查：

```bash
# 查看某项目有哪些源文件及其函数数量
python -c "
import sys; sys.path.insert(0, 'scripts')
from slicer.project import load_project
from slicer.parser import SymbolExtractor
ctx = load_project('datasets/go/chi')
ext = SymbolExtractor(ctx.lang_config)
for f in ctx.source_files:
    funcs = ext.extract_functions(f)
    nt = [fn for fn in funcs if not fn.is_trivial]
    loc = len(f.read_text().splitlines())
    print(f'{f.name:30s}  LOC={loc:4d}  non_trivial={len(nt)}')
"
```

### Docker 挂载失败

确认 Docker Desktop 正在运行，且 `/tmp` 目录在 Docker 的文件共享列表中。

### Docker 测试超时

默认 300 秒。如果项目测试套件较慢，可在 `runner.py` 的 `run()` 函数中调整 `timeout` 参数。

### API 超时

`APISolver` 使用 SDK 默认超时。L2 任务输出较长（整个文件），建议将 `max_tokens` 从默认的 8192 调大（修改 `solver/api.py`）。
