import { useState } from 'react'
import { ErrorState, Loading, PageHeader, Segmented } from '../../shared/components'
import { useTaskResults } from '../../shared/hooks/data'
import { useFiltered, useQueryFilters } from '../../shared/hooks/query'
import { resultFields, ResultsFilters } from '../../shared/results/resultPresentation'
import type { ResultRow } from '../../shared/types/benchmark'
import { TaskDetails } from './TaskDetails'
import { TasksTable } from './TasksTable'

export function TasksPage() {
  const { filters, update, reset } = useQueryFilters({
    level: 'L3',
    search: '',
    language: '',
    project: '',
    method: '',
    model: '',
    source: '',
    submitter: '',
    build: '',
    full: '',
    testPass: '',
  })
  const source = useTaskResults(filters.level, filters.language)
  const rows = useFiltered(source.data, filters, resultFields)
  const [selected, setSelected] = useState<ResultRow | null>(null)
  return (
    <>
      <PageHeader
        eyebrow="Auditable records"
        title="Task Explorer"
        description="Search and inspect normalized task-level results while preserving links to their source records."
        actions={
          <Segmented
            label="Evaluation level"
            value={filters.level}
            options={['L0', 'L1', 'L2', 'L3']}
            onChange={(v) => update('level', v)}
          />
        }
      />
      <ResultsFilters rows={source.data} filters={filters} update={update} reset={reset} />
      {source.loading ? (
        <Loading label={`Loading ${filters.level} task records`} />
      ) : source.error ? (
        <ErrorState message={source.error} />
      ) : (
        <TasksTable rows={rows} level={filters.level} onSelect={setSelected} />
      )}
      <TaskDetails task={selected} onClose={() => setSelected(null)} />
    </>
  )
}
