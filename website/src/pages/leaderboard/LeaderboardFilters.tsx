import { Field, FilterBar, Segmented } from '../../shared/components'
import { unique } from '../../shared/hooks/query'
import type { LeaderboardEntry } from './leaderboard.types'

export interface LeaderboardFilterState {
  level: string
  language: string
  method: string
  model: string
  source: string
  submitter: string
  board: string
  search: string
}

interface Props {
  rows: LeaderboardEntry[]
  filters: LeaderboardFilterState
  update: (key: keyof LeaderboardFilterState, value: string) => void
  reset: () => void
}

export function LeaderboardFilters({ rows, filters, update, reset }: Props) {
  return (
    <>
      <div className="leaderboard-levels">
        <Segmented
          label="Evaluation level"
          value={filters.level}
          options={['L0', 'L1', 'L2', 'L3']}
          onChange={(value) => update('level', value)}
        />
        {(filters.level === 'L0' || filters.level === 'L1') && (
          <Segmented
            label="Ranking view"
            value={filters.board}
            options={['Execution', 'Full Quality']}
            onChange={(value) => update('board', value)}
          />
        )}
      </div>
      <FilterBar onReset={reset}>
        <Field
          label="Search"
          value={filters.search}
          onChange={(value) => update('search', value)}
          placeholder="Method or model"
        />
        <Field
          label="Language"
          value={filters.language}
          onChange={(value) => update('language', value)}
          options={unique(rows.map((row) => row.language))}
          placeholder="Overall"
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
      </FilterBar>
    </>
  )
}
