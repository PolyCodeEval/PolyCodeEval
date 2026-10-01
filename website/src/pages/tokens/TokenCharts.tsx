import { Chart, Empty, Panel } from '../../shared/components'
import { axis, chartText, colors } from '../../shared/styles/charts'
import type { TokenRow } from '../../shared/types/benchmark'

interface TokenChartsProps {
  rows: TokenRow[]
}

export function TokenCharts({ rows }: TokenChartsProps) {
  const generationRows = rows.filter((row) => row.level !== 'Construction')
  const labels = generationRows.map((row) =>
    [row.level, row.method, row.model, row.language].filter(Boolean).join(' · '),
  )

  return (
    <Panel
      title="Generation token composition"
      subtitle="Provider-specific token components for generation runs; construction totals remain available in the accounting table."
    >
      {generationRows.length ? (
        <Chart
          name="token-composition"
          height={Math.max(350, generationRows.length * 28)}
          option={{
            tooltip: { trigger: 'axis' },
            legend: { top: 0, textStyle: chartText },
            grid: { left: 150, right: 25, top: 45, bottom: 35 },
            xAxis: { type: 'value', name: 'Tokens', ...axis },
            yAxis: {
              type: 'category',
              data: labels,
              axisLabel: { ...chartText, width: 135, overflow: 'truncate' },
            },
            series: [
              ['input', colors.blue],
              ['output', colors.orange],
              ['draft', '#7c8993'],
              ['embedding', '#bd7770'],
            ].map(([key, color]) => ({
              name: String(key).replace(/([A-Z])/g, ' $1'),
              type: 'bar',
              stack: 'tokens',
              color,
              data: generationRows.map((row) => Number(row[key as keyof TokenRow] ?? 0)),
            })),
          }}
        />
      ) : (
        <Empty />
      )}
    </Panel>
  )
}
