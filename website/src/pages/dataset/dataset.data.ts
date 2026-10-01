import { useMemo } from 'react'
import { normalizeDataset } from '../../shared/lib/benchmark'
import { useJson } from '../../shared/hooks/data'
import { useFiltered } from '../../shared/hooks/query'
import type { DatasetFiltersState, DatasetRecord, LanguageSummary } from './dataset.types'

export function useDatasetData(filters: DatasetFiltersState) {
  const source = useJson('dataset/projects.json', normalizeDataset, [])
  const fields = useMemo(
    () => ({
      search: (row: DatasetRecord) => `${row.project} ${row.source}`,
      language: (row: DatasetRecord) => row.language,
      difficulty: (row: DatasetRecord) => row.difficulty,
      framework: (row: DatasetRecord) => row.testFramework,
      source: (row: DatasetRecord) => row.source,
      level: (row: DatasetRecord) =>
        filters.level && row.levels[filters.level] > 0 ? filters.level : '',
    }),
    [filters.level],
  )
  const rows = useFiltered(source.data, filters, fields)
  const languageSummary = useMemo<LanguageSummary[]>(() => {
    const grouped = new Map<string, LanguageSummary>()
    rows.forEach((row) => {
      const current = grouped.get(row.language) ?? {
        language: row.language,
        repositories: 0,
        loc: 0,
      }
      current.repositories += 1
      current.loc += row.loc ?? 0
      grouped.set(row.language, current)
    })
    return [...grouped.values()].sort((a, b) => a.language.localeCompare(b.language))
  }, [rows])

  return { source, rows, languageSummary }
}
