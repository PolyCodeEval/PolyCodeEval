import { useMemo } from 'react'
import { normalizeResults, normalizeSignificance } from '../../shared/lib/benchmark'
import { useJson } from '../../shared/hooks/data'
import type { ResultRow, SignificanceRow } from '../../shared/types/benchmark'
import type { StateTransition, StatisticsFilters } from './statistics.types'

export function useStatisticsData() {
  const significance = useJson('statistics/significance.json', normalizeSignificance, [])
  const paired = useJson('statistics/l2-to-l3.json', normalizeResults, [])
  const transitions = useMemo(() => buildStateTransitions(paired.data), [paired.data])
  return { significance, paired, transitions }
}

export function filterSignificanceRows(rows: SignificanceRow[], filters: StatisticsFilters) {
  return rows.filter(
    (row) =>
      (!filters.level || row.level === filters.level) &&
      (!filters.search || row.comparison.toLowerCase().includes(filters.search.toLowerCase())),
  )
}

function buildStateTransitions(rows: ResultRow[]): StateTransition[] {
  const counts = new Map<string, number>()
  rows.forEach((row) => {
    const withImplementations = row.raw.withRelatedImplementations as
      Record<string, unknown> | undefined
    const signatureOnly = row.raw.signatureContextOnly as Record<string, unknown> | undefined
    const state = (value: Record<string, unknown> | undefined) =>
      value?.fullPass ? 'Full pass' : value?.buildSuccess ? 'Build only' : 'Failed'
    const label = `${state(signatureOnly)} → ${state(withImplementations)}`
    counts.set(label, (counts.get(label) ?? 0) + 1)
  })
  return [...counts].map(([label, count]) => ({ label, count }))
}
