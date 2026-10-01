# L3 评分协议

## 1. 目标与范围

本协议定义了 PolyCodeEval 在 `L3` 函数级代码补全任务上的当前评分方式。

`L3` 的任务形式是：

- 给定一个源码文件
- 挖空其中一个目标函数体
- 保留同文件其余上下文
- 模型只需补全该函数体

本协议只描述当前仓库实现中的 `L3` 评分逻辑，不扩展到 `L0/L1/L2`。

与 `L0` 的多维工程化评分不同，当前 `L3` 采用的是**执行导向的部分分制**：

- 是否至少能编译 / 被测试框架识别
- 测试通过了多少

因此 `L3` 当前没有：

- `Faithfulness`
- `Architecture`
- `Health`

这三类维度。

## 2. 总分约定

`L3` 的总分范围是 `0.0–1.0`。

总分由两部分组成：

```text
score = compile_score + test_score
```

其中：

- `compile_score` 满分 `0.5`
- `test_score` 满分 `0.5`

因此：

- 完全失败：`0.0`
- 能编译但测试全挂：`0.5`
- 测试全过：`1.0`

## 3. 输入来源

`L3` 评分完全来自任务执行结果，不引入额外的 LLM Judge。

评分所依赖的输入包括：

- `passed`
- `exit_code`
- `stdout`
- `stderr`
- `test_details`

其中 `test_details` 来自测试输出解析器：

- Go：`go test -v`
- Python：`pytest`
- JavaScript：`Jest / Mocha`
- Java：`JUnit / Maven / Gradle`
- C++：`Google Test`

## 4. 评分流程

### 4.1 执行主流程

每个 `L3` 任务按以下步骤执行：

1. 组建工作区
2. 调用 solver 生成目标函数体
3. 回填目标函数体
4. 启动容器或复用长驻容器执行测试
5. 收集：
   - `passed`
   - `exit_code`
   - `stdout`
   - `stderr`
6. 从 `stdout` 中解析 `test_details`
7. 根据执行结果计算 `compile_score / test_score / score`

### 4.2 测试明细解析

当前实现通过 `parse_test_results(stdout, language)` 从测试输出提取：

```json
{
  "tests": [
    {"name": "TestFoo", "passed": true}
  ],
  "passed": 5,
  "failed": 1,
  "total": 6
}
```

如果语言对应的测试输出解析不到单测明细，则：

- `total = 0`
- `passed = 0`
- `failed = 0`

### 4.3 编译通过判定

当前实现中的 `compile_passed` 逻辑不是单纯看 `passed`，而是：

```text
compile_passed = passed OR (test_details.total > 0)
```

也就是说，只要：

- 任务最终完全通过，或者
- 测试输出里至少识别到了测试用例

就认为该任务至少已经“编译/进入测试阶段”。

这是一种比较实用的近似，因为对于 `L3` 而言：

- 如果代码根本不能编译，通常不会产出任何可解析测试结果
- 一旦能进入测试框架并出现测试用例，说明编译/装载阶段已经过去

### 4.4 分数计算

#### 情况 1：未通过编译/未进入测试阶段

如果：

```text
compile_passed = false
```

则：

```text
compile_score = 0.0
test_score = 0.0
score = 0.0
test_pass_ratio = 0.0
```

#### 情况 2：已通过编译/已进入测试阶段

如果：

```text
compile_passed = true
```

则：

```text
compile_score = 0.5
test_pass_ratio = passed_tests / total_tests
test_score = 0.5 * test_pass_ratio
score = compile_score + test_score
```

即：

```text
score = 0.5 + 0.5 * test_pass_ratio
```

### 4.5 示例

#### 示例 A：完全失败

- 代码无法编译
- 无法进入测试阶段

则：

```text
compile_score = 0.0
test_score = 0.0
score = 0.0
```

#### 示例 B：能编译，但测试全失败

- `compile_passed = true`
- `test_pass_ratio = 0.0`

则：

```text
compile_score = 0.5
test_score = 0.0
score = 0.5
```

#### 示例 C：测试通过一半

- `compile_passed = true`
- `test_pass_ratio = 0.5`

则：

```text
compile_score = 0.5
test_score = 0.25
score = 0.75
```

#### 示例 D：测试全过

- `compile_passed = true`
- `test_pass_ratio = 1.0`

则：

```text
compile_score = 0.5
test_score = 0.5
score = 1.0
```

## 5. 结果字段

每个 `L3` 任务的结果 JSON 在原始执行字段基础上，会追加以下评分字段：

```json
{
  "task": "go/chi/L3_context__Reset",
  "solver": "oracle",
  "passed": true,
  "exit_code": 0,
  "duration_seconds": 12.4,
  "stdout": "...",
  "stderr": "",
  "test_mode": "both",
  "test_details": {
    "tests": [
      {"name": "TestFoo", "passed": true}
    ],
    "passed": 5,
    "failed": 1,
    "total": 6
  },
  "compile_passed": true,
  "full_passed": true,
  "test_pass_ratio": 0.8333,
  "compile_score": 0.5,
  "test_score": 0.4167,
  "score": 0.9167
}
```

### 字段说明

| 字段 | 类型 | 含义 |
|:---|:---|:---|
| `test_mode` | string | 测试模式，取值为 `both` / `whitebox` / `blackbox` |
| `test_details` | dict | 从测试输出中解析出的测试明细 |
| `compile_passed` | bool | 是否至少进入了可测试阶段 |
| `full_passed` | bool | 是否最终所有测试都通过，等价于 `passed` |
| `test_pass_ratio` | float | `passed_tests / total_tests` |
| `compile_score` | float | 编译分，当前满分 `0.5` |
| `test_score` | float | 测试分，当前满分 `0.5` |
| `score` | float | 总分，范围 `0.0–1.0` |

## 6. 汇总逻辑

`L3` 的 `summary.json` 会输出：

- 全局统计
- 按语言统计
- 按项目统计
- 按任务逐条统计

### 顶层字段

```json
{
  "solver": "oracle",
  "total": 2388,
  "full_passed": 2377,
  "compile_passed": 2384,
  "full_pass_rate": 0.9954,
  "compile_pass_rate": 0.9983,
  "compile_score": 1192.0,
  "test_score": 1178.6,
  "avg_score": 0.9927,
  "total_score": 2370.6
}
```

### 统计含义

- `total`
  - 总任务数
- `full_passed`
  - 完全通过的任务数
- `compile_passed`
  - 至少进入可测试阶段的任务数
- `full_pass_rate`
  - `full_passed / total`
- `compile_pass_rate`
  - `compile_passed / total`
- `compile_score`
  - 所有任务 `compile_score` 之和
- `test_score`
  - 所有任务 `test_score` 之和
- `avg_score`
  - 所有任务 `score` 的平均值
- `total_score`
  - 所有任务 `score` 的总和

### `by_task`

每个任务会保留：

- `score`
- `compile_score`
- `test_score`
- `test_pass_ratio`

用于后续细粒度分析。

## 7. 失败语义

### 7.1 编译失败

如果任务既没有整体通过，也没有产生任何可解析测试明细，则视为未编译成功：

- `compile_passed = false`
- `score = 0.0`

### 7.2 测试失败

如果任务进入测试阶段但没有全部通过：

- `compile_passed = true`
- `full_passed = false`
- `score` 在 `(0.5, 1.0)` 或等于 `0.5`

### 7.3 测试输出无法解析

如果测试框架实际执行了，但 `stdout` 未被当前解析器识别，则：

- `test_details.total = 0`
- `compile_passed` 会退化为依赖 `passed`

这意味着：

- 若最终 `passed = true`，仍然可以拿到满分 `1.0`
- 若最终 `passed = false` 且解析不到测试明细，则该任务会被视为 `0.0`

这是当前实现的限制之一。

## 8. 如何解读 L3 分数

### `score = 1.0`

说明：

- 函数补全后的代码可以与项目集成
- 测试全部通过

### `score = 0.5`

说明：

- 代码至少已经编译/进入测试阶段
- 但功能行为没有通过测试

### `0.5 < score < 1.0`

说明：

- 代码能运行
- 部分测试通过
- 具备部分语义正确性

### `score = 0.0`

说明：

- 代码没有通过编译，或者
- 根本没进入测试执行阶段

## 9. 与 L0 的区别

`L3` 当前评分协议和 `L0` 有本质区别：

- `L0`
  - 使用四维评分
  - 引入 LLM Judge
  - 强调工程结构与需求达成
- `L3`
  - 只使用执行结果
  - 不引入架构/忠实度/健康度 Judge
  - 强调函数级可编译性与局部语义正确性

换句话说：

- `L0` 更像“项目交付能力评测”
- `L3` 更像“函数补全正确率评测”

## 10. 实现说明

当前 `L3` 实现的评分逻辑集中在：

- [task.py](scripts/l3_evaluator/task.py)
  - 负责给单任务附加 `compile_score / test_score / score`
- [scorer.py](scripts/l3_evaluator/scorer.py)
  - 负责按任务、语言、项目聚合统计

如果未来要扩展 `L3` 的评分协议，例如加入：

- 语义 Judge
- AST 结构对齐
- 风格或复杂度评分

应在本协议基础上新增版本，而不是直接覆盖当前 `0.5 + 0.5 * test_pass_ratio` 的口径。
