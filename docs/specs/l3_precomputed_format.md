# L3 预生成输出格式约定

本文档定义了学术工具（本地推理模型、需要特殊运行环境的代码生成系统等）接入 PolyCodeEval L3 评测的标准流程。

---

## 目录结构约定

```
<outputs_dir>/
└── {language}/
    └── {project}/
        └── {task_name}.txt
```

示例：
```
results/codellama_outputs/
├── go/
│   └── chi/
│       ├── L3_context__Reset.txt
│       ├── L3_mux__NotFound.txt
│       └── ...
├── python/
│   └── TextCNN/
│       ├── L3_model__forward.txt
│       └── ...
└── ...
```

- `language`、`project`、`task_name` 必须与 `datasets/` 中的目录名完全一致
- 每个 `.txt` 文件对应一个 L3 任务

---

## 文件内容约定

每个 `.txt` 文件包含**纯函数体字符串**：

- UTF-8 编码
- 不含 markdown 代码块包裹（无 ` ```go ` 等）
- 不含函数签名（无 `func`、`def`、返回类型等）
- 内容将直接替换 `hollowed_files/` 中的 stub 字符串

示例（Go 函数体）：
```
	a.URL = "http://example.com/v3"
	a.ViewsCount = int64(rand.Intn(100))
	a.APIVersion = "v3"
	if a.CustomDataForAuthUsers == nil {
		a.CustomDataForAuthUsers = struct{}{}
	}
	return nil
```

---

## 缺失文件的处理

如果某个任务没有对应的 `.txt` 文件，`PrecomputedSolver` 会抛出 `FileNotFoundError`，该任务的结果会被记录为：

```json
{
  "passed": false,
  "exit_code": -1,
  "error": "No precomputed output for go/chi/L3_context__Reset\nExpected: ..."
}
```

不会中断其他任务的评测。

---

## 完整接入流程

### 第一步：导出 prompt

使用配套工具批量导出所有任务的 prompt：

```bash
python scripts/gen_l3_prompts.py --all --output prompts/
```

生成结构：
```
prompts/
└── {language}/
    └── {project}/
        └── {task_name}.md
```

### 第二步：在工具自身环境中批量推理

以 CodeLlama 为例：

```python
import os
from pathlib import Path

prompts_dir = Path("prompts")
outputs_dir = Path("results/codellama_outputs")

for prompt_file in prompts_dir.glob("**/*.md"):
    rel = prompt_file.relative_to(prompts_dir)
    output_file = outputs_dir / rel.with_suffix(".txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    prompt = prompt_file.read_text()
    function_body = your_model.generate(prompt)  # 替换为实际推理调用
    output_file.write_text(function_body)
```

### 第三步：运行评测

```bash
python scripts/run_l3_eval.py --all \
    --solver precomputed:results/codellama_outputs/ \
    --workers 8 \
    --output results/l3_codellama/
```

### 第四步：查看结果

```bash
cat results/l3_codellama/summary.json
```

或用 `scorer.py` 单独聚合：

```python
from scripts.l3_evaluator.scorer import aggregate
aggregate(Path("results/l3_codellama"))
```
