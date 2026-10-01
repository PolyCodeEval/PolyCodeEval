# L2 Prompt Score Results

本目录保存 L2 级别任务提示词评分结果。

当前 L2 评分逻辑是：

- 评价对象不是整份 prompt 的所有内容
- 重点评价：
  - `File Description`
  - `Function Responsibilities`
- 以真实完整目标文件实现为主要事实依据
- 输出单分数评分，不做多维度拆分

## 目录结构

本目录下一般按 judge / 模型分子目录，例如：

- `gpt5.4_judge/`
- `dpskv4_judge/`
- `sonnet4.6_judge/`

每个 judge 子目录代表一套独立评分结果。

## judge 子目录内文件含义

### 1. `summary.json`

当前范围内的聚合汇总结果。

常见字段：

- `review_type`
  当前结果类型，固定为 `l2_prompt_score`
- `review_schema_version`
  当前评分 schema 版本
- `judge_model`
  本次评分使用的模型名
- `generated_at`
  汇总生成时间
- `total`
  目标范围内应有的任务总数
- `completed`
  已成功生成评分结果的任务数
- `failed`
  当前汇总里失败任务数
- `avg_score`
  平均分
- `complete_enough_count`
  被判定为 `complete_enough = true` 的任务数量
- `missing_description_count`
  缺失 `File Description` 或 `Function Responsibilities` 的任务数量
- `by_language`
  按语言聚合
- `by_project`
  按项目聚合

注意：

- 如果后来只对单个任务或单个项目重新跑过 aggregate，`summary.json` 可能被局部范围覆盖。
- 如需恢复全量汇总，请重新执行全量 `aggregate`。

### 2. `agent_runs.jsonl`

逐任务运行日志，JSON Lines 格式，一行一个任务执行记录。

常见字段：

- `task`
  任务 ID，例如 `go/chi/L2_mux`
- `language`
- `project`
- `status`
  `ok` 或 `failed`
- `started_at`
- `completed_at`
- `raw_response_path`
  模型原始评分输出文件路径
- `json_result_path`
  任务级评分结果 JSON 路径
- `parse_ok`
  是否成功解析模型输出
- `error`
  失败时的错误信息
- `model`
  使用的评分模型

用途：

- 排查失败任务
- 查看哪些任务已经完成
- 检查某次评分是否真正产出结果文件

### 3. `incomplete_run.json`

只在目标范围**不完整**时出现。

含义：

- 当前有任务缺失评分结果
- 因此不会产出可信的完整汇总

常见字段：

- `total_expected`
  该次目标范围预期任务总数
- `completed`
  已完成评分任务数
- `missing`
  缺失任务数
- `failed_tasks`
  缺失任务列表
- `resume_hint`
  提示后续用 `--resume` 续跑

如果这个文件存在，建议：

1. 继续执行 `run --resume`
2. 全部补齐后再执行 `aggregate`

## 语言/项目子目录内文件含义

目录层级一般为：

- `{judge_dir}/{language}/{project}/`

例如：

- `gpt5.4_judge/go/chi/`
- `gpt5.4_judge/cpp/base64pp/`

该目录下通常包含三类文件。

### 1. 任务级评分结果：`L2_*.json`

每个任务一个 JSON。

例如：

- `L2_mux.json`
- `L2_base64pp.json`

常见字段：

- `task`
  完整任务 ID
- `project`
- `language`
- `prompt_path`
  被评分任务的 `prompt.md`
- `task_json_path`
- `source_file_path`
  真实目标文件路径
- `target_file`
  `task.json.target`
- `judge_model`
- `descriptions_present`
  是否成功提取到 `File Description` 和 `Function Responsibilities`
- `score`
  1.0 到 5.0 的单分数
- `reason`
  评分理由
- `missing_functionality`
  描述中遗漏的关键行为或多函数职责
- `incorrect_or_misleading_points`
  描述中不准确或误导的部分
- `complete_enough`
  是否足以支持模型补全 skeleton 中所有被挖空函数并恢复整份文件
- `raw_response_file`
  对应原始模型输出文件名

### 2. 模型原始输出：`L2_*.raw.md`

保存评分模型原始返回的 JSON 文本。

用途：

- 调试评分提示词
- 核对模型原始判断
- 排查 JSON 解析问题

### 3. 项目级汇总：`L2_{project}.json`

例如：

- `L2_chi.json`
- `L2_base64pp.json`

这是单个项目内所有 L2 任务的聚合统计。

常见字段：

- `project`
- `language`
- `total`
- `avg_score`
- `complete_enough_count`
- `missing_description_count`
- `completed`
- `failed`
- `tasks`
  任务级简表
- `failed_tasks`
  项目范围内的缺失任务

注意：

- 如果某些任务被手动删掉重跑，项目级汇总会过时。
- 重新执行 `aggregate` 会重建。

## 如何理解几个核心字段

### `score`

单分数，范围 `1.0` 到 `5.0`。

它主要评价两件事：

- `File Description` 是否和真实目标文件实现一致
- `Function Responsibilities` 是否足够支撑多函数补全并恢复整份文件

### `complete_enough`

布尔值。

含义：

- `true`
  表示这份 L2 prompt 的描述部分足以支持模型补全 skeleton 中所有被挖空函数，并恢复目标文件的主要功能行为
- `false`
  表示描述仍不够完整

### `missing_description_count`

聚合字段。

表示目标范围内有多少任务缺失：

- `File Description`
  或
- `Function Responsibilities`

### `complete_enough_count`

聚合字段。

表示目标范围内有多少任务被判定为 `complete_enough = true`。

## 常见操作

### 1. 查看某个任务的评分

进入对应项目目录，查看：

- `{task}.json`
- `{task}.raw.md`

### 2. 查看失败或未完成任务

看：

- `incomplete_run.json`
- `agent_runs.jsonl`

### 3. 重建汇总

如果你手动修改了任务 prompt，或者手动删除了部分任务级评分结果，原有：

- `summary.json`
- `L2_{project}.json`

可能已经过时，需要重新执行 `aggregate`。

## 说明

- 本目录是结果目录，不是源码目录。
- 结果文件可能因后续实验反复覆盖。
- 如果你做了 L2 低分任务重生成并删掉了旧评分 JSON，那么这里的汇总在重新 aggregate 前都可能是过时的。
