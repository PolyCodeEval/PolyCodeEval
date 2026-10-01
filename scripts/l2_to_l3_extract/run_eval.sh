#!/bin/bash
# Run L3 evaluation on L2-extracted function bodies (extracted subset only).
# Usage: bash scripts/l2_to_l3_extract/run_eval.sh [sonnet|gpt54|all]

set -e
cd "$(dirname "$0")/../.."

MODEL="${1:-all}"

run_eval() {
    local model_name="$1"
    local output_name="$2"
    local output_dir="finalresults/L2toL3/${output_name}"

    if [ ! -d "All_answers/L2toL3/${model_name}/generated_code" ]; then
        echo "ERROR: Extracted output not found: All_answers/L2toL3/${model_name}/generated_code"
        return 1
    fi

    echo "=========================================="
    echo "Evaluating: $model_name"
    echo "  Output: $output_dir"
    echo "=========================================="

    python3 scripts/l2_to_l3_extract/run_eval_extracted.py \
        --model "${model_name}" \
        --workers 16 --tests both \
        --output "$output_dir"
}

case "$MODEL" in
    sonnet)
        run_eval "l2_direct_full_sonnet" "l2toL3_eval_sonnet"
        ;;
    gpt54)
        run_eval "l2_direct_full_gpt54" "l2toL3_eval_gpt54"
        ;;
    all)
        run_eval "l2_direct_full_sonnet" "l2toL3_eval_sonnet"
        run_eval "l2_direct_full_gpt54" "l2toL3_eval_gpt54"
        ;;
    *)
        echo "Usage: $0 [sonnet|gpt54|all]"
        exit 1
        ;;
esac

echo ""
echo "Done. Results in finalresults/L2toL3/"
