# L3 函数级评测题指南

## 一、什么是 L3 函数级评测题

L3 评测题的定义：给模型看一个源码文件，把其中某一个函数的函数体挖空（替换为语言对应的 stub），让模型补全该函数体。

- 一道题 = 一个函数被挖空，同文件其余函数保持完整
- 评测标准：将模型输出回填到 stub 位置后，运行项目原有的测试套件，全部通过 = pass

各语言的 stub：

| 语言 | stub |
|:---|:---|
| Python | `pass` |
| Go | `panic("not implemented")` |
| Java | `throw new UnsupportedOperationException();` |
| JavaScript/TypeScript | `throw new Error('not implemented')` |
| C++ | `/* not implemented */` |

---

## 二、题目是如何生成的

### 2.1 哪些函数会被挖空

生成器（`scripts/run_l3_slicer.py`）对每个项目执行以下流程：

1. 读取 `config.json` 中 `source_dirs` 指定的源码目录
2. 用 tree-sitter 解析每个源码文件的 AST，提取所有函数的位置信息
3. 过滤掉不适合出题的函数：
   - 函数体 < 10 行（trivial，没有评测价值）
   - 函数名为样板函数（`__init__`、`__str__`、`__repr__`、`setUp`、`tearDown`、`main`、`toString` 等）
   - 文件本身是测试文件（`test_*.py`、`*_test.go`、`*Test.java`、`*.test.js`、`*.spec.js`）
4. 每个非 trivial 函数生成一道题

### 2.2 每道题包含什么

```
tasks/L3_{file}__{func}/
├── task.json           # 元数据：target、stub_info、context_from_src
├── prompt.md           # 组装好的提示词（直接发给模型）
├── run_config.json     # 运行时配置：docker_image、test_command、src_dir 等
└── hollowed_files/
    └── {file}          # 只有这一个文件，目标函数体已替换为 stub
```

- `hollowed_files/` 只包含被挖空的那一个文件，不是整个项目的副本
- 运行测试时，评测器会把 `src/` 复制到临时目录，再用 `hollowed_files/` 中的文件覆盖对应位置

### 2.3 `task.json` 字段说明

```json
{
  "level": "L3",
  "target": "mux.go::NotFound",
  "hollowed_files": ["mux.go"],
  "context_from_src": ["chi.go", "tree.go", "..."],
  "stub_info": {
    "file": "mux.go",
    "func_name": "NotFound",
    "body_start_byte": 6718,
    "body_end_byte": 7085,
    "stub": "panic(\"not implemented\")",
    "lang": "go"
  }
}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `level` | string | 固定为 `"L3"` |
| `target` | string | `"文件路径::函数名"`，如 `"mux.go::NotFound"` |
| `hollowed_files` | list | 被挖空的文件路径列表（相对于 `src/`），当前始终只有一个元素 |
| `context_from_src` | list | 同项目其他源码文件路径列表（相对于 `src/`） |
| `stub_info.file` | string | 被挖空的文件路径（相对于 `src/`） |
| `stub_info.func_name` | string | 被挖空的函数名 |
| `stub_info.body_start_byte` | int | 函数体在原始 `src/` 文件中的起始字节偏移量 |
| `stub_info.body_end_byte` | int | 函数体在原始 `src/` 文件中的结束字节偏移量 |
| `stub_info.stub` | string | 替换函数体的 stub 字符串 |
| `stub_info.lang` | string | 语言名 |

### 2.4 `run_config.json` 字段说明

```json
{
  "docker_image": "golang:1.23-alpine",
  "install_command": "cd src && go mod download",
  "test_command": "cd src && go test ./...",
  "src_dir": "../../src",
  "hollowed_files": ["mux.go"]
}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `docker_image` | string | 运行测试用的 Docker 镜像 |
| `install_command` | string | 依赖安装命令 |
| `test_command` | string | 测试执行命令 |
| `src_dir` | string | 相对于任务目录的 `src/` 路径，固定为 `"../../src"` |
| `hollowed_files` | list | 需要覆盖工作区的文件列表（相对于 `src/`） |

评测器拿到一个任务目录后，只需读取 `run_config.json` 就能独立完成工作区组建和测试运行，无需回溯到项目根目录的 `config.json`。

### 2.5 `prompt.md` 的结构

```markdown
# Task
Complete the body of the `NotFound` function.

# Requirement Context
{从 docs/prd.md 中提取的与该函数相关的段落}

# Target File
## mux.go
{含 stub 的完整文件内容，模型能看到同文件其他函数}

# Called Definitions
## chi.go — func Chain(...)
{被挖空函数内部调用的其他函数/类的完整源码}

# Callers
## context.go — func RouteContext(...)
{项目中调用了被挖空函数的地方}
```

提示词不是把整个项目源码都给模型，而是只包含与被挖空函数强相关的上下文：
- 被挖空函数所在文件的完整内容（含 stub）
- 被挖空函数内部调用的其他函数/类的定义
- 项目中调用了被挖空函数的地方
- `prd.md` 中与该函数相关的需求段落

### 2.6 如何重新生成题目

```bash
# 生成单个项目
python scripts/run_l3_slicer.py --project datasets/go/chi

# 生成某语言所有项目
python scripts/run_l3_slicer.py --language go

# 生成全部项目
python scripts/run_l3_slicer.py --all
```

---

## 三、完整评测运行逻辑

### 3.1 评测的五个步骤

每道题的评测按以下顺序执行：

```
步骤 1：组建工作区
  读取 run_config.json，将 src_dir 指向的 src/ 完整复制到临时目录，
  再用 hollowed_files/ 中的文件覆盖临时目录中对应位置。
  结果：一个完整的项目目录，只有目标函数被挖空。

步骤 2：调用模型
  读取 prompt.md，发送给指定模型。
  模型返回目标函数的函数体字符串。

步骤 3：回填答案
  在工作区的挖空文件中，找到 stub 的位置，用模型输出替换 stub。
  结果：工作区中的文件恢复为完整可运行的状态。

步骤 4：运行测试
  启动 Docker 容器（镜像来自 run_config.json 的 docker_image），
  将工作区挂载到容器的 /workspace/src，
  在容器内依次执行 install_command 和 test_command，
  收集 exit code、stdout、stderr、耗时。

步骤 5：记录结果
  passed = (exit_code == 0)
  写入 results/{task_id}.json，清理临时工作区。
```

### 3.2 运行评测

```bash
# 评测单个任务（调试用）
python scripts/run_eval.py \
  --task datasets/go/chi/tasks/L3_mux__NotFound \
  --model anthropic/claude-opus-4-5

# 评测某个项目
python scripts/run_eval.py \
  --project datasets/go/chi \
  --model anthropic/claude-opus-4-5

# 评测某语言
python scripts/run_eval.py \
  --language go \
  --model anthropic/claude-opus-4-5

# 评测全部（并发）
python scripts/run_eval.py \
  --all \
  --model anthropic/claude-opus-4-5 \
  --workers 8 \
  --output results/run_20250115/
```

### 3.3 oracle 模式

`--model oracle` 是一个特殊模式，不调用任何模型 API，而是直接从 `src/` 读取原始函数体作为"答案"回填。用于验证评测流程本身的正确性——所有题目应 100% 通过，否则说明工作区组建或 Docker 挂载有问题。

```bash
python scripts/run_eval.py --all --model oracle
```

### 3.4 结果文件格式

每道题生成一个 `results/{task_id}.json`：

```json
{
  "task": "go/chi/L3_mux__NotFound",
  "model": "claude-opus-4-5",
  "passed": true,
  "exit_code": 0,
  "duration_seconds": 12.4,
  "stdout": "ok  \tgithub.com/go-chi/chi/v5\t0.432s\n...",
  "stderr": ""
}
```

汇总报告由 `scorer.py` 生成，按语言和项目分组统计通过率：

```json
{
  "model": "claude-opus-4-5",
  "total": 2388,
  "passed": 1456,
  "pass_rate": 0.610,
  "by_language": {
    "python":              {"total": 253, "passed": 145, "pass_rate": 0.573},
    "go":                  {"total": 464, "passed": 312, "pass_rate": 0.672},
    "java":                {"total": 234, "passed": 160, "pass_rate": 0.684},
    "cpp":                 {"total": 852, "passed": 489, "pass_rate": 0.574},
    "javascript/typescript": {"total": 585, "passed": 350, "pass_rate": 0.598}
  },
  "by_project": { "..." : "..." }
}
```

---

## 四、数据集目录结构参考

```
datasets/
└── {language}/
    └── {project}/
        ├── config.json              # 项目配置（语言、测试命令、Docker 镜像等）
        ├── src/                     # Oracle 源码（标准答案，不修改）
        ├── tests/                   # 测试套件
        ├── docs/
        │   └── prd.md               # 需求文档（用于生成 prompt.md）
        └── tasks/
            └── L3_{file}__{func}/
                ├── task.json        # 元数据 + stub_info
                ├── prompt.md        # 提示词（直接发给模型）
                ├── run_config.json  # 运行时配置
                └── hollowed_files/
                    └── {file}       # 只有这一个挖空文件
```

---

## 五、当前统计

| 语言 | 有任务的项目数 | L3 任务数 |
|:---|:---|:---|
| Python | 13/13 | 253 |
| Java | 11/11 | 234 |
| Go | 12/12 | 464 |
| C++ | 10/11 | 852 |
| JavaScript/TypeScript | 11/11 | 585 |
| **合计** | **57/58** | **2388** |

1 个项目生成 0 道题：
- `cpp/area_calculation`：所有函数均为 trivial（< 10 行）
