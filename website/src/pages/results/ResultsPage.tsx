import { ErrorState, Loading, PageHeader, Ratio, Segmented, Stat } from '../../shared/components'
import { useQueryFilters } from '../../shared/hooks/query'
import { ResultsCharts } from './ResultsCharts'
import { ResultsFilters } from './ResultsFilters'
import { ResultsTable } from './ResultsTable'
import { useResultsData } from './results.data'
import type { ResultsFilterState } from './results.types'
import './results.css'

const defaultFilters: ResultsFilterState = {
  level: 'L2',
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
}

export function ResultsPage() {
  const { filters, update, reset } = useQueryFilters(defaultFilters)
  const { source, rows, aggregates } = useResultsData(filters)
  const testedRows = rows.filter((row) => row.buildSuccess && row.testPassRatio !== null)
  const conditionalTestPass = testedRows.length
    ? testedRows.reduce((sum, row) => sum + (row.testPassRatio ?? 0), 0) / testedRows.length
    : null

  return (
    <>
      <PageHeader
        eyebrow="Execution outcomes"
        title="Results Explorer"
        description="Analyze build success, full-pass behavior, and conditional test performance across the benchmark."
        actions={
          <Segmented
            label="Evaluation level"
            value={filters.level}
            options={['L0', 'L1', 'L2', 'L3']}
            onChange={(value) => update('level', value)}
          />
        }
      />
      <ResultsFilters rows={source.data} filters={filters} update={update} reset={reset} />
      {source.loading ? (
        <Loading label={`Loading ${filters.level} results`} />
      ) : source.error ? (
        <ErrorState message={source.error} />
      ) : (
        <>
          <div className="stat-grid compact">
            <Stat label="Visible records" value={rows.length.toLocaleString()} />
            <Stat
              label="Build success"
              value={
                <Ratio
                  value={
                    rows.length ? rows.filter((row) => row.buildSuccess).length / rows.length : null
                  }
                />
              }
            />
            <Stat
              label="Full pass"
              value={
                <Ratio
                  value={
                    rows.length ? rows.filter((row) => row.fullPass).length / rows.length : null
                  }
                />
              }
            />
            <Stat label="Conditional test pass" value={<Ratio value={conditionalTestPass} />} />
          </div>
          <ResultsCharts rows={aggregates} level={filters.level} />
          <ResultsTable rows={rows} level={filters.level} />
        </>
      )}
    </>
  )
}
