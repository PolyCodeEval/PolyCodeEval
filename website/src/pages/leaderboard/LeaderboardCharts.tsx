import { Chart, Empty, Panel } from '../../shared/components'
import { axis, chartGrid, chartText, colors } from '../../shared/styles/charts'
import type { RankedEntry } from './leaderboard.types'

const shortModel = (model: string) =>
  model.replace('Claude Sonnet 4.6', 'Sonnet 4.6').replace('DeepSeek-V4-Pro', 'DeepSeek V4')

export function LeaderboardCharts({ rows, level }: { rows: RankedEntry[]; level: string }) {
  const overall = rows.filter((row) => !row.language)
  const labels = overall.map((row) => `${row.method} · ${shortModel(row.model)}`)
  return (
    <div className="two-grid leaderboard-charts">
      <Panel
        title="Execution ranking"
        subtitle="Full-pass rate for maintainer-evaluated configurations."
      >
        {overall.length ? (
          <Chart
            name={`${level.toLowerCase()}-leaderboard-full-pass`}
            height={Math.max(280, overall.length * 35)}
            option={{
              tooltip: { trigger: 'axis' },
              grid: { ...chartGrid, left: 145, right: 45, top: 12, bottom: 30 },
              xAxis: { type: 'value', max: 100, name: 'Full pass (%)', ...axis },
              yAxis: {
                type: 'category',
                inverse: true,
                data: labels,
                axisLabel: { ...chartText, width: 135, overflow: 'truncate' },
              },
              series: [
                {
                  type: 'bar',
                  color: colors.blue,
                  data: overall.map((row) => +(row.fullPassRate * 100).toFixed(1)),
                  label: { show: true, position: 'right', formatter: '{c}%' },
                },
              ],
            }}
          />
        ) : (
          <Empty />
        )}
      </Panel>
      <Panel
        title="Build and full-pass profile"
        subtitle="Execution rates over the complete task set."
      >
        {overall.length ? (
          <Chart
            name={`${level.toLowerCase()}-leaderboard-profile`}
            height={Math.max(280, overall.length * 35)}
            option={{
              tooltip: { trigger: 'axis' },
              legend: { top: 0, textStyle: chartText },
              grid: { ...chartGrid, left: 145, right: 28, top: 42, bottom: 30 },
              xAxis: { type: 'value', max: 100, name: 'Rate (%)', ...axis },
              yAxis: {
                type: 'category',
                inverse: true,
                data: labels,
                axisLabel: { ...chartText, width: 135, overflow: 'truncate' },
              },
              series: [
                {
                  name: 'Build success',
                  type: 'bar',
                  color: colors.orange,
                  data: overall.map((row) => +(row.buildSuccessRate * 100).toFixed(1)),
                },
                {
                  name: 'Full pass',
                  type: 'bar',
                  color: colors.blue,
                  data: overall.map((row) => +(row.fullPassRate * 100).toFixed(1)),
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
