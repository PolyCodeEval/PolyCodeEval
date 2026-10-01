import { GitCompareArrows } from 'lucide-react'
import {
  Chart,
  Empty,
  ErrorState,
  Field,
  FilterBar,
  Loading,
  PageHeader,
  Panel,
} from '../../shared/components'
import { unique, useQueryFilters } from '../../shared/hooks/query'
import { axis, chartGrid, chartText, colors } from '../../shared/styles/charts'
import { StatisticalTables } from './StatisticalTables'
import { filterSignificanceRows, useStatisticsData } from './statistics.data'
import type { StatisticsFilters } from './statistics.types'

const initialFilters: StatisticsFilters = { level: '', search: '' }

export function StatisticsPage() {
  const { significance, paired, transitions } = useStatisticsData()
  const { filters, update, reset } = useQueryFilters(initialFilters)
  const significanceRows = filterSignificanceRows(significance.data, filters)

  return (
    <>
      <PageHeader
        eyebrow="Paired evidence"
        title="Statistical Analysis"
        description="Review selected Wilcoxon signed-rank tests and task-level L2-to-L3 paired outcomes."
      />
      <FilterBar onReset={reset}>
        <Field
          label="Search"
          value={filters.search}
          onChange={(value) => update('search', value)}
          placeholder="Comparison"
        />
        <Field
          label="Level"
          value={filters.level}
          onChange={(value) => update('level', value)}
          options={unique(significance.data.map((row) => row.level))}
        />
      </FilterBar>
      <div className="two-grid">
        <StatisticalTables
          rows={significanceRows}
          loading={significance.loading}
          error={significance.error}
        />
        <Panel
          title="L2-to-L3 state transitions"
          subtitle="Counts across paired tasks with and without related implementation context."
        >
          {paired.loading ? (
            <Loading />
          ) : paired.error ? (
            <ErrorState message={paired.error} />
          ) : transitions.length ? (
            <Chart
              name="l2-to-l3-transitions"
              option={{
                tooltip: { trigger: 'axis' },
                grid: { ...chartGrid, left: 60, bottom: 75 },
                xAxis: {
                  type: 'category',
                  data: transitions.map((transition) => transition.label),
                  axisLabel: { ...chartText, rotate: 30 },
                },
                yAxis: { type: 'value', name: 'Model-task records', ...axis },
                series: [
                  {
                    type: 'bar',
                    data: transitions.map((transition) => transition.count),
                    color: colors.green,
                  },
                ],
              }}
            />
          ) : (
            <Empty />
          )}
        </Panel>
        <Panel title="Analysis scope">
          <div className="method-note">
            <GitCompareArrows size={24} />
            <h3>Paired task design</h3>
            <p>
              The paired analysis isolates the contribution of visible related-function
              implementations while retaining the same target function and evaluation pathway.
            </p>
            <dl>
              <div>
                <dt>Unique paired tasks</dt>
                <dd>1,891</dd>
              </div>
              <div>
                <dt>Model-task records</dt>
                <dd>{paired.data.length.toLocaleString()}</dd>
              </div>
              <div>
                <dt>Test family</dt>
                <dd>Wilcoxon signed-rank</dd>
              </div>
            </dl>
          </div>
        </Panel>
      </div>
    </>
  )
}
