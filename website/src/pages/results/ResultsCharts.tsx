import { Chart, Empty, Panel } from '../../shared/components'
import { unique } from '../../shared/hooks/query'
import { axis, chartGrid, chartText, colors } from '../../shared/styles/charts'
import type { AggregatedResult } from './results.types'

export function ResultsCharts({ rows, level }: { rows: AggregatedResult[]; level: string }) {
  const labels = unique(rows.map((row) => row.label))
  const languages = unique(rows.map((row) => row.language))
  const heat = rows.map((row) => [
    labels.indexOf(row.label),
    languages.indexOf(row.language),
    +(row.fullRate * 100).toFixed(1),
  ])
  const mean = (label: string, key: 'buildRate' | 'fullRate' | 'testRate') => {
    const matches = rows.filter((row) => row.label === label)
    return matches.length
      ? (matches.reduce((sum, row) => sum + row[key], 0) / matches.length) * 100
      : 0
  }

  return (
    <div className="two-grid results-charts">
      <Panel
        title="Full-pass matrix"
        subtitle="Percentage of tasks passing all tests for each method and language."
      >
        {heat.length ? (
          languages.length === 1 ? (
            <Chart
              name={`${level.toLowerCase()}-full-pass-bars`}
              height={Math.max(330, labels.length * 27)}
              option={{
                tooltip: { trigger: 'axis' },
                grid: { left: 145, right: 42, top: 12, bottom: 35 },
                xAxis: { type: 'value', max: 100, name: 'Full pass (%)', ...axis },
                yAxis: {
                  type: 'category',
                  data: labels,
                  axisLabel: { ...chartText, width: 135, overflow: 'truncate' },
                },
                series: [
                  {
                    type: 'bar',
                    data: rows.map((row) => +(row.fullRate * 100).toFixed(1)),
                    color: colors.blue,
                    label: { show: true, position: 'right', formatter: '{c}%' },
                  },
                ],
              }}
            />
          ) : (
            <Chart
              name={`${level.toLowerCase()}-full-pass-heatmap`}
              height={Math.max(310, labels.length * 34)}
              option={{
                tooltip: {
                  position: 'top',
                  formatter: (point: any) =>
                    `${labels[point.value[0]]}<br/>${languages[point.value[1]]}: ${point.value[2]}%`,
                },
                grid: { left: 90, right: 35, top: 20, bottom: 70 },
                xAxis: { type: 'category', data: labels, axisLabel: { ...chartText, rotate: 28 } },
                yAxis: { type: 'category', data: languages, ...axis },
                visualMap: {
                  min: 0,
                  max: 100,
                  calculable: true,
                  orient: 'horizontal',
                  left: 'center',
                  bottom: 0,
                  inRange: { color: ['#eef2f3', '#9bb9c8', '#376f9e'] },
                },
                series: [
                  {
                    type: 'heatmap',
                    data: heat,
                    label: { show: true, formatter: (point: any) => `${point.value[2]}%` },
                  },
                ],
              }}
            />
          )
        ) : (
          <Empty />
        )}
      </Panel>
      <Panel
        title="Outcome profile"
        subtitle="Rates are aggregated over the current filtered records."
      >
        {labels.length ? (
          <Chart
            name={`${level.toLowerCase()}-outcome-profile`}
            option={{
              tooltip: { trigger: 'axis' },
              legend: { top: 0, textStyle: chartText },
              grid: chartGrid,
              xAxis: { type: 'category', data: labels, axisLabel: { ...chartText, rotate: 25 } },
              yAxis: { type: 'value', max: 100, name: 'Rate (%)', ...axis },
              series: [
                {
                  name: 'Build',
                  type: 'bar',
                  color: colors.orange,
                  data: labels.map((label) => mean(label, 'buildRate')),
                },
                {
                  name: 'Full pass',
                  type: 'bar',
                  color: colors.blue,
                  data: labels.map((label) => mean(label, 'fullRate')),
                },
                {
                  name: 'Test pass',
                  type: 'bar',
                  color: colors.green,
                  data: labels.map((label) => mean(label, 'testRate')),
                },
              ],
            }}
          />
        ) : (
          <Empty />
        )}
      </Panel>
    </div>
  )
}
