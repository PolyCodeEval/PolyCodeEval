import { ErrorState, Field, FilterBar, Loading, PageHeader, Stat } from '../../shared/components'
import { unique, useQueryFilters } from '../../shared/hooks/query'
import { TokenCharts } from './TokenCharts'
import { filterTokenRows, sumTokenField, useTokenData } from './tokens.data'
import type { TokenFilters } from './tokens.types'
import { TokensTable } from './TokensTable'

const initialFilters: TokenFilters = { level: '', method: '', model: '', language: '' }

export function TokensPage() {
  const source = useTokenData()
  const { filters, update, reset } = useQueryFilters(initialFilters)
  const rows = filterTokenRows(source.data, filters)

  return (
    <>
      <PageHeader
        eyebrow="Resource accounting"
        title="Token & Cost"
        description="Inspect input, output, draft, and embedding usage for the recorded generation configurations."
      />
      <FilterBar onReset={reset}>
        <Field
          label="Level"
          value={filters.level}
          onChange={(value) => update('level', value)}
          options={unique(source.data.map((row) => row.level))}
        />
        <Field
          label="Method"
          value={filters.method}
          onChange={(value) => update('method', value)}
          options={unique(source.data.map((row) => row.method))}
        />
        <Field
          label="Model"
          value={filters.model}
          onChange={(value) => update('model', value)}
          options={unique(source.data.map((row) => row.model))}
        />
        <Field
          label="Language"
          value={filters.language}
          onChange={(value) => update('language', value)}
          options={unique(source.data.map((row) => row.language))}
        />
      </FilterBar>
      {source.loading ? (
        <Loading />
      ) : source.error ? (
        <ErrorState message={source.error} />
      ) : (
        <>
          <div className="stat-grid compact">
            <Stat label="Recorded tokens" value={sumTokenField(rows, 'total').toLocaleString()} />
            <Stat label="Input tokens" value={sumTokenField(rows, 'input').toLocaleString()} />
            <Stat label="Output tokens" value={sumTokenField(rows, 'output').toLocaleString()} />
            <Stat
              label="Recorded cost"
              value={`$${sumTokenField(rows, 'cost').toLocaleString(undefined, { maximumFractionDigits: 2 })}`}
            />
          </div>
          <TokenCharts rows={rows} />
          <TokensTable rows={rows} />
        </>
      )}
    </>
  )
}
