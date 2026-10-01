# 提示词质量验证方案

## 目标

各层级评测以提示词（PRD / Prompt）作为模型输入，提示词质量直接决定评测有效性。本方案通过多模型交叉评分与投票机制，系统性验证各层级任务的提示词质量。

## 评分模型

使用以下 5 个大语言模型独立评分：

| 模型 | 提供方 |
|------|--------|
| GPT-5.4 | OpenAI |
| Claude Sonnet 4.6 | Anthropic |
| Gemini 3.5 Flash | Google |
| DeepSeek-V4 | DeepSeek |
| GLM-5.1 | 智谱 |

## 评分维度

每个维度 1-5 分：

1. **完整性（Completeness）** — 提示词是否提供了足够的上下文信息（函数签名、依赖、调用方、接口契约等）
2. **无歧义性（Unambiguity）** — 需求描述是否足够清晰，不会导致多种合理但互斥的实现
3. **可测试性（Testability）** — 提示词中的需求是否能通过测试用例验证，是否有明确的验收标准
4. **与实现一致性（Consistency）** — 提示词描述是否与代码上下文、项目结构保持一致，无自相矛盾

## 各层级维度权重

不同层级的任务性质不同，四个维度的重要性存在显著差异：

| 维度 | L3（函数级） | L2（文件级） | L1（模块级） | L0（项目级） |
|:---|:---:|:---:|:---:|:---:|
| **Completeness** | 0.50 | 0.40 | 0.30 | 0.30 |
| **Unambiguity** | 0.30 | 0.30 | 0.25 | 0.25 |
| **Consistency** | 0.15 | 0.20 | 0.30 | 0.30 |
| **Testability** | 0.05 | 0.10 | 0.15 | 0.15 |

### 权重设计依据

**L3 函数级**：提示词的核心职责是给够上下文让模型生成可拼接运行的代码。completeness 权重最高（0.50）——函数签名、参数类型、依赖的类/方法、调用方期望的返回格式缺一不可。unambiguity 其次（0.30），确保行为描述清晰、模型不用猜。consistency 较低（0.15），函数级上下文小，矛盾少见。testability 最低（0.05），评测框架自带测试用例，提示词不需要承担验收标准的职责。

**L2 文件级**：模型生成整个文件，需要完整的接口契约和依赖关系（completeness 0.40）。文件级涉及多个函数协作，歧义影响更大（unambiguity 0.30）。文件需要与项目其他模块对接，一致性开始重要（consistency 0.20）。

**L1 模块级**：任务涉及多文件协作，completeness 仍然主导（0.35）但开始让位给 consistency（0.25），因为多文件间的接口一致性直接影响能否正确集成。unambiguity 降低（0.25），模块级允许一定实现自由度。

**L0 项目级**：任务复杂度最高，模型需要做全局架构决策。consistency 权重最高（0.30）——PRD 各模块描述之间不能自相矛盾，否则模型无法做出一致的设计。completeness 仍然重要（0.30），但项目级 PRD 天然较完整。unambiguity 保持（0.25），允许实现自由度。testability 上升（0.15），项目级需要明确的验收边界。

### 加权评分计算

```
weighted_score = unambiguity × W_u + testability × W_t + completeness × W_c + consistency × W_s
```

各维度原始分为 1-5，权重之和为 1.0，因此加权分范围为 **1.0 ~ 5.0**。

### 通过阈值

所有层级使用统一阈值：**加权分 ≥ 3.5**（满分 5.0）。

不同层级的严格程度通过权重分配来控制——权重高的维度如果得分低，会更显著地拉低加权分，从而更容易触发修订。例如 L3 的 completeness 权重 0.45，该维度得 3 分就会贡献 1.35，而 testability 权重 0.05 只贡献 0.15。

### 硬性否决规则

无论加权分是否达标，以下情况直接标记为需修订：

- 任何维度得分 ≤ 2（存在严重缺陷）
- L3/L2：completeness ≤ 2 或 unambiguity ≤ 2
- L1/L0：completeness ≤ 2 或 consistency ≤ 2

## 评分 Prompt

```
你是一位资深的软件工程评审专家。请对以下提示词进行质量评估。

评估对象：
- 提示词内容：{prompt_content}
- 任务层级：{level}（L0=项目级 / L1=模块级 / L2=文件级 / L3=函数级）
- 项目语言：{language}

请从以下四个维度分别给出 1-5 分的评分，并附简要理由：

1. 完整性（1-5）：提示词是否提供了足够的上下文信息？对于 L3 需包含函数签名、关键依赖和调用方；对于 L0 需覆盖全部核心功能模块。
2. 无歧义性（1-5）：需求描述是否足够清晰精确？是否存在可能导致多种合理但互斥实现的模糊表述？边界条件、异常处理、分支逻辑是否明确？
3. 可测试性（1-5）：提示词中描述的需求是否有明确的验收标准？是否提供了输入输出示例或可量化的行为约束？
4. 与实现一致性（1-5）：提示词描述是否与代码上下文保持一致？是否存在自相矛盾或技术上不可行的需求？

输出格式：
{
  "completeness": {"score": <int>, "reason": "<string>"},
  "unambiguity": {"score": <int>, "reason": "<string>"},
  "testability": {"score": <int>, "reason": "<string>"},
  "consistency": {"score": <int>, "reason": "<string>"}
}
```

## 投票与决策机制

1. 每个维度取 5 个模型评分的**中位数**作为最终得分
2. 按任务所属层级选取对应权重，计算加权分（满分 5.0）
3. 加权分 ≥ 3.5：提示词通过验证
4. 加权分 < 3.5，或触发硬性否决规则：进入人工修订流程，修订后重新评分

## 执行流程

```
WEIGHTS = {
    "L3": {"completeness": 0.50, "unambiguity": 0.30, "consistency": 0.15, "testability": 0.05},
    "L2": {"completeness": 0.40, "unambiguity": 0.30, "consistency": 0.20, "testability": 0.10},
    "L1": {"completeness": 0.35, "unambiguity": 0.25, "consistency": 0.25, "testability": 0.15},
    "L0": {"completeness": 0.30, "unambiguity": 0.25, "consistency": 0.30, "testability": 0.15},
}

THRESHOLD = 3.50  # 统一阈值，所有层级相同

VETO_DIMS = {
    "L3": ["completeness", "unambiguity"],
    "L2": ["completeness", "unambiguity"],
    "L1": ["completeness", "consistency"],
    "L0": ["completeness", "consistency"],
}

for each task in all_tasks:
    prompt = load_prompt(task)
    level = task.level  # L0 / L1 / L2 / L3
    scores = {}
    for model in [gpt54, claude_sonnet46, gemini35flash, deepseekv4, glm51]:
        scores[model] = evaluate_prompt(model, prompt, level)
    
    final_scores = median(scores, axis=models)
    
    # 硬性否决
    vetoed = False
    for dim in VETO_DIMS[level]:
        if final_scores[dim] <= 2:
            flag_for_revision(task, reason=f"{dim} <= 2")
            vetoed = True
            break
    if vetoed:
        continue
    
    # 加权分（满分 5.0）
    w = WEIGHTS[level]
    weighted_score = sum(final_scores[dim] * w[dim] for dim in w)
    
    if weighted_score < THRESHOLD:
        flag_for_revision(task, reason=f"weighted_score={weighted_score:.2f} < {THRESHOLD}")
```

## 输出产物

- `results/prompt_validation/scores.json` — 每个任务、每个模型的详细评分
- `results/prompt_validation/summary.json` — 聚合统计（按语言、按层级、按维度）
- `results/prompt_validation/flagged.json` — 需人工修订的任务列表（含原因）

## 状态

- [ ] 实现评分脚本（支持多层级加权总分）
- [ ] 对 L0 全部 58 个项目 PRD 执行评分
- [ ] 对 L3 抽样 50 个任务执行评分（已完成 gpt-5.4 单模型试跑）
- [ ] 补充其余 4 个模型评分，取中位数
- [ ] 汇总结果，生成 flagged 列表
- [ ] 人工修订低分提示词
- [ ] 重新验证修订后的提示词
