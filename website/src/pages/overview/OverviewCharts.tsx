import { Chart, Empty, ErrorState, Loading, Panel } from '../../shared/components'
import { axis, chartGrid, chartText, colors } from '../../shared/styles/charts'
import type { OutcomeAggregate } from './overview.types'

const levels = ['L0', 'L1', 'L2', 'L3']

function meanRate(
  rows: OutcomeAggregate[],
  level: string,
  key: 'buildRate' | 'fullRate' | 'testRate',
) {
  const subset = rows.filter((row) => row.level === level)
  return subset.length ? (subset.reduce((sum, row) => sum + row[key], 0) / subset.length) * 100 : 0
}

export function OverviewCharts({
  rows,
  loading,
  error,
}: {
  rows: OutcomeAggregate[]
  loading: boolean
  error: string | null
}) {
  const series = [
    {
      name: 'Build success',
      type: 'bar' as const,
      color: colors.orange,
      data: levels.map((level) => +meanRate(rows, level, 'buildRate').toFixed(2)),
    },
    {
      name: 'Full pass',
      type: 'bar' as const,
      color: colors.blue,
      data: levels.map((level) => +meanRate(rows, level, 'fullRate').toFixed(2)),
    },
    {
      name: 'Conditional test pass',
      type: 'bar' as const,
      color: colors.green,
      data: levels.map((level) => +meanRate(rows, level, 'testRate').toFixed(2)),
    },
  ]

  return (
    <Panel
      title="Evaluation outcomes by level"
      subtitle="Mean rates across the canonical configurations evaluated at each level."
      className="span-2"
    >
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorState message={error} />
      ) : rows.length ? (
        <Chart
          name="aggregate-outcomes"
          option={{
            tooltip: { trigger: 'axis' },
            legend: { top: 0, textStyle: chartText },
            grid: chartGrid,
            xAxis: { type: 'category', data: levels, ...axis },
            yAxis: { type: 'value', max: 100, name: 'Rate (%)', ...axis },
            series,
          }}
        />
      ) : (
        <Empty />
      )}
    </Panel>
  )
}
