# L3 Direct API

这套脚本对应的是最朴素的 L3 流程：

- 输入只用每个 task 自带的 `prompt.md`
- 不拼临时仓库
- 不做 retrieval
- 直接把提示词发给大模型
- 要求模型返回纯函数体
- 先批量生成 `generated_code/`
- 再用 `precomputed:` 跑批量评测

它和下面这条命令的生成逻辑本质一致：

```bash
python3 scripts/run_l3_eval.py --language python --solver openai/gpt-5.4 --workers 4
```

区别只是这里把“生成”和“评测”拆开了，便于断点续跑、保存生成结果、后续反复评测。

## 输出格式

生成结果会写成：

```text
<output-dir>/generated_code/{language}/{project}/{task}.txt
```

这正好匹配 `precomputed:` solver 的目录要求。

脚本还会额外生成：

- `summary.json`
- `failures.json`

其中 `summary.json` 会统计输入/输出/总 token 用量。

## 只生成

### OpenAI 兼容接口

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://your-openai-compatible-endpoint/v1"

python3 scripts/L3_proxy/DirectAPI/run_api_batch.py \
  --language python \
  --provider openai \
  --model gpt-5.4 \
  --workers 4 \
  --resume \
  --output-dir output/direct_api_gpt54_python
```

只跑单个语言的前 5 个任务：

```bash
python3 scripts/L3_proxy/DirectAPI/run_api_batch.py \
  --language python \
  --provider openai \
  --model gpt-5.4 \
  --workers 4 \
  --limit 5 \
  --resume \
  --output-dir output/direct_api_gpt54_python_smoke
```

只跑单个项目：

```bash
python3 scripts/L3_proxy/DirectAPI/run_api_batch.py \
  --project datasets/python/marshmallow \
  --provider openai \
  --model gpt-5.4 \
  --workers 4 \
  --resume \
  --output-dir output/direct_api_gpt54_marshmallow
```

只跑单个 task：

```bash
python3 scripts/L3_proxy/DirectAPI/run_api_batch.py \
  --task datasets/python/marshmallow/tasks/L3_decorators__set_hook \
  --provider openai \
  --model gpt-5.4 \
  --output-dir output/direct_api_single
```

### Anthropic 官方接口

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"

python3 scripts/L3_proxy/DirectAPI/run_api_batch.py \
  --language python \
  --provider anthropic \
  --model claude-sonnet-4-6 \
  --workers 4 \
  --resume \
  --output-dir output/direct_api_claude_python
```

## 只评测

对上一步已经生成好的结果做批量评测：

```bash
python3 scripts/run_l3_eval.py \
  --language python \
  --solver precomputed:output/direct_api_gpt54_python/generated_code \
  --workers 16 \
  --tests both \
  --output output/direct_api_gpt54_python_eval
```

如果你想评测生成目录里已经覆盖到的全部语言，直接用：

```bash
python3 scripts/run_l3_eval.py \
  --all \
  --solver precomputed:output/direct_api_gpt54_python/generated_code \
  --workers 16 \
  --tests both \
  --output output/direct_api_gpt54_python_eval_all
```

注意：

- `--language python` 的含义是“评测整个 Python 数据集”
- 如果你的 `generated_code/python` 不是全覆盖，没生成到的 task 会按 0 分失败
- 所以不全量时，更推荐用 `--project`、`--task`，或者自己只对完整覆盖的语言目录运行

## 推荐两步命令

### 1. 批量生成

```bash
OPENAI_API_KEY='xxx' OPENAI_BASE_URL='https://yunwu.ai/v1' \
python3 scripts/L3_proxy/DirectAPI/run_api_batch.py \
  --language python \
  --provider openai \
  --model gpt-5.4 \
  --workers 4 \
  --resume \
  --output-dir output/direct_api_gpt54_python
```

### 2. 批量评测

```bash
python3 scripts/run_l3_eval.py \
  --language python \
  --solver precomputed:output/direct_api_gpt54_python/generated_code \
  --workers 16 \
  --tests both \
  --output output/direct_api_gpt54_python_eval
```

## 和 RepoCoder 的区别

- DirectAPI：只看 `prompt.md`
- RepoCoder：会基于仓库上下文做检索增强后再生成

所以如果你的目标是“纯基座模型能力”或“最简单基线”，用这里。
如果你的目标是“带代码仓库上下文的现有工作接入”，用 `RepoCoder/`。
