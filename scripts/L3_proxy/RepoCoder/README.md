
只生成

cd /data/bowen/PolyCodeEval

OPENAI_API_KEY='<OPENAI_API_KEY>' OPENAI_BASE_URL='https://yunwu.ai/v1' \
python3 scripts/L3_proxy/RepoCoder/run_repocoder_batch.py \
  --all \
  --solver-prefix repocoder-openai \
  --model claude-sonnet-4-6 \
  --workers 4 \
  --output-dir /data/bowen/PolyCodeEval/output/repocoder_batch_all_claude \
  --resume


只评测
基于上面已经生成好的 generated_code

cd /data/bowen/PolyCodeEval

python3 scripts/run_l3_eval.py \
  --all \
  --solver precomputed:/data/bowen/PolyCodeEval/output/repocoder_batch_all_claude/generated_code \
  --workers 16 \
  --tests both \
  --output /data/bowen/PolyCodeEval/output/repocoder_eval_all_claude

python3 scripts/run_l3_eval.py \
  --language python \
  --solver precomputed:/data/bowen/PolyCodeEval/output/repocoder_e2e_all_gpt5.4_pypassfix \
  --workers 16 \
  --tests both \
  --output /data/bowen/PolyCodeEval/output/test

端到端：生成 + 评测

cd /data/bowen/PolyCodeEval

ANTHROPIC_API_KEY='你的key' \
python3 scripts/L3_proxy/RepoCoder/run_end_to_end.py \
  --all \
  --provider anthropic \
  --model claude-sonnet-4-6 \
  --workers 2 \
  --eval-workers 8 \
  --tests both \
  --output-dir /data/bowen/PolyCodeEval/output/repocoder_e2e_all_claude \
  --resume