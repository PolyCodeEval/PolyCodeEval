#!/usr/bin/env python3
"""AlignCoder 推理入口（在 Docker 容器内运行）。

由 adapter.py 通过 docker exec -i 调用：
  stdin:  JSON 格式的 Example 数据 + 推理参数
  stdout: JSON 格式的 {"completion", "input_tokens", "output_tokens",
                       "draft_input_tokens", "draft_output_tokens"}
  stderr: 日志/调试信息
"""

import json
import os
import sys
import time
from pathlib import Path

# suppress tokenizers fork warnings flooding stderr
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

sys.path.insert(0, '/workspace/L3works/AlignCoder')

# 直接从各模块导入，完全绕开 main.py 和 generator.py 的顶层 vllm 导入
from datasets import CodeBlock, Example
from bm25 import TaskSpecificBM25
from retriever import Retriever
import argparse
import torch
from torch.utils.data import Dataset


# ---------------------------------------------------------------------------
# CustomDataset: 从 AlignCoder/generator.py 内联（完全保留原始逻辑）
# 不导入 generator.py，因为其顶层有 from vllm import LLM 我们不需要
# ---------------------------------------------------------------------------

class CustomDataset(Dataset):
    def __init__(self, args, tokenizer, examples, retrieved_codeblocks, generation=False):
        self.args = args
        self.tokenizer = tokenizer
        self.examples = examples
        self.retrieved_codeblocks = retrieved_codeblocks
        self.generation = generation

    def __len__(self):
        return len(self.examples)

    def construct_prompts(self, example, retrieved_codeblocks):
        filter_codeblocks = []
        for x in retrieved_codeblocks:
            if x.file_path != "":
                filter_codeblocks.append(x)
            else:
                break

        crossfile_context = "\n\n".join([str(cb) for cb in filter_codeblocks])
        crossfile_context = self.tokenizer.encode(
            crossfile_context[:self.args.generator_max_crossfile_length * 10],
            add_special_tokens=False)[:self.args.generator_max_crossfile_length]
        path_context = f"\n\n# file path: {example.file_path}\n\n"
        path_context = self.tokenizer.encode(path_context, add_special_tokens=False)
        allowed_prompt_length = (self.args.generator_max_context_length
                                 - len(crossfile_context) - len(path_context) - 10)
        infile_context = self.tokenizer.encode(
            example.left_context, add_special_tokens=False)[-allowed_prompt_length:]
        prompt = self.tokenizer.decode(crossfile_context + path_context + infile_context)
        return prompt

    def __getitem__(self, idx):
        example = self.examples[idx]
        retrieved_codeblocks = self.retrieved_codeblocks[idx]
        prompt = self.construct_prompts(example, retrieved_codeblocks)
        prompt_ids = self.tokenizer.encode(prompt)[-self.args.generator_max_context_length:]
        if self.generation:
            padding_length = self.args.generator_max_context_length - len(prompt_ids)
            input_ids = [self.tokenizer.pad_token_id] * padding_length + prompt_ids
            return torch.tensor(input_ids)
        target_ids = self.tokenizer.encode(
            example.target_code, add_special_tokens=False)[:self.args.generator_max_generation_length]
        input_ids = prompt_ids + target_ids
        labels = [-100 for _ in prompt_ids] + target_ids
        padding_length = (self.args.generator_max_context_length
                          + self.args.generator_max_generation_length - len(input_ids))
        input_ids = [self.tokenizer.pad_token_id] * padding_length + input_ids
        labels = [-100] * padding_length + labels
        return torch.tensor(input_ids), torch.tensor(labels)


# ---------------------------------------------------------------------------
# retrieve_codeblocks: 从 AlignCoder/main.py 内联（完全保留原始逻辑）
# 不通过 main.py 导入，因为 main.py 顶层会导入 vllm（我们不需要）
# ---------------------------------------------------------------------------

def retrieve_codeblocks(args, examples, bm25, retriever, dataset_name,
                        is_training=False, inference_type=None):
    if inference_type is None:
        inference_type = args.inference_type
    if inference_type == "baseline":
        return None, [[] for _ in range(len(examples))]

    bm25_topk, unixcoder_topk, context_len = 5, 5, 20
    if inference_type in ["bm25", "unixcoder", "unixcoder_with_rl"]:
        if dataset_name not in bm25:
            bm25[dataset_name] = TaskSpecificBM25(examples, args)

        if inference_type == "unixcoder":
            bm25_topk = 50
        elif inference_type == "unixcoder_with_rl":
            bm25_topk = args.sample_number * 10
            unixcoder_topk = args.sample_number

        if args.enable_prediction:
            queries = ["\n".join([x for x in example.left_context.split("\n")
                                  if x.strip() != ""][-context_len:])
                       for example in examples]

            if args.add_api_blocks:
                candidate_codeblocks = bm25[dataset_name].query_with_api(
                    [x.task_id for x in examples], queries, topk=bm25_topk)
            else:
                candidate_codeblocks = bm25[dataset_name].query(
                    [x.task_id for x in examples], queries, topk=bm25_topk)

            # generator 是全局 APIGenerator 实例（由 main() 注入）
            generations, counts = generator.generate(
                examples, candidate_codeblocks,
                args.temperature1, args.top_p1,
                args.number_sample, deduplicated=True)
            candidate_batches = []
            start_idx = 0
            for count in counts:
                candidate_batches.append(generations[start_idx:start_idx + count])
                start_idx += count
            queries = [
                query + "\n\n" + "\n\n".join([
                    f"# candidate answer {i + 1}:\n{candidate}"
                    for i, candidate in enumerate(candidates)
                ])
                for query, candidates in zip(queries, candidate_batches)
            ]

        elif args.enable_oracle:
            queries = [
                "\n".join([x for x in example.left_context.split("\n")
                           if x.strip() != ""][-context_len:]) + example.target_code
                for example in examples
            ]
        else:
            queries = [
                "\n".join([x for x in example.left_context.split("\n")
                           if x.strip() != ""][-context_len:])
                for example in examples
            ]

        candidate_codeblocks = bm25[dataset_name].query(
            [x.task_id for x in examples], queries, topk=bm25_topk)

        if args.add_api_blocks:
            for example, codeblock in zip(examples, candidate_codeblocks):
                api_blocks = bm25[dataset_name].api_blocks[example.task_id]
                codeblock.extend(api_blocks)

        # enable_repocoder 我们不使用，跳过该分支

        if inference_type == "bm25":
            return queries, candidate_codeblocks
        elif inference_type == "unixcoder":
            return queries, retriever.retrieve(queries, candidate_codeblocks, topk=unixcoder_topk)
        elif inference_type == "unixcoder_with_rl":
            # 统计 AlignRetriever 输入序列长度（近似 token 数）
            global retriever_approx_tokens
            _q_chars = sum(len(q) for q in queries)
            _c_chars = sum(len(b.code_content) for blocks in candidate_codeblocks for b in blocks)
            retriever_approx_tokens += (_q_chars + _c_chars) // 4

            if is_training:
                if args.disable_stop_block:
                    candidate_codeblocks = retriever.retrieve(
                        queries, candidate_codeblocks, topk=unixcoder_topk)
                else:
                    candidate_codeblocks = retriever.retrieve(
                        queries, candidate_codeblocks, topk=unixcoder_topk - 1)
                    candidate_codeblocks = [
                        x + [CodeBlock("", "Don't need cross file context for completion",
                                       "", y.language, '')]
                        for x, y in zip(candidate_codeblocks, examples)
                    ]
            else:
                if not args.disable_stop_block:
                    candidate_codeblocks = [
                        x + [CodeBlock("", "Don't need cross file context for completion",
                                       "", y.language, '')]
                        for x, y in zip(candidate_codeblocks, examples)
                    ]
                candidate_codeblocks = retriever.retrieve(
                    queries, candidate_codeblocks, topk=unixcoder_topk)

            return queries, candidate_codeblocks

    raise ValueError("Unsupported inference type: {}".format(inference_type))


# ---------------------------------------------------------------------------
# APIGenerator: 实现与 AlignCoder vLLM_online_Generator 相同的接口
# 用 OpenAI API 替代本地模型，思路完全等价（普通预训练 base 模型的随机采样）
# ---------------------------------------------------------------------------

class APIGenerator:
    """用 OpenAI/Anthropic API 实现 AlignCoder Generator 接口。

    AlignCoder 原始代码用 deepseek-coder-1.3b-base 做草稿生成（未微调）。
    这里用 GPT-5.4 替代，思路完全一致：都是从预训练代码模型做随机采样。
    接口对齐 vLLM_online_Generator.generate(examples, codeblocks, temperature, top_p, sample_number, deduplicated)
    """

    def __init__(self, provider: str, model_name: str, tokenizer, args):
        self.provider = provider
        self.model_name = model_name
        self.tokenizer = tokenizer
        self.args = args
        # 用于统计草稿生成消耗的 token
        self.draft_input_tokens = 0
        self.draft_output_tokens = 0

    def generate(self, examples, retrieved_codeblocks, temperature, top_p,
                 sample_number=0, deduplicated=False):
        """采样 sample_number 个候选答案用于 query enhancement。"""
        all_completions = []
        counts = []
        # 收集所有草稿（供外部记录调试信息）
        self.all_draft_candidates = []

        for i, example in enumerate(examples):
            codeblocks = retrieved_codeblocks[i] if i < len(retrieved_codeblocks) else []
            dataset = CustomDataset(self.args, self.tokenizer, [example], [codeblocks], generation=True)
            prompt_text = dataset.construct_prompts(example, codeblocks)

            candidates, in_tok, out_tok = self._sample_n(prompt_text, temperature, top_p, sample_number)
            self.draft_input_tokens += in_tok
            self.draft_output_tokens += out_tok

            if deduplicated:
                seen = []
                for c in candidates:
                    if c not in seen:
                        seen.append(c)
                candidates = seen

            all_completions.extend(candidates)
            counts.append(len(candidates))
            self.all_draft_candidates.append(candidates)

        return all_completions, counts

    def _sample_n(self, prompt: str, temperature: float, top_p: float, n: int):
        """调用 API 采样 n 个候选，返回 (candidates, input_tokens, output_tokens)。"""
        import random

        # 构建带代理的 httpx client（读取 HTTP_PROXY/HTTPS_PROXY 环境变量）
        def _make_http_client():
            import httpx
            proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
            if proxy:
                return httpx.Client(proxy=proxy)
            return httpx.Client()

        if self.provider == "openai":
            from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError
            client = OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url=os.environ.get("OPENAI_BASE_URL") or None,
                http_client=_make_http_client(),
                timeout=120.0,
            )

            max_retries = 8
            base_delay = 15
            for attempt in range(max_retries):
                try:
                    resp = client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": (
                                "You are an expert programmer. Complete the code. "
                                "Return ONLY the code continuation, no explanation."
                            )},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=256,
                        temperature=temperature,
                        top_p=top_p,
                        n=n,
                    )
                    candidates = [choice.message.content or "" for choice in resp.choices]
                    usage = resp.usage
                    in_tok = usage.prompt_tokens if usage else 0
                    out_tok = usage.completion_tokens if usage else sum(len(c.split()) for c in candidates)
                    return candidates, in_tok, out_tok
                except (RateLimitError, APITimeoutError, APIConnectionError) as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                    print(f"草稿生成请求失败({type(e).__name__})，{delay:.0f}s 后重试 (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                    time.sleep(delay)

        elif self.provider == "anthropic":
            import anthropic
            from anthropic import RateLimitError as AnthropicRateLimitError
            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

            results, in_tok_total, out_tok_total = [], 0, 0
            max_retries = 8
            base_delay = 15
            for _ in range(n):
                for attempt in range(max_retries):
                    try:
                        msg = client.messages.create(
                            model=self.model_name,
                            max_tokens=256,
                            system="You are an expert programmer. Complete the code. Return ONLY the code continuation.",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=temperature,
                            top_p=top_p,
                        )
                        results.append(msg.content[0].text or "")
                        in_tok_total += msg.usage.input_tokens if msg.usage else 0
                        out_tok_total += msg.usage.output_tokens if msg.usage else 0
                        break
                    except AnthropicRateLimitError as e:
                        if attempt == max_retries - 1:
                            raise
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                        print(f"草稿生成 429 限流，{delay:.0f}s 后重试 (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                        time.sleep(delay)
            return results, in_tok_total, out_tok_total

        return [""] * n, 0, 0


# ---------------------------------------------------------------------------
# 模型参数构建
# ---------------------------------------------------------------------------

def _make_args(retriever_model: str, generator_model: str, language: str,
               add_api_blocks: bool, number_sample: int,
               temperature1: float, top_p1: float) -> argparse.Namespace:
    gpu_count = torch.cuda.device_count()
    batch_size = 1
    return argparse.Namespace(
        retriever_model_path=retriever_model,
        retriever_batch_size_per_gpu=batch_size,
        retriever_batch_size=max(1, batch_size * gpu_count),
        retriever_query_context_length=256,
        retriever_candidate_context_length=512,
        disable_retriever=False,
        generator_model_path=generator_model,
        generator_batch_size_per_gpu=batch_size,
        generator_batch_size=max(1, batch_size * gpu_count),
        generator_max_crossfile_length=8192,
        generator_max_context_length=16384,
        generator_max_generation_length=512,
        disable_generator=False,
        inference_type="unixcoder_with_rl",
        enable_tqdm=False,
        num_workers=0,
        weighted_keywords=True,
        enable_fixed_block=False,
        disable_stop_block=False,
        enable_repocoder=False,
        sample_number=5,          # AlignRetriever top-k
        # AlignCoder 新增参数
        enable_prediction=True,   # 开启 query enhancement
        enable_oracle=False,
        add_api_blocks=add_api_blocks,
        number_sample=number_sample,
        temperature1=temperature1,
        top_p1=top_p1,
        # 训练相关（推理不用）
        epoch=20, inner_epoch=1, batch_size=16,
        data_per_epoch=2000, lr=5e-5,
        enable_sft=False,
        feedback_signal="ppl",
        vllm_generator_batch_size_per_gpu=10000000,
    )


# ---------------------------------------------------------------------------
# Model path resolution
# ---------------------------------------------------------------------------

_retriever_cache: dict = {}
generator = None  # 由 main() 注入 APIGenerator 实例，retrieve_codeblocks 通过此全局变量调用
retriever_approx_tokens = 0  # AlignRetriever 输入序列长度近似 token 数（字符数 / 4）


def _resolve_to_snapshot(model_id: str) -> str:
    hub_cache = Path("/workspace/models")
    slug = model_id.replace("/", "--")
    candidates = [hub_cache / f"models--{slug}", hub_cache / slug]
    for base in candidates:
        snapshots_dir = base / "snapshots"
        if snapshots_dir.is_dir():
            snapshots = sorted([d for d in snapshots_dir.iterdir() if d.is_dir()])
            if snapshots:
                return str(snapshots[-1])
        if (base / "config.json").exists():
            return str(base)
    return model_id


def _get_retriever(args):
    key = args.retriever_model_path
    if key not in _retriever_cache:
        # Retriever.__init__ 里用 AutoTokenizer.from_pretrained 加载 fast tokenizer
        # AlignRetriever 的 tokenizer.json 是新格式，与 transformers 4.34 的 tokenizers<0.15 不兼容
        # monkey-patch：强制使用 slow tokenizer（不依赖 tokenizers 版本）
        from transformers import AutoTokenizer as _AutoTokenizer
        _orig_from_pretrained = _AutoTokenizer.from_pretrained.__func__ if hasattr(_AutoTokenizer.from_pretrained, '__func__') else None

        import transformers as _transformers
        _orig = _transformers.AutoTokenizer.from_pretrained

        def _patched_from_pretrained(name_or_path, *args_, **kwargs):
            kwargs.setdefault("use_fast", False)
            return _orig(name_or_path, *args_, **kwargs)

        _transformers.AutoTokenizer.from_pretrained = _patched_from_pretrained
        try:
            _retriever_cache[key] = Retriever(args)
        finally:
            _transformers.AutoTokenizer.from_pretrained = _orig

    return _retriever_cache[key]


# ---------------------------------------------------------------------------
# 主推理函数
# ---------------------------------------------------------------------------

def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"stdin JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    retriever_model_id = payload["retriever_model"]
    provider = payload["provider"]
    model_name = payload["model_name"]
    language = payload["language"]
    add_api_blocks = payload.get("add_api_blocks", language in ("python", "java"))
    number_sample = payload.get("number_sample", 4)
    temperature1 = payload.get("temperature1", 0.8)
    top_p1 = payload.get("top_p1", 0.95)

    # API 模式下 generator_model 只用来加载 tokenizer 构建 prompt
    generator_model_id = "deepseek-ai/deepseek-coder-1.3b-base"

    retriever_model = _resolve_to_snapshot(retriever_model_id)
    generator_model = _resolve_to_snapshot(generator_model_id)
    print(f"retriever_model resolved: {retriever_model}", file=sys.stderr)
    print(f"generator_model (tokenizer): {generator_model}", file=sys.stderr)

    # 重建 Example 对象
    related_files = [
        CodeBlock(
            file_path=f["file_path"],
            description=f.get("description", f["file_path"]),
            code_content=f["code_content"],
            language=f.get("language", language),
            _type=f.get("_type", ""),
            _api_block=f.get("_api_block", False),
        )
        for f in payload["related_files"]
    ]

    example = Example(
        task_id=payload["task_id"],
        file_path=payload["file_path"],
        left_context=payload["left_context"],
        right_context=payload["right_context"],
        related_files=related_files,
        target_code="",
        language=language,
    )

    args = _make_args(
        retriever_model, generator_model, language,
        add_api_blocks, number_sample, temperature1, top_p1,
    )

    # 加载检索器
    retriever = _get_retriever(args)

    # 加载 tokenizer（只用于 construct_prompts 的 token 截断计算）
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(generator_model)
    tokenizer.model_max_length = int(1e10)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # 创建 APIGenerator 用于 query enhancement 的草稿生成
    # retrieve_codeblocks（已内联）通过文件级全局变量 generator 调用草稿生成
    api_generator = APIGenerator(provider, model_name, tokenizer, args)

    global generator
    generator = api_generator

    examples = [example]
    bm25: dict = {}

    print("开始 AlignCoder 检索（含 query enhancement）...", file=sys.stderr)
    _, retrieved_codeblocks = retrieve_codeblocks(
        args, examples, bm25, retriever,
        dataset_name=example.task_id,
    )

    # 收集草稿生成的 token 统计和中间输出
    draft_input_tokens = api_generator.draft_input_tokens
    draft_output_tokens = api_generator.draft_output_tokens

    # 构建最终 prompt 并调用 API 生成
    dataset = CustomDataset(args, tokenizer, examples, retrieved_codeblocks, generation=True)
    prompt_text = dataset.construct_prompts(examples[0], retrieved_codeblocks[0])

    # 保存完整调试信息（包含 AlignCoder 独有的中间输出）
    debug_info = {
        "prompt_text": prompt_text,
        "retrieved_blocks": [
            {"file_path": b.file_path, "api_block": b._api_block}
            for b in retrieved_codeblocks[0] if b.file_path
        ],
        # AlignCoder 独有：草稿候选答案（query enhancement 的输出）
        "draft_candidates": getattr(api_generator, "all_draft_candidates", [[]])[0]
                            if getattr(api_generator, "all_draft_candidates", None) else [],
    }

    # 正式生成（temperature=0.2）
    import random
    import httpx

    def _make_http_client():
        proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        if proxy:
            return httpx.Client(proxy=proxy)
        return httpx.Client()

    input_tokens = 0
    output_tokens = 0

    if provider == "openai":
        from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError
        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
            http_client=_make_http_client(),
            timeout=120.0,
        )
        max_retries = 8
        base_delay = 15
        for attempt in range(max_retries):
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": (
                            "You are an expert programmer. Complete the body of the target function. "
                            "Return ONLY the function body code, no signature, no markdown."
                        )},
                        {"role": "user", "content": prompt_text},
                    ],
                    max_tokens=4096,
                    temperature=0.2,
                )
                break
            except (RateLimitError, APITimeoutError, APIConnectionError) as e:
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                print(f"正式生成请求失败({type(e).__name__})，{delay:.0f}s 后重试 (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                time.sleep(delay)
        completion = resp.choices[0].message.content or ""
        usage = resp.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else len(completion.split())

    elif provider == "anthropic":
        import anthropic
        from anthropic import RateLimitError as AnthropicRateLimitError
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        max_retries = 8
        base_delay = 15
        for attempt in range(max_retries):
            try:
                msg = client.messages.create(
                    model=model_name,
                    max_tokens=4096,
                    system=(
                        "You are an expert programmer. Complete the body of the target function. "
                        "Return ONLY the function body code, no signature, no markdown."
                    ),
                    messages=[{"role": "user", "content": prompt_text}],
                    temperature=0.2,
                )
                break
            except AnthropicRateLimitError as e:
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                print(f"正式生成 429 限流，{delay:.0f}s 后重试 (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                time.sleep(delay)
        completion = msg.content[0].text or ""
        input_tokens = msg.usage.input_tokens if msg.usage else 0
        output_tokens = msg.usage.output_tokens if msg.usage else len(completion.split())
    else:
        print(f"不支持的 provider: {provider}", file=sys.stderr)
        sys.exit(1)

    # 统计草稿生成的 token（从 APIGenerator 的最后一次调用中获取，通过重新估算）
    # draft token 已在 APIGenerator._sample_n 中消耗，这里通过 debug_info 记录
    print(json.dumps({
        "completion": completion,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "draft_input_tokens": draft_input_tokens,
        "draft_output_tokens": draft_output_tokens,
        "retriever_approx_tokens": retriever_approx_tokens,
        "debug": debug_info,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
