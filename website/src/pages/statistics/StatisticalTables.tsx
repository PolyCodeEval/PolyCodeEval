import type { ColumnDef } from '@tanstack/react-table'
import { Badge, DataTable, ErrorState, Loading, NumberValue, Panel } from '../../shared/components'
import type { SignificanceRow } from '../../shared/types/benchmark'

const columns: ColumnDef<SignificanceRow>[] = [
  { accessorKey: 'comparison', header: 'Comparison' },
  { accessorKey: 'level', header: 'Level' },
  {
    accessorKey: 'n',
    header: 'N',
    cell: (cell) => <NumberValue value={cell.getValue() as number | null} digits={0} />,
  },
  {
    accessorKey: 'statistic',
    header: 'Statistic',
    cell: (cell) => <NumberValue value={cell.getValue() as number | null} />,
  },
  {
    accessorKey: 'difference',
    header: 'Difference',
    cell: (cell) => <NumberValue value={cell.getValue() as number | null} />,
  },
  {
    accessorKey: 'pValue',
    header: 'p-value',
    cell: (cell) => (
      <span className="mono">
        {cell.getValue() === null ? '—' : Number(cell.getValue()).toExponential(2)}
      </span>
    ),
  },
  { accessorKey: 'adjustment', header: 'Adjustment' },
  {
    id: 'significant',
    header: 'p < 0.05',
    accessorFn: (row) => row.pValue !== null && row.pValue < 0.05,
    cell: (cell) => (
      <Badge
        tone={cell.getValue() ? 'success' : 'neutral'}
        value={cell.getValue() ? 'Yes' : 'No'}
      />
    ),
  },
  { accessorKey: 'interpretation', header: 'Hypothesis' },
]

interface StatisticalTablesProps {
  rows: SignificanceRow[]
  loading: boolean
  error: string | null
}

export function StatisticalTables({ rows, loading, error }: StatisticalTablesProps) {
  return (
    <Panel
      title="Significance tests"
      subtitle="Selected comparisons use Holm-adjusted p-values; L2-to-L3 tests report unadjusted paired-test values."
      className="span-2"
    >
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorState message={error} />
      ) : (
        <DataTable data={rows} columns={columns} name="significance-tests" />
      )}
    </Panel>
  )
}
