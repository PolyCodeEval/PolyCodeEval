import { Chart, Panel } from '../../shared/components'
import { axis, chartGrid, colors, languageColors } from '../../shared/styles/charts'
import type { LanguageSummary } from './dataset.types'

export function DatasetCharts({ summary }: { summary: LanguageSummary[] }) {
  const categoryAxis = {
    type: 'category' as const,
    data: summary.map((item) => item.language),
    ...axis,
  }
  return (
    <div className="two-grid dataset-charts">
      <Panel title="Repositories by language">
        <Chart
          name="repositories-by-language"
          option={{
            tooltip: { trigger: 'axis' },
            grid: chartGrid,
            xAxis: categoryAxis,
            yAxis: { type: 'value', name: 'Repositories', ...axis },
            series: [
              {
                type: 'bar',
                data: summary.map((item) => ({
                  value: item.repositories,
                  itemStyle: { color: languageColors[item.language] ?? colors.blue },
                })),
              },
            ],
          }}
        />
      </Panel>
      <Panel title="Oracle code volume">
        <Chart
          name="loc-by-language"
          option={{
            tooltip: { trigger: 'axis' },
            grid: chartGrid,
            xAxis: categoryAxis,
            yAxis: { type: 'value', name: 'LOC', ...axis },
            series: [
              {
                type: 'bar',
                data: summary.map((item) => ({
                  value: item.loc,
                  itemStyle: { color: languageColors[item.language] ?? colors.blue },
                })),
              },
            ],
          }}
        />
      </Panel>
    </div>
  )
}
