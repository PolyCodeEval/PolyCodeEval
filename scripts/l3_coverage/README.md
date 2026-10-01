# L3 覆盖率分析

检测项目原始测试套件是否覆盖了 L3 任务对应的函数——即"测试是否触及了我们挖空的那个函数"。

## 原理

1. 对每个项目，在 Docker 容器中使用语言原生覆盖率工具运行原始测试（不做任何函数挖空）
2. 解析覆盖率报告，将 `stub_info.body_start_byte` 映射到源码行号
3. 查询该行是否被测试执行过，判定为 covered / uncovered / unknown

## 使用方式

```bash
# 单个项目
python scripts/check_l3_coverage.py --project datasets/go/script

# 某个语言下所有项目
python scripts/check_l3_coverage.py --language go --workers 4

# 全部项目
python scripts/check_l3_coverage.py --all --workers 4

# 强制重算（跳过已有结果）
python scripts/check_l3_coverage.py --language java --force
```

## 各语言覆盖率工具

| 语言 | 工具 | 报告格式 | 产出路径 |
|:---|:---|:---|:---|
| Go | `go test -coverprofile` | 文本 cover.out | `/workspace/coverage_out/cover.out` |
| Python | pytest-cov | JSON | `/workspace/coverage_out/coverage.json` |
| Java (Maven) | JaCoCo + `jacoco:report` | XML | `target/site/jacoco/jacoco.xml` |
| Java (Gradle) | JaCoCo + `jacocoTestReport` | XML | `build/reports/jacoco/` |
| JavaScript | Jest `--coverage` 或 nyc | json-summary | `/workspace/coverage_out/coverage-summary.json` |
| C++ | — | 不支持 | — |

## 判定逻辑

- **Go**：解析 `cover.out` 的行范围和执行计数，检查目标行是否落在 count > 0 的区间内
- **Python**：解析 `coverage.json` 的 `executed_lines` 列表，检查目标行是否在其中
- **Java**：解析 JaCoCo XML 中 `<sourcefile>` 下的 `<line>` 元素，检查目标行的 `ci`（covered instructions）是否 > 0；允许 ±3 行模糊匹配
- **JavaScript**：解析 Jest `coverage-summary.json`，按文件名匹配后检查 `lines.covered > 0`（文件级粒度，非行级）

## 输出格式

每个项目生成一个 JSON 文件（`results/coverage/{language}/{project}.json`）：

```json
{
  "project": "script",
  "language": "go",
  "total_tasks": 42,
  "covered": 38,
  "uncovered": 2,
  "unknown": 2,
  "tasks": {
    "L3_script__Bytes": {
      "covered": true,
      "file": "script.go",
      "func": "Bytes"
    }
  },
  "docker_exit_code": 0
}
```

所有项目完成后自动生成 `results/coverage/summary.json` 汇总。

## CLI 参数

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `--project <path>` | — | 单个项目目录 |
| `--language <lang>` | — | 某语言下所有 L3 项目 |
| `--all` | — | 全部 L3 项目 |
| `--output <path>` | `results/coverage/` | 结果输出目录 |
| `--workers N` | 2 | 并发 Docker 运行数 |
| `--force` | false | 强制重算，忽略已有结果 |

## 模块职责

| 文件 | 职责 |
|:---|:---|
| `commands.py` | 为各语言的 install/test 命令注入覆盖率参数 |
| `parsers.py` | 解析各语言覆盖率报告，判定目标行是否被覆盖 |
| `runner.py` | 编排 Docker 运行、收集结果、生成汇总 |
| `java_pom.py` | 自动向 `pom.xml` 注入 JaCoCo 插件声明 |
| `../check_l3_coverage.py` | CLI 入口脚本 |

## 覆盖率的意义

覆盖率回答的是："如果模型生成了错误的函数体，测试套件能否发现？"

- **covered**：测试执行过该函数 → 评测结果可信
- **uncovered**：测试从未执行该函数 → 即使模型生成了错误代码也可能通过测试
- **unknown**：无法判定（覆盖率工具未生成报告、文件匹配失败等）
