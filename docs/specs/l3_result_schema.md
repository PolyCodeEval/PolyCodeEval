# L3 评测结果文件格式约定

## 单任务结果文件

路径：`{output_dir}/{language}/{project}/{task_name}.json`

示例：`results/l3_oracle_20260501/go/chi/L3_context__Reset.json`

```json
{
  "task": "go/chi/L3_context__Reset",
  "solver": "oracle",
  "passed": true,
  "exit_code": 0,
  "duration_seconds": 12.4,
  "stdout": "ok  \tgithub.com/go-chi/chi/v5\t0.432s\n...",
  "stderr": "",
  "error": null
}
```

### 字段定义

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `task` | string | 任务标识，格式 `{language}/{project}/{task_name}` |
| `solver` | string | Solver 标识，来自 `Solver.name` 属性 |
| `passed` | bool | `exit_code == 0` |
| `exit_code` | int | Docker 容器退出码。`0` = 测试全部通过，`-1` = 评测流程异常（如 stub 未找到、Docker 超时） |
| `duration_seconds` | float | 从 Docker 启动到退出的耗时（秒） |
| `stdout` | string | Docker 容器标准输出（截断至最后 8000 字符） |
| `stderr` | string | Docker 容器标准错误（截断至最后 4000 字符） |
| `error` | string \| null | 评测流程异常信息。正常执行时为 `null`，异常时记录 Python 异常消息 |

---

## 汇总报告文件

路径：`{output_dir}/summary.json`

由 `scorer.py` 的 `aggregate()` 函数生成。

```json
{
  "solver": "oracle",
  "total": 2388,
  "passed": 2377,
  "pass_rate": 0.9954,
  "by_language": {
    "cpp": {"total": 852, "passed": 848, "pass_rate": 0.9953},
    "go": {"total": 464, "passed": 464, "pass_rate": 1.0},
    "java": {"total": 234, "passed": 232, "pass_rate": 0.9915},
    "javascript": {"total": 585, "passed": 580, "pass_rate": 0.9914},
    "python": {"total": 253, "passed": 253, "pass_rate": 1.0}
  },
  "by_project": {
    "go/chi": {"total": 42, "passed": 42, "pass_rate": 1.0},
    "python/TextCNN": {"total": 18, "passed": 18, "pass_rate": 1.0}
  }
}
```

### 字段定义

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `solver` | string | Solver 标识 |
| `total` | int | 总任务数 |
| `passed` | int | 通过的任务数 |
| `pass_rate` | float | `passed / total`，保留 4 位小数 |
| `by_language` | dict | 按语言分组的统计，每个值含 `total`、`passed`、`pass_rate` |
| `by_project` | dict | 按 `{language}/{project}` 分组的统计，结构同上 |

---

## 断点续跑

`evaluate_task()` 在写入结果前会检查 `result_path.exists()`。如果结果文件已存在，直接返回已有结果，不重复执行。

重跑失败任务的方法：删除对应的 `.json` 文件后重新运行即可。
