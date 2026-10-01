import { Field, FilterBar } from '../../shared/components'
import { unique } from '../../shared/hooks/query'
import type { ResultsFilterState, ResultsRecord } from './results.types'

export function ResultsFilters({
  rows,
  filters,
  update,
  reset,
}: {
  rows: ResultsRecord[]
  filters: ResultsFilterState
  update: (key: keyof ResultsFilterState, value: string) => void
  reset: () => void
}) {
  return (
    <FilterBar onReset={reset}>
      <Field
        label="Search"
        value={filters.search}
        onChange={(value) => update('search', value)}
        placeholder="Task or project"
      />
      <Field
        label="Language"
        value={filters.language}
        onChange={(value) => update('language', value)}
        options={unique(rows.map((row) => row.language))}
      />
      <Field
        label="Project"
        value={filters.project}
        onChange={(value) => update('project', value)}
        options={unique(rows.map((row) => row.project))}
      />
      <Field
        label="Method"
        value={filters.method}
        onChange={(value) => update('method', value)}
        options={unique(rows.map((row) => row.method))}
      />
      <Field
        label="Model"
        value={filters.model}
        onChange={(value) => update('model', value)}
        options={unique(rows.map((row) => row.model))}
      />
      <Field
        label="Source"
        value={filters.source}
        onChange={(value) => update('source', value)}
        options={unique(rows.map((row) => row.sourceType))}
      />
      <Field
        label="Submitter"
        value={filters.submitter}
        onChange={(value) => update('submitter', value)}
        options={unique(rows.map((row) => row.submitter))}
      />
      <Field
        label="Build"
        value={filters.build}
        onChange={(value) => update('build', value)}
        options={['Success', 'Failed', 'Unknown']}
      />
      <Field
        label="Full pass"
        value={filters.full}
        onChange={(value) => update('full', value)}
        options={['Passed', 'Not passed', 'Unknown']}
      />
      <Field
        label="Test pass"
        value={filters.testPass}
        onChange={(value) => update('testPass', value)}
        options={['0%', '0.1–49.9%', '50.0–99.9%', '100%', 'Unavailable']}
      />
    </FilterBar>
  )
}
