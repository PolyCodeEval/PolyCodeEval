# L0 评分协议

## 1. 目标与范围

本协议定义了 PolyCodeEval 在 `L0` 项目级代码生成任务执行完成之后，如何对结果进行评分。

本协议**只覆盖 `L0`**。`L1–L3` 不在当前协议范围内。

协议目标是把 `L0` 从“单纯 pass/fail 的执行型评测”升级为一个四维工程化评分体系：

- `Correctness`
- `Faithfulness`
- `Architecture`
- `Health`

这份协议既服务于实现，也服务于结果解释，并可作为后续报告、论文或实验说明的正式依据。

## 2. 总分约定

四个维度统一使用 `0–5` 分制。

- `0`：不可用，或存在明显严重失败
- `1–2`：质量较弱，存在明确缺陷
- `3`：部分可接受
- `4`：表现较强
- `5`：表现优秀

总分公式为：

```text
overall_score = 0.4*C + 0.25*F + 0.25*A + 0.1*H
```

其中：

- `C = Correctness`
- `F = Faithfulness`
- `A = Architecture`
- `H = Health`

当前实现中，如果任一非 `Correctness` 维度不能直接通过主链路得分，系统会优先进入回退逻辑；只有在主链路和回退链路全部失败时，该维度才会为 `null`。  
若任一非 `Correctness` 维度最终仍为 `null`，则 `overall_score = null`。

## 3. 各维度输入

### Correctness

`Correctness` 使用当前已有的 Docker 执行结果：

- 任务级 `passed`
- `test_details.passed`
- `test_details.failed`
- `test_details.total`

### Faithfulness

`Faithfulness` 的主输入固定为：

- `tasks/L0_*/prompt.md`

这是刻意的设计。`L0` 评测的是“模型实际被要求生成什么”，因此需求忠实度必须以**实际下发给模型的 prompt** 为准，而不是以隐藏的原始 PRD 为准。

辅助输入包括：

- 生成仓库的文件树
- 从仓库中检索出的源码证据片段

### Architecture

`Architecture` 的主输入固定为：

- 生成仓库的文件树

这也是刻意的设计。`L0` 不应该过度依赖具体源码实现细节；目录组织、模块边界、入口结构、命名方式，通常是架构最稳定、最可泛化的观察面。

辅助输入包括：

- prompt 需求摘要
- 推断出的技术栈画像
- 少量关键源码片段
- 可选的在线参考架构信息

### Health

`Health` 使用生成仓库的静态分析输出：

- `lizard` 圈复杂度统计
- 超长行统计
- 行尾空白统计
- 各语言附加检查：
  - Python：`flake8`
  - Go：`gofmt -l`、`go vet`
  - JavaScript：优先 `eslint`，否则退化为语法检查
  - Java / C++：当前版本只做通用复杂度和文本规范检查

## 4. 评分流程

### 4.1 Correctness

`Correctness` 完全由测试执行结果决定。

规则如下：

- 如果 `test_details.total > 0`
  - `C = 5 * passed / total`
- 如果 `test_details.total == 0` 且任务整体通过
  - `C = 5.0`
- 如果 `test_details.total == 0` 且任务整体失败
  - `C = 0.0`

当前版本中，`Correctness` 不再拆出额外的 coverage 或 E2E 二级权重。

### 4.2 Faithfulness

`Faithfulness` 用于判断：生成项目是否真正实现了 prompt 中要求的内容。

流程如下：

1. 读取 `prompt.md`
2. 提取项目需求区块
3. 从需求中抽取 requirement 候选项，并分成：
   - `feature`
   - `constraint`
4. 为每条 requirement 分配稳定 id，例如：
   - `F001`
   - `C001`
5. 针对每条 requirement 在生成仓库中搜索证据：
   - 路径命中
   - 标识符命中
   - 文本片段命中
6. 将 requirement 与证据一并送给 Judge
7. Judge 对每条 requirement 输出以下四类之一：
   - `implemented`
   - `partial`
   - `missing`
   - `unclear`
8. 将标签映射为数值覆盖率：
   - `implemented = 1.0`
   - `partial = 0.5`
   - `missing = 0.0`
   - `unclear = 0.0`
9. 计算：
   - `feature_coverage`
   - `constraint_coverage`
10. 最终得分：

```text
F = 5 * (0.7 * feature_coverage + 0.3 * constraint_coverage)
```

如果没有 `constraint`，则：

```text
constraint_coverage = feature_coverage
```

#### Faithfulness 回退逻辑

如果 Judge 调用失败、连接失败、返回不可解析内容，系统不会直接给 `null`，而是进入启发式回退：

- 每条 requirement 根据 evidence 数量进行近似判断
  - evidence ≥ 2：`implemented`
  - evidence = 1：`partial`
  - evidence = 0：`missing`
- 输出的 `dimension_details.faithfulness.status` 会标记为 `fallback`

这样即使外部 Judge 不可用，`Faithfulness` 仍然可以给出一个保底可解释分数。

### 4.3 Architecture

`Architecture` 用于判断：生成仓库的结构是否清晰、是否匹配技术栈、是否符合该类项目的架构实践。

#### 步骤 A：文件树摘要

先从生成仓库构造文件树摘要。  
这是 `Architecture` 的主观察面。

#### 步骤 B：技术栈推断

从以下信号推断 `stack_profile`：

- 文件名
- 构建文件
- 依赖文件
- 框架关键字
- 入口命名

输出字段包括：

- `language`
- `framework`
- `app_style`
- `build_system`
- `persistence`
- `frontend_presence`
- `confidence`

#### 步骤 C：在线参考架构检索

如果技术栈推断成功，系统会尝试基于以下输入检索在线参考架构：

- prompt 需求摘要
- 推断出的技术栈
- 仓库文件树摘要

检索目标不是“找完全一样的项目”，而是：

- 相似项目类型
- 相同或接近的技术栈
- 架构最佳实践
- 推荐的目录组织方式

期望检索输出：

- `reference_sources`
- `reference_architecture_summary`
- `reference_checklist`

#### 步骤 D：Judge 评分

Judge 需要输出 3 个子分：

- `structure_reasonableness`
- `stack_alignment`
- `reference_alignment`

最终架构分：

```text
A = (structure_reasonableness + stack_alignment + reference_alignment) / 3
```

### 4.4 Architecture 回退语义

`Architecture` 有明确的多层回退路径。

#### 模式 1：`online_reference_compare`

适用条件：

- 技术栈推断成功
- 在线检索成功
- 返回的参考信息质量足够

解释：

- `reference_alignment` 基于外部参考架构对比

#### 模式 2：`local_stack_judge`

适用条件：

- 技术栈推断成功
- 在线检索结果过弱、无关或明显不匹配

解释：

- Judge 回退为“基于本地上下文的专家自评”
- 仍然输出 3 个子分
- `reference_alignment` 退化为“与该技术栈合理实践的自我对照”

#### 模式 3：`offline_autonomous_judge`

适用条件：

- 在线检索不可用
- provider 不支持 web search
- 网络或工具链调用失败

解释：

- Judge 只使用：
  - prompt 摘要
  - 文件树
  - 技术栈推断结果
  - 少量关键源码片段
- 只要技术栈推断成功，仍然可以给出架构分

#### 模式 4：启发式回退

如果：

- 在线检索失败
- 本地 Judge 失败
- 离线 Judge 也失败

系统不会直接给 `null`，而会进入启发式架构回退：

- 基于文件数、是否有测试、是否有文档、是否有构建元数据、是否能识别出基础技术栈
- 给出保底的 `structure_reasonableness / stack_alignment / reference_alignment`
- `dimension_details.architecture.status = "fallback"`

#### 模式 5：`hard_failure`

理论上只有在以下情况下才会出现：

- 技术栈完全无法推断
- 文件树本身也无法构造
- 连启发式回退都无法建立最小上下文

在当前实现中，这种情况已经被大幅压缩到极少出现。

### 4.5 Health

`Health` 是规则型静态质量分。

使用的指标：

- 平均复杂度 `avg_ccn`
- 最大复杂度 `max_ccn`
- 超过复杂度阈值的函数数量
- 超长行数量
- 行尾空白数量
- 各语言附加 issue 数量

评分从 `5.0` 开始扣分。

#### 复杂度扣分

- `0.0`：如果 `max_ccn <= 15` 且 `avg_ccn <= 10`
- `0.5`：如果 `max_ccn <= 20` 且 `avg_ccn <= 15`
- `1.0`：如果 `max_ccn <= 30` 且 `avg_ccn <= 20`
- `1.5`：否则

#### 风格 / issue 扣分

定义：

```text
issue_count = line_length_violations + trailing_whitespace_violations + language_specific_issue_count
```

扣分规则：

- `0.0`：如果 `issue_count == 0`
- `0.5`：如果 `1 <= issue_count <= 10`
- `1.0`：如果 `11 <= issue_count <= 50`
- `2.0`：如果 `issue_count > 50`

#### 致命语言特定错误

如果语言特定静态检查报告了致命失败，则额外扣 `1.0`。

最终得分被 clamp 到 `[0, 5]`。

#### Health 回退逻辑

如果 Docker 内静态分析输出缺失、工具执行异常、输出无法解析，系统不会直接返回 `null`，而是进入本地启发式回退：

- 本地统计超长行
- 本地统计行尾空白
- 给出一个保底健康分
- `dimension_details.health.status = "fallback"`

## 5. 输出字段

每个任务的结果 JSON 包含：

```json
{
  "result_schema_version": "l0_scoring_v3",
  "score_scale": "0-5",
  "score_formula": "0.4*C + 0.25*F + 0.25*A + 0.1*H",
  "radar_scores": {
    "Correctness": 0.0,
    "Faithfulness": 0.0,
    "Architecture": 0.0,
    "Health": 0.0
  },
  "overall_score": 0.0,
  "dimension_details": {
    "correctness": {},
    "faithfulness": {},
    "architecture": {},
    "health": {}
  },
  "judge_reviews": {
    "faithfulness_review": "",
    "architecture_review": ""
  }
}
```

### `dimension_details.correctness`

- `tests_passed`
- `tests_failed`
- `tests_total`
- `test_pass_ratio`
- `derived_from`

### `dimension_details.faithfulness`

- `requirements`
- `feature_count`
- `constraint_count`
- `implemented_count`
- `partial_count`
- `missing_count`
- `unclear_count`
- `feature_coverage`
- `constraint_coverage`
- `fallback_used`

### `dimension_details.architecture`

- `stack_profile`
- `reference_mode`
- `reference_sources`
- `reference_architecture_summary`
- `reference_checklist`
- `subscores`
- `fallback_reason`

### `dimension_details.health`

- `avg_ccn`
- `max_ccn`
- `functions_over_15`
- `line_length_violations`
- `trailing_whitespace_violations`
- `language_specific_issue_count`
- `tool_results`

## 6. 失败语义

### Correctness

`Correctness` 不返回 `null`。  
它总能由测试结果导出。

### Faithfulness

只有当 Judge 主链和启发式回退都失败时，才会返回 `null`。  
在当前实现中，正常情况下应尽量避免出现这种情况。

### Architecture

只有在：

- 技术栈无法推断
- 在线、离线、本地 Judge 全部失败
- 启发式回退也无法建立最小上下文

时，`Architecture` 才可能为 `null`。

### Health

只有在：

- Docker 输出缺失
- 本地 fallback 也无法得到最小统计

时，`Health` 才可能为 `null`。

### Overall

如果 `F/A/H` 中任一维度最终仍为 `null`：

- `overall_score = null`

不过在当前版本中，系统的设计目标是通过重试与 fallback，把这种情况压缩到极少出现。

## 7. 结果解释方式

### 高 `C`，低 `A`

说明：

- 项目功能测试能过
- 但结构混乱、分层弱、实现方式不够惯用

常见场景：

- “能跑，但结构不优雅”

### 高 `A`，低 `F`

说明：

- 结构看起来合理
- 但 prompt 要求的能力没有真正交付完整

常见场景：

- “骨架好看，但漏功能”

### 高 `F`，低 `C`

说明：

- 看起来试图实现了要求
- 但运行时行为不正确

### 高 `H`，低 `C`

说明：

- 代码风格与复杂度控制不错
- 但并没有产生正确运行结果

### `scoring_coverage`

表示：

- 在一批任务中，有多少比例得到了完整 `overall_score`

它很重要，因为：

- 如果大量任务 Judge 失败或 fallback 失败，单纯看平均分会误导结论
- `coverage` 能帮助判断该批结果是否“完整可信”

## 8. 示例：单任务结果

```json
{
  "task": "go/chi/L0_chi",
  "solver": "openai/gpt-4o-mini",
  "passed": true,
  "radar_scores": {
    "Correctness": 5.0,
    "Faithfulness": 4.25,
    "Architecture": 4.1,
    "Health": 4.5
  },
  "overall_score": 4.56,
  "dimension_details": {
    "architecture": {
      "reference_mode": "online_reference_compare",
      "fallback_reason": "",
      "subscores": {
        "structure_reasonableness": 4.2,
        "stack_alignment": 4.0,
        "reference_alignment": 4.1
      }
    }
  }
}
```

## 9. 示例：汇总结果

```json
{
  "solver": "openai/gpt-4o-mini",
  "total": 12,
  "passed": 7,
  "pass_rate": 0.5833,
  "scored_tasks": 11,
  "scoring_coverage": 0.9167,
  "avg_overall_score": 3.8421,
  "avg_correctness": 3.9545,
  "avg_faithfulness": 3.7018,
  "avg_architecture": 3.9364,
  "avg_health": 4.2091
}
```

## 10. 实现说明

- `Faithfulness` 以 `prompt.md` 为主输入，因为 `L0` 应该评估模型真正收到的任务描述
- `Architecture` 以文件树为主输入，因为仓库组织是最稳定的架构信号
- 在线检索优先，但不是唯一途径
- fallback 不是“临时补丁”，而是当前协议中的正式组成部分
- 当前实现目标是：在结果可解释性的前提下，尽可能避免 `n/a`
