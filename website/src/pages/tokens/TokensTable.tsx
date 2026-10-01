import type { ColumnDef } from '@tanstack/react-table'
import { DataTable, NumberValue, Panel } from '../../shared/components'
import type { TokenRow } from '../../shared/types/benchmark'

const columns: ColumnDef<TokenRow>[] = [
  { accessorKey: 'level', header: 'Level' },
  { accessorKey: 'method', header: 'Method' },
  { accessorKey: 'model', header: 'Model' },
  { accessorKey: 'language', header: 'Language' },
  {
    accessorKey: 'total',
    header: 'Total',
    cell: (cell) => <NumberValue value={Number(cell.getValue())} digits={0} />,
  },
  ...(
    [
      ['input', 'Input'],
      ['output', 'Output'],
      ['draft', 'Draft'],
      ['embedding', 'Embedding'],
    ] as const
  ).map(([key, header]) => ({
    accessorKey: key,
    header,
    cell: (cell: { getValue: () => unknown }) => (
      <NumberValue value={Number(cell.getValue())} digits={0} />
    ),
  })),
  {
    accessorKey: 'cost',
    header: 'Cost (USD)',
    cell: (cell) => <NumberValue value={cell.getValue() as number | null} />,
  },
]

export function TokensTable({ rows }: { rows: TokenRow[] }) {
  return (
    <Panel
      title="Accounting records"
      subtitle="A dash denotes a cost that was not preserved in the source summary."
    >
      <DataTable data={rows} columns={columns} name="token-accounting" />
    </Panel>
  )
}
