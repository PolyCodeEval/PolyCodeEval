# L0 Prompt Score 结果规范

本目录用于保存 `PolyCodeEval` 中 `L0` 级别项目提示词的复评结果。

`L0` 的含义是：给定一个 prompt，让模型从 `0-1` 生成一个完整可用的代码仓库。这里保存的是对这些 prompt 本身的质量审核结果，而不是运行评测结果。

## 目录结构

每一轮审核结果按 judge 配置单独放在一个根目录下。当前已有批次：

- `gpt5.4_judge/`

批次目录结构固定为：

```text
l0_prompt_score/
├── README.md
└── gpt5.4_judge/
    ├── summary.json
    ├── agent_runs.jsonl
    ├── review_template.txt
    ├── cpp/
    ├── go/
    ├── java/
    ├── javascript/
    └── python/
```

语言目录下按项目分组：

```text
gpt5.4_judge/<language>/<project>/
├── L0_<project>.raw.md
└── L0_<project>.json
```

例如：

```text
gpt5.4_judge/javascript/mitt/
├── L0_mitt.raw.md
└── L0_mitt.json
```

## 输入对象约定

每个结果对应的数据集 prompt 路径固定为：

```text
datasets/<language>/<project>/tasks/L0_<project>/prompt.md
```

评分对象必须是该真实路径下的 prompt，而不是仓库根下的伪相对路径。

## 单项目结果文件

### 1. 原始子代理输出

文件名：

```text
L0_<project>.raw.md
```

内容约定：

- 保存子代理最终返回的原始 JSON 文本
- 只包含评分结果本体
- 不允许额外 Markdown 包装
- 不允许额外解释性文字

### 2. 结构化标准结果

文件名：

```text
L0_<project>.json
```

结构约定：

```json
{
  "task": "javascript/mitt/L0_mitt",
  "project": "javascript/mitt",
  "language": "javascript",
  "prompt_path": "/abs/path/to/datasets/javascript/mitt/tasks/L0_mitt/prompt.md",
  "project_root": "/abs/path/to/datasets/javascript/mitt",
  "review_type": "l0_prompt_review",
  "review_schema_version": "l0_prompt_review_v1",
  "judge_model": "gpt-5.4",
  "scores": {
    "completeness": {"score": 4.3, "reason": "..."},
    "unambiguity": {"score": 4.6, "reason": "..."},
    "testability": {"score": 4.8, "reason": "..."},
    "consistency": {"score": 4.4, "reason": "..."}
  },
  "overall_score": 4.53,
  "raw_response_file": "L0_mitt.raw.md"
}
```

字段规则：

- `task`: `<language>/<project>/L0_<project>`
- `project`: `<language>/<project>`
- `language`: 语言名，当前取值为 `cpp` / `go` / `java` / `javascript` / `python`
- `review_type`: 固定为 `l0_prompt_review`
- `review_schema_version`: 固定为 `l0_prompt_review_v1`
- `judge_model`: 当前批次固定为 `gpt-5.4`
- `scores`: 四个维度必须齐全
- `overall_score`: 四维算术平均值，保留 2 位小数
- `raw_response_file`: 只写文件名，不写绝对路径

## 评分维度

当前批次使用的维度固定为：

- `completeness`
- `unambiguity`
- `testability`
- `consistency`

评分范围：

- `1.0` 到 `5.0`
- 允许 `1` 位小数

当前采用的宽松口径来源于：

- [Prompt 复评提示词.md](docs/Prompt%20复评提示词.md)

核心解释：

- `completeness`：只要覆盖仓库核心功能、主要能力边界和大致实现思路，即可拿到较高分，不要求覆盖全部工程细节
- `consistency`：只要不和当前真实实现明显冲突，就可给较高分；仅仅遗漏细节不应重扣
- `testability`：重点看是否足以支撑黑盒可验证的核心能力
- `unambiguity`：重点看核心接口、核心行为、关键输入输出是否说清楚

## 汇总文件

文件名：

```text
summary.json
```

顶层字段：

- `review_type`
- `review_schema_version`
- `judge_model`
- `generated_at`
- `total`
- `completed`
- `failed`
- `avg_overall_score`
- `avg_completeness`
- `avg_unambiguity`
- `avg_testability`
- `avg_consistency`
- `by_language`
- `by_project`
- `failed_tasks`

语义约定：

- `total` 应等于本批次目标任务总数，当前为 `58`
- `completed` 是成功标准化为 `.json` 的任务数
- `failed` 是未完成或解析失败任务数
- `by_language` / `by_project` 中保存均值聚合
- `failed_tasks` 在全成功时应为空列表

## 运行记录

文件名：

```text
agent_runs.jsonl
```

格式约定：

- `jsonl`
- 1 行对应 1 个项目

字段约定：

```json
{
  "task": "javascript/mitt/L0_mitt",
  "language": "javascript",
  "project": "javascript/mitt",
  "agent_id": "...",
  "agent_type": "worker",
  "model": "gpt-5.4",
  "status": "completed",
  "started_at": "...",
  "completed_at": "...",
  "raw_response_path": ".../L0_mitt.raw.md",
  "json_result_path": ".../L0_mitt.json",
  "parse_ok": true,
  "retry_count": 0,
  "error": null
}
```

用途：

- 保留每个子代理的最终执行记录
- 支持后续审计、抽查和失败重跑

## review_template.txt

文件名：

```text
review_template.txt
```

用途：

- 保存当前批次使用的子代理审核模板
- 后续重跑同一批时，应优先复用该文件，保证口径一致

如果评分口径改变，建议：

1. 先更新 `docs/Prompt 复评提示词.md`
2. 再同步更新对应批次目录下的 `review_template.txt`
3. 然后新开一个批次目录重跑，而不是覆盖旧批次

## 新批次命名建议

后续若新增结果目录，建议用以下模式：

```text
<judge_model>_judge
<judge_model>_judge_<date>
<judge_model>_judge_<policy_tag>
```

例如：

- `gpt5.4_judge`
- `gpt5.4_judge_20260525`
- `gpt5.4_judge_relaxed_policy`

原则：

- 不覆盖旧批次
- 每个批次应自带 `summary.json`、`agent_runs.jsonl`、`review_template.txt`

## 完整性检查

一个完整可用的批次应满足：

1. `summary.json` 存在
2. `agent_runs.jsonl` 存在
3. 每个项目目录同时存在：
   - `L0_<project>.raw.md`
   - `L0_<project>.json`
4. `summary.json.total == 58`
5. `summary.json.completed == 58`
6. `summary.json.failed == 0`
7. `find <batch_dir> -name 'L0_*.json' | wc -l == 58`

## 备注

- 这里保存的是 prompt 审核分，不是 oracle 运行分
- 这里的 `.raw.md` 是子代理最终回包，不保存完整中间对话
- 结果是只读产物，后续若要复跑，优先新增批次目录，不直接覆写已有结果
