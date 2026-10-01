# L3 Solver 接口约定

## Solver 抽象基类

所有 solver 必须继承 `scripts/l3_evaluator/solver/__init__.py` 中的 `Solver` ABC，实现两个接口：

```python
class Solver(ABC):
    @abstractmethod
    def solve(self, task_dir: Path) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...
```

### `solve(task_dir: Path) -> str`

- 输入：L3 任务目录的绝对路径，如 `datasets/go/chi/tasks/L3_context__Reset`
- 输出：**纯函数体字符串**
- 任务目录内可用的文件：`task.json`、`run_config.json`、`prompt.md`、`hollowed_files/`

### `name -> str`

- 用于结果文件中的 `solver` 字段标识
- 示例：`"oracle"`、`"anthropic/claude-sonnet-4-6"`、`"codellama_outputs"`

---

## 返回值语义：函数体的精确定义

`solve()` 返回的字符串将直接替换 `hollowed_files/` 中的 stub 字符串。因此：

- **只含函数体**，不含函数签名、不含花括号（对 Go/Java/C++/JS）或 `def` 行（对 Python）
- **不含 markdown 代码块包裹**（无 ` ```go ` 等）
- 字符串的边界与 `task.json` 中 `stub_info.body_start_byte` / `body_end_byte` 所界定的范围一致

各语言 stub 及其对应的函数体边界：

| 语言 | stub | 函数体范围 |
|:---|:---|:---|
| Python | `pass` | `def` 行之后、下一个同级定义之前的缩进块（保留 docstring 后的部分） |
| Go | `panic("not implemented")` | `{` 之后到 `}` 之前的内容 |
| Java | `throw new UnsupportedOperationException();` | `{` 之后到 `}` 之前的内容 |
| JavaScript/TypeScript | `throw new Error('not implemented')` | `{` 之后到 `}` 之前的内容 |
| C++ | `/* not implemented */` | `{` 之后到 `}` 之前的内容 |

---

## `make_solver(spec)` 规格字符串

工厂函数 `make_solver(spec: str) -> Solver` 解析以下格式：

| 格式 | 实例化的类 | 说明 |
|:---|:---|:---|
| `oracle` | `OracleSolver` | 从原始 `src/` 读取真实函数体，用于验证基础设施 |
| `anthropic/<model_id>` | `APISolver(provider="anthropic", ...)` | 调用 Anthropic Messages API |
| `openai/<model_id>` | `APISolver(provider="openai", ...)` | 调用 OpenAI Chat Completions API |
| `precomputed:<path>` | `PrecomputedSolver(outputs_dir=Path(path))` | 读取预生成输出文件 |

---

## 新增 Solver 的步骤

1. 在 `scripts/l3_evaluator/solver/` 下新建 `.py` 文件
2. 实现 `Solver` ABC 的 `solve()` 和 `name` 两个接口
3. 在 `solver/__init__.py` 的 `make_solver()` 中添加对应的 spec 解析分支
4. 更新本文档
