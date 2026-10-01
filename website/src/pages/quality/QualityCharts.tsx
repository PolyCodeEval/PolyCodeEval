import { Chart, Empty, ErrorState, Loading, Panel } from '../../shared/components'
import { axis, chartGrid, chartText, colors } from '../../shared/styles/charts'
import type { CoverageDistribution, PromptQualitySummary } from './quality.types'

interface QualityChartsProps {
  coverage: CoverageDistribution
  coverageLoading: boolean
  coverageError: string | null
  promptQuality: PromptQualitySummary
  promptQualityLoading: boolean
  promptQualityError: string | null
}

export function QualityCharts({
  coverage,
  coverageLoading,
  coverageError,
  promptQuality,
  promptQualityLoading,
  promptQualityError,
}: QualityChartsProps) {
  return (
    <div className="two-grid">
      <Panel
        title="Coverage distributions"
        subtitle="Per-project or per-task coverage, grouped by level and language."
      >
        {coverageLoading ? (
          <Loading />
        ) : coverageError ? (
          <ErrorState message={coverageError} />
        ) : coverage.values.length ? (
          <Chart
            name="coverage-distributions"
            option={{
              tooltip: { trigger: 'item' },
              grid: { ...chartGrid, left: 58, bottom: 75 },
              xAxis: {
                type: 'category',
                data: coverage.groups,
                axisLabel: { ...chartText, rotate: 30 },
              },
              yAxis: { type: 'value', max: 100, name: 'Coverage (%)', ...axis },
              series: [
                {
                  type: 'boxplot',
                  data: coverage.values,
                  itemStyle: { color: '#dbe8ee', borderColor: colors.blue },
                },
              ],
            }}
          />
        ) : (
          <Empty />
        )}
      </Panel>
      <Panel
        title="Prompt-quality scores"
        subtitle="Mean score for each available level and judge."
      >
        {promptQualityLoading ? (
          <Loading />
        ) : promptQualityError ? (
          <ErrorState message={promptQualityError} />
        ) : promptQuality.groups.length ? (
          <Chart
            name="prompt-quality"
            option={{
              tooltip: { trigger: 'axis' },
              grid: { ...chartGrid, bottom: 75 },
              xAxis: {
                type: 'category',
                data: promptQuality.groups,
                axisLabel: { ...chartText, rotate: 30 },
              },
              yAxis: { type: 'value', name: 'Mean score', ...axis },
              series: [{ type: 'bar', data: promptQuality.averages, color: colors.purple }],
            }}
          />
        ) : (
          <Empty />
        )}
      </Panel>
    </div>
  )
}
