# L3 Prompt Score Results

本目录保存 L3 级别任务提示词评分结果。

当前评分逻辑是：

- 只评价每个任务 `prompt.md` 中的 `Function Description`
- 以真实完整函数实现为主要事实依据
- 输出单分数评分，不做多维度拆分

## 目录结构

本目录下一般按 judge / 模型分子目录，例如：

- `gpt5.4_judge/`
- `dpskv4pro_judge/`

每个 judge 子目录代表一套独立评分结果，不同目录之间互不覆盖。

## judge 子目录内文件含义

### 1. `summary.json`

全量或指定范围聚合后的汇总结果。

常见字段：

- `review_type`
  当前结果类型，固定为 `l3_prompt_score`
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
  所有任务平均分
- `complete_enough_count`
  被判定为 `complete_enough = true` 的任务数量
- `missing_description_count`
  缺失 `Function Description` 的任务数量
- `by_language`
  按语言聚合的统计
- `by_project`
  按项目聚合的统计

注意：

- 如果后来只对单个任务或单个项目重新跑过 aggregate，`summary.json` 可能被局部范围覆盖。
- 如果你需要全量汇总，请重新执行全量 `aggregate`。

### 2. `agent_runs.jsonl`

逐任务运行日志，JSON Lines 格式，一行一个任务执行记录。

常见字段：

- `task`
  任务 ID，例如 `go/chi/L3_mux__Find`
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
- 查看运行时间
- 追踪某次评分是否成功写入结果

### 3. `incomplete_run.json`

只在本次运行或聚合范围**不完整**时出现。

含义：

- 说明当前目标范围内仍有任务缺失评分结果
- 因此不会产出可信的完整汇总

常见字段：

- `total_expected`
  该次目标范围预期任务总数
- `completed`
  已完成评分的任务数
- `missing`
  缺失任务数
- `failed_tasks`
  缺失任务列表
- `resume_hint`
  提示你后续用 `--resume` 续跑

如果该文件存在，说明这次结果集还没完整，建议：

1. 继续 `run --resume`
2. 完成后再执行 `aggregate`

## 语言/项目子目录内文件含义

目录层级一般为：

- `{judge_dir}/{language}/{project}/`

例如：

- `gpt5.4_judge/go/chi/`
- `gpt5.4_judge/cpp/tinyxml2/`

该目录下通常包含三类文件。

### 1. 任务级评分结果：`L3_*.json`

每个任务一个 JSON。

例如：

- `L3_mux__Find.json`
- `L3_base64pp__decode.json`

常见字段：

- `task`
  完整任务 ID
- `project`
- `language`
- `prompt_path`
  被评分的任务 `prompt.md` 路径
- `task_json_path`
- `source_file_path`
  真实源码文件路径
- `target_symbol`
  `task.json.target`
- `function_extraction_status`
  完整函数实现抽取状态
- `judge_model`
- `description_present`
  是否成功提取到 `Function Description`
- `score`
  1.0 到 5.0 的单分数
- `reason`
  评分理由
- `missing_functionality`
  功能描述遗漏的要点
- `incorrect_or_misleading_points`
  功能描述中不准确或误导的部分
- `complete_enough`
  是否足以支持另一个模型实现该函数
- `raw_response_file`
  对应原始模型输出文件名

### 2. 模型原始输出：`L3_*.raw.md`

保存评分模型原始返回的 JSON 文本，通常是任务级结果写入前的原始响应。

用途：

- 调试评分提示词
- 核对模型原始判断
- 排查 JSON 解析问题

### 3. 项目级汇总：`L3_{project}.json`

例如：

- `L3_chi.json`
- `L3_tinyxml2.json`

这是单个项目内所有任务的聚合统计。

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
  该项目范围内的缺失任务

注意：

- 如果该项目部分任务结果被手动删除或等待重跑，这个项目级汇总会过时。
- 后续重新跑 `aggregate` 时会被重建。

## 如何理解几个核心字段

### `score`

单分数，范围 `1.0` 到 `5.0`。

它只评价：

- `Function Description` 是否和真实实现一致
- `Function Description` 是否足够完整

### `complete_enough`

布尔值。

含义：

- `true`
  表示这段功能描述足以支持模型实现该函数，而不遗漏重要行为
- `false`
  表示这段功能描述仍不够完整

### `missing_description_count`

聚合字段。

表示目标范围内有多少任务缺失 `Function Description`。

### `complete_enough_count`

聚合字段。

表示目标范围内有多少任务被判定为 `complete_enough = true`。

## 常见操作

### 1. 查某个任务的评分结果

进入对应项目目录，查看：

- `{task}.json`
- `{task}.raw.md`

### 2. 查失败或未完成任务

看：

- `incomplete_run.json`
- `agent_runs.jsonl`

### 3. 重建汇总

如果你修改了任务 prompt 或手动删除了部分任务级评分结果，原有：

- `summary.json`
- `L3_{project}.json`

可能已经过时。需要重新执行评分脚本的 `aggregate`。

## 说明

- 本目录是**结果目录**，不是源码目录。
- 其中 JSON/RAW 文件可能因为后续实验重新生成而变化。
- 如果你对某批任务进行了 prompt 重写并删掉了旧评分 JSON，那么这里的旧汇总文件在重新 aggregate 前都可能是过时的。
