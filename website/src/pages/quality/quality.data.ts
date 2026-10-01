import { normalizeCoverage, normalizePromptQuality } from '../../shared/lib/benchmark'
import { useJson } from '../../shared/hooks/data'
import { unique } from '../../shared/hooks/query'
import type { CoverageRow, PromptQualityRow } from '../../shared/types/benchmark'
import type {
  CoverageDistribution,
  CommunityQualityRow,
  PromptQualitySummary,
  QualityFilters,
  QualityPageData,
} from './quality.types'

const normalizeCommunityQuality = (raw: unknown): CommunityQualityRow[] => {
  const value = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const records = Array.isArray(value.records) ? value.records : []
  return records.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const row = item as Record<string, unknown>
    if (row.language || !row.qualityEligible) return []
    const optional = (field: string) => (row[field] == null ? null : Number(row[field]))
    return [
      {
        submissionId: String(row.submissionId ?? ''),
        submitter: String(row.submitter ?? ''),
        level: String(row.level ?? ''),
        method: String(row.method ?? ''),
        model: String(row.model ?? ''),
        coverageRate: Number(row.coverageRate ?? 0),
        correctness: optional('correctness'),
        faithfulness: optional('faithfulness'),
        architecture: optional('architecture'),
        health: optional('health'),
        overall: optional('overall'),
      },
    ]
  })
}

export function useQualityData() {
  const coverage = useJson('quality/coverage.json', normalizeCoverage, [])
  const qualityL0 = useJson('quality/prompt-quality/l0.json', normalizePromptQuality, [])
  const qualityL2 = useJson('quality/prompt-quality/l2.json', normalizePromptQuality, [])
  const qualityL3 = useJson('quality/prompt-quality/l3.json', normalizePromptQuality, [])
  const communityQuality = useJson('community/leaderboard.json', normalizeCommunityQuality, [])

  return {
    coverage,
    quality: {
      data: [...qualityL0.data, ...qualityL2.data, ...qualityL3.data],
      loading: qualityL0.loading || qualityL2.loading || qualityL3.loading,
      error: qualityL0.error || qualityL2.error || qualityL3.error,
    },
    communityQuality,
  }
}

export function deriveQualityPageData(
  coverage: CoverageRow[],
  quality: PromptQualityRow[],
  filters: QualityFilters,
): QualityPageData {
  const coverageRows = coverage.filter(
    (row) =>
      (!filters.level || row.level === filters.level) &&
      (!filters.language || row.language === filters.language) &&
      (!filters.project || row.project === filters.project),
  )
  const qualityRows = quality.filter(
    (row) =>
      (!filters.level || row.level === filters.level) &&
      (!filters.language || row.language === filters.language) &&
      (!filters.project || row.project === filters.project) &&
      (!filters.judge || row.judge === filters.judge),
  )

  return {
    coverageRows,
    qualityRows,
    coverageDistribution: buildCoverageDistribution(coverageRows),
    promptQualitySummary: buildPromptQualitySummary(qualityRows),
  }
}

function buildCoverageDistribution(rows: CoverageRow[]): CoverageDistribution {
  const groups = unique(rows.map((row) => `${row.level} · ${row.language}`))
  const values = groups.map((group) => {
    const sorted = rows
      .filter((row) => `${row.level} · ${row.language}` === group)
      .map((row) => row.value)
      .filter((value): value is number => value !== null)
      .sort((a, b) => a - b)

    if (!sorted.length) return [0, 0, 0, 0, 0]
    const quantile = (position: number) =>
      sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * position))] * 100
    return [quantile(0), quantile(0.25), quantile(0.5), quantile(0.75), quantile(1)]
  })

  return { groups, values }
}

function buildPromptQualitySummary(rows: PromptQualityRow[]): PromptQualitySummary {
  const groups = unique(rows.map((row) => `${row.level} · ${row.judge || 'Judge'}`))
  const averages = groups.map((group) => {
    const matching = rows.filter(
      (row) => `${row.level} · ${row.judge || 'Judge'}` === group && row.score !== null,
    )
    return matching.length
      ? matching.reduce((sum, row) => sum + (row.score ?? 0), 0) / matching.length
      : 0
  })

  return { groups, averages }
}
