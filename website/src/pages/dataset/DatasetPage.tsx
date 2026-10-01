import { useState } from 'react'
import {
  Badge,
  DetailList,
  Drawer,
  ErrorState,
  Loading,
  NumberValue,
  PageHeader,
  Ratio,
  RawJson,
} from '../../shared/components'
import { useQueryFilters } from '../../shared/hooks/query'
import { DatasetCharts } from './DatasetCharts'
import { DatasetFilters } from './DatasetFilters'
import { DatasetTable } from './DatasetTable'
import { useDatasetData } from './dataset.data'
import type { DatasetFiltersState, DatasetRecord } from './dataset.types'
import './dataset.css'

const defaultFilters: DatasetFiltersState = {
  search: '',
  language: '',
  difficulty: '',
  framework: '',
  source: '',
  level: '',
}

export function DatasetPage() {
  const [selected, setSelected] = useState<DatasetRecord | null>(null)
  const { filters, update, reset } = useQueryFilters(defaultFilters)
  const { source, rows, languageSummary } = useDatasetData(filters)

  return (
    <>
      <PageHeader
        eyebrow="Data composition"
        title="Dataset Explorer"
        description="Inspect the executable repository pool and the tasks derived at each evaluation level."
      />
      <DatasetFilters rows={source.data} filters={filters} update={update} reset={reset} />
      {source.loading ? (
        <Loading />
      ) : source.error ? (
        <ErrorState message={source.error} />
      ) : (
        <>
          <DatasetCharts summary={languageSummary} />
          <DatasetTable rows={rows} onSelect={setSelected} />
        </>
      )}
      <Drawer
        title={selected?.project || 'Repository details'}
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
      >
        {selected && (
          <>
            <div className="drawer-badges">
              <Badge value={selected.language} />
              <Badge tone="accent" value={selected.difficulty} />
              {selected.oracleValidated !== null && (
                <Badge
                  tone={selected.oracleValidated ? 'success' : 'danger'}
                  value={selected.oracleValidated ? 'Oracle validated' : 'Oracle failed'}
                />
              )}
            </div>
            <DetailList
              entries={[
                ['Source', selected.source],
                ['Test framework', selected.testFramework],
                ['Oracle LOC', <NumberValue value={selected.loc} digits={0} />],
                ['Project coverage', <Ratio value={selected.coverage} />],
                ['L0 tasks', selected.levels.L0],
                ['L1 tasks', selected.levels.L1],
                ['L2 tasks', selected.levels.L2],
                ['L3 tasks', selected.levels.L3],
              ]}
            />
            <RawJson value={selected.raw} />
          </>
        )}
      </Drawer>
    </>
  )
}
