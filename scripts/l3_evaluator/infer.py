#!/usr/bin/env python3
"""
Infer LLM API and generate precomputed outputs for PolyCodeEval L3 Tasks.
This script uses the OpenAI-compatible client, which works perfectly with platforms like 云雾(Yunwu).
"""

import argparse
import os
import sys
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from openai import OpenAI
except ImportError:
    print("需要安装 openai 包：pip install openai")
    sys.exit(1)

def clean_code(content: str) -> str:
    """清理 Markdown 代码块，提取纯代码，并尝试去除函数签名"""
    # 去除首尾的 markdown 代码块标记
    pattern = re.compile(r"^```[\w]*\n(.*)```", re.DOTALL | re.MULTILINE)
    match = pattern.search(content.strip())
    if match:
        content = match.group(1)
    
    # 简单过滤可能残留的 ```
    content = content.replace("```", "").strip()
    return content

def should_retry(exc: Exception) -> bool:
    """识别适合自动重试的临时性错误。"""
    status_code = getattr(exc, "status_code", None)
    if status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True

    text = str(exc).lower()
    retry_markers = (
        "timeout",
        "timed out",
        "connection",
        "temporarily unavailable",
        "bad gateway",
        "rate limit",
        "server error",
    )
    return any(marker in text for marker in retry_markers)


def process_file(
    client,
    prompt_file: Path,
    output_file: Path,
    model: str,
    max_retries: int,
    retry_base_delay: float,
) -> bool:
    if output_file.exists():
        # 如果文件已生成，直接跳过（支持断点续跑）
        return True
    
    prompt = prompt_file.read_text(encoding="utf-8")
    
    system_prompt = (
        "You are an expert programmer. Complete the body of the function described in the prompt. "
        "Return ONLY the function body code. "
        "Do NOT include the function signature (e.g., no 'func', 'def', or return types). "
        "Do NOT wrap the code in markdown formatting like ```."
    )
    
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2048,
            )
            result = response.choices[0].message.content
            cleaned_result = clean_code(result)

            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(cleaned_result, encoding="utf-8")
            return True
        except Exception as e:
            if attempt < max_retries and should_retry(e):
                delay = retry_base_delay * (2 ** attempt)
                print(
                    f"Retrying {prompt_file.name} after attempt {attempt + 1}/{max_retries + 1}: {e} "
                    f"(sleep {delay:.1f}s)"
                )
                time.sleep(delay)
                continue

            print(f"Error processing {prompt_file.name} after {attempt + 1} attempts: {e}")
            return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", type=Path, default="prompts", help="Directory containing generated prompts")
    parser.add_argument("--output", type=Path, default="results/yunwu_outputs", help="Output directory for precomputed results")
    parser.add_argument("--model", type=str, default="gpt-3.5-turbo", help="Model name to use in the API")
    parser.add_argument("--base-url", type=str, default=os.environ.get("OPENAI_BASE_URL"), help="API Base URL (e.g. 云雾 API)")
    parser.add_argument("--api-key", type=str, default=os.environ.get("OPENAI_API_KEY"), help="API Key")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent requests")
    parser.add_argument("--max-retries", type=int, default=4, help="Maximum retries for transient API failures")
    parser.add_argument("--retry-base-delay", type=float, default=2.0, help="Base delay in seconds for exponential backoff")
    parser.add_argument("--timeout", type=float, default=120.0, help="Request timeout in seconds")
    
    args = parser.parse_args()

    if not args.api_key:
        print("错误：请提供 --api-key 或设置 OPENAI_API_KEY 环境变量")
        sys.exit(1)
        
    if not args.base_url:
        print("错误：请提供 --base-url 或设置 OPENAI_BASE_URL 环境变量。例如: https://api.yunwu.com/v1")
        sys.exit(1)

    client = OpenAI(
        api_key=args.api_key,
        base_url=args.base_url,
        timeout=args.timeout,
    )
    
    prompts_dir = args.prompts
    if not prompts_dir.exists():
        print(f"找不到 prompts 目录：{prompts_dir}。请先运行 gen_l3_prompts.py。")
        sys.exit(1)
        
    tasks = list(prompts_dir.rglob("*.md"))
    total = len(tasks)
    print(f"找到 {total} 个 prompt。准备调用 {args.model} 进行推理...")

    success = 0
    failed = 0
    done = 0
    start_time = time.time()
    lock = __import__("threading").Lock()

    def _progress_bar():
        elapsed = time.time() - start_time
        pct = done / total * 100 if total else 0
        bar_len = 30
        filled = int(bar_len * done / total) if total else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        eta_str = f"{int(eta // 60)}m{int(eta % 60):02d}s" if eta < 3600 else f"{eta / 3600:.1f}h"
        return (
            f"\r  [{bar}] {done}/{total} ({pct:.0f}%) "
            f"| ok:{success} err:{failed} "
            f"| {elapsed:.0f}s elapsed, ETA {eta_str}  "
        )

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for prompt_file in tasks:
            relative_path = prompt_file.relative_to(prompts_dir)
            output_file = args.output / relative_path.with_suffix(".txt")

            futures[pool.submit(
                process_file,
                client,
                prompt_file,
                output_file,
                args.model,
                args.max_retries,
                args.retry_base_delay,
            )] = prompt_file

        for future in as_completed(futures):
            with lock:
                done += 1
                if future.result():
                    success += 1
                else:
                    failed += 1
                sys.stderr.write(_progress_bar())
                sys.stderr.flush()

    sys.stderr.write("\n")
                
    print(f"成功处理 {success}/{total} 个任务。")
    print(f"结果已保存在 {args.output} 目录。")
    print(f"接下来您可以运行：")
    print(f"python scripts/run_l3_eval.py --language go --solver precomputed:{args.output} --workers 4")

if __name__ == "__main__":
    main()
