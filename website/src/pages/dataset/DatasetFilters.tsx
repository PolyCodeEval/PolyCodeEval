import { Field, FilterBar } from '../../shared/components'
import { unique } from '../../shared/hooks/query'
import type { DatasetFiltersState, DatasetRecord } from './dataset.types'

export function DatasetFilters({
  rows,
  filters,
  update,
  reset,
}: {
  rows: DatasetRecord[]
  filters: DatasetFiltersState
  update: (key: keyof DatasetFiltersState, value: string) => void
  reset: () => void
}) {
  return (
    <FilterBar onReset={reset}>
      <Field
        label="Search"
        value={filters.search}
        onChange={(value) => update('search', value)}
        placeholder="Repository or source"
      />
      <Field
        label="Language"
        value={filters.language}
        onChange={(value) => update('language', value)}
        options={unique(rows.map((row) => row.language))}
      />
      <Field
        label="Difficulty"
        value={filters.difficulty}
        onChange={(value) => update('difficulty', value)}
        options={unique(rows.map((row) => row.difficulty))}
      />
      <Field
        label="Test framework"
        value={filters.framework}
        onChange={(value) => update('framework', value)}
        options={unique(rows.map((row) => row.testFramework))}
      />
      <Field
        label="Source"
        value={filters.source}
        onChange={(value) => update('source', value)}
        options={unique(rows.map((row) => row.source))}
      />
      <Field
        label="Level"
        value={filters.level}
        onChange={(value) => update('level', value)}
        options={['L0', 'L1', 'L2', 'L3']}
      />
    </FilterBar>
  )
}
