#!/usr/bin/env python3
"""HCP-Coder 推理入口（在 Docker 容器内运行）。

stdin:  JSON payload
stdout: JSON {"completion", "input_tokens", "output_tokens"}
"""

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

sys.path.insert(0, '/workspace/L3works/HCP-Coder')

from src.topo.modeling_topo import RepoTopo
from src.retriever.auto import AutoRetriever


def _make_http_client():
    import httpx
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    return httpx.Client(proxy=proxy) if proxy else httpx.Client()


def _api_call(provider, model_name, system_msg, user_msg):
    import random
    max_retries, base_delay = 8, 15

    if provider == "openai":
        from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError
        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
            http_client=_make_http_client(),
            timeout=120.0,
        )
        for attempt in range(max_retries):
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "system", "content": system_msg},
                              {"role": "user", "content": user_msg}],
                    max_tokens=4096, temperature=0.2,
                )
                text = resp.choices[0].message.content or ""
                usage = resp.usage
                return text, (usage.prompt_tokens if usage else 0), (usage.completion_tokens if usage else 0)
            except (RateLimitError, APITimeoutError, APIConnectionError) as e:
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                print(f"API error ({type(e).__name__}), retry in {delay:.0f}s", file=sys.stderr)
                time.sleep(delay)

    elif provider == "anthropic":
        import anthropic
        from anthropic import RateLimitError as ARL
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        for attempt in range(max_retries):
            try:
                msg = client.messages.create(
                    model=model_name, max_tokens=4096,
                    system=system_msg,
                    messages=[{"role": "user", "content": user_msg}],
                    temperature=0.2,
                )
                text = msg.content[0].text or ""
                return text, (msg.usage.input_tokens if msg.usage else 0), (msg.usage.output_tokens if msg.usage else 0)
            except ARL as e:
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                print(f"Anthropic rate limit, retry in {delay:.0f}s", file=sys.stderr)
                time.sleep(delay)

    raise ValueError(f"unsupported provider: {provider}")


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"stdin JSON error: {e}", file=sys.stderr)
        sys.exit(1)

    workspace_src_path = payload["workspace_src_path"]
    file_path = payload["file_path"]
    row = payload["row"]
    language = payload["language"]
    provider = payload["provider"]
    model_name = payload["model_name"]

    print(f"RepoTopo({workspace_src_path}, language={language})...", file=sys.stderr)
    repo_topo = RepoTopo(workspace_src_path, language=language)
    print(f"  files={repo_topo.num_files}", file=sys.stderr)

    cross_file_ctx = {}
    infile = {}
    retriever = AutoRetriever(engine="openai")

    try:
        context = repo_topo.get_completion_context(
            strategy="hcp", d_level=1, p_level=1,
            file_path=file_path, row=row, col=0,
            top_k=[5], top_p=[0.1],
            retriever=retriever,
        )
        key = "topp_0.1_topk_5"
        cross_file_ctx = (context.get("cross_file_context") or {}).get(key, {})
        infile = context.get("infile_context", {})
        print(f"  cross_file entries={len(cross_file_ctx)}", file=sys.stderr)
    except (AssertionError, KeyError, Exception) as e:
        print(f"  HCP context error ({type(e).__name__}: {e}), fallback to infile-only", file=sys.stderr)
        abs_key = str(Path(workspace_src_path) / file_path)
        file_node = repo_topo.file_nodes.get(abs_key)
        if file_node:
            infile = repo_topo.get_infile_context(file_node, row, 0)

    embedding_tokens = retriever.embedding_tokens

    # build chat prompt
    cross_block = "\n\n".join(f"# {fp}\n{c}" for fp, c in cross_file_ctx.items() if c)
    user_msg = (
        (cross_block + "\n\n" if cross_block else "")
        + f"# {file_path}\n"
        + infile.get("prefix", "")
    )
    if infile.get("suffix"):
        user_msg += f"\n[SUFFIX]\n{infile['suffix']}\n[/SUFFIX]\nComplete only the code between PREFIX and SUFFIX."

    system_msg = (
        "You are an expert programmer. Complete the body of the target function. "
        "Return ONLY the function body code, no signature, no markdown."
    )

    print("Calling API...", file=sys.stderr)
    completion, input_tokens, output_tokens = _api_call(provider, model_name, system_msg, user_msg)

    print(json.dumps({
        "completion": completion,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "embedding_tokens": embedding_tokens,
        "debug": {
            "prompt_text": user_msg,
            "cross_file_files": list(cross_file_ctx.keys()),
        },
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
