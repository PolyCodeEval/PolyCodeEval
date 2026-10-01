import { normalizeManifest, rowsOf } from '../../shared/lib/benchmark'
import { useJson } from '../../shared/hooks/data'
import type { CommunitySummary, OutcomeAggregate } from './overview.types'

export function useOverviewData() {
  const manifest = useJson('overview/summary.json', normalizeManifest, normalizeManifest({}))
  const aggregates = useJson(
    'results/aggregates.json',
    (raw): OutcomeAggregate[] =>
      rowsOf(raw)
        .map((record) => ({
          level: String(record.level ?? ''),
          label: [String(record.method ?? ''), String(record.model ?? '')]
            .filter(Boolean)
            .join(' + '),
          buildRate: Number(record.buildSuccessRate ?? 0),
          fullRate: Number(record.fullPassRate ?? 0),
          testRate: Number(record.conditionalTestPassRatio ?? 0),
          scope: String(record.scopeType ?? ''),
        }))
        .filter((record) => record.scope === 'all'),
    [],
  )
  const community = useJson(
    'community/manifest.json',
    (raw): CommunitySummary => {
      const value = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
      return {
        submissionCount: Number(value.submissionCount ?? 0),
        generatedAt: String(value.generatedAt ?? ''),
      }
    },
    { submissionCount: 0, generatedAt: '' },
  )

  return { manifest, aggregates, community }
}
