import { normalizePrompts } from '../../shared/lib/benchmark'
import { useJson } from '../../shared/hooks/data'
import type { PromptEntry } from '../../shared/types/benchmark'
import type { PromptFilters } from './prompts.types'

export const reproductionCommands = `# Construct tasks
conda run -n polycodeeval python scripts/construction/build_tasks.py \\
  --level all --all

# Run representative generation methods
python scripts/L0_proxy/codex/run_codex_l0_batch.py --all --output-dir <RUN_DIR>
python scripts/L2_proxy/direct/run_l2_direct_batch.py \\
  --all --model openai/<MODEL_ID> --output-dir <RUN_DIR>
python scripts/L3_proxy/RepoCoder/run_end_to_end.py \\
  --all --provider openai --model <MODEL_ID> --output-dir <RUN_DIR> \\
  --workers 4 --eval-workers 16 --tests both

# Evaluate saved artifacts
python scripts/run_l2_eval.py --all --solver <RUN_DIR> --tests both
python scripts/run_l3_eval.py --all --solver <RUN_DIR> --tests both --workers 4

# Regenerate the website snapshot
python3 website/tools/export_data.py
python3 website/tools/validate_data.py`

export const reproductionSteps = [
  [
    'Prepare repositories',
    'Validate licenses, build entry points, tests, and production-code scope.',
  ],
  [
    'Construct tasks',
    'Build L3, L2, L1, and L0 artifacts with the formal construction entry point.',
  ],
  ['Validate Oracle', 'Execute build, test, reintegration, and coverage checks.'],
  ['Run generation', 'Select a level, method, model, language, project, or task.'],
  ['Evaluate and aggregate', 'Store task JSON, verify counts, and regenerate the public snapshot.'],
] as const

export function usePromptData() {
  return useJson('prompts/catalog.json', normalizePrompts, [])
}

export function filterPromptEntries(entries: PromptEntry[], filters: PromptFilters) {
  const search = filters.search.toLowerCase()
  return entries.filter(
    (entry) =>
      (!filters.category || entry.category === filters.category) &&
      (!filters.role || entry.role === filters.role) &&
      (!filters.search ||
        `${entry.title} ${entry.purpose} ${entry.template}`.toLowerCase().includes(search)),
  )
}
