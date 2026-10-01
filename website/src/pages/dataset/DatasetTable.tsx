import type { ColumnDef } from '@tanstack/react-table'
import { Badge, DataTable, NumberValue, Panel, Ratio } from '../../shared/components'
import type { DatasetRecord } from './dataset.types'

const columns: ColumnDef<DatasetRecord>[] = [
  { accessorKey: 'project', header: 'Repository' },
  {
    accessorKey: 'language',
    header: 'Language',
    cell: (cell) => <Badge value={String(cell.getValue())} />,
  },
  { accessorKey: 'difficulty', header: 'Difficulty' },
  {
    accessorKey: 'loc',
    header: 'Oracle LOC',
    cell: (cell) => <NumberValue value={cell.getValue() as number | null} digits={0} />,
  },
  { accessorKey: 'testFramework', header: 'Tests' },
  { accessorKey: 'source', header: 'Source' },
  ...['L0', 'L1', 'L2', 'L3'].map(
    (level) =>
      ({
        id: level,
        header: level,
        accessorFn: (row: DatasetRecord) => row.levels[level] ?? 0,
      }) as ColumnDef<DatasetRecord>,
  ),
  {
    accessorKey: 'coverage',
    header: 'Coverage',
    cell: (cell) => <Ratio value={cell.getValue() as number | null} />,
  },
  {
    accessorKey: 'oracleValidated',
    header: 'Oracle',
    cell: (cell) =>
      cell.getValue() === null ? (
        '—'
      ) : (
        <Badge
          tone={cell.getValue() ? 'success' : 'danger'}
          value={cell.getValue() ? 'Validated' : 'Failed'}
        />
      ),
  },
]

export function DatasetTable({
  rows,
  onSelect,
}: {
  rows: DatasetRecord[]
  onSelect: (row: DatasetRecord) => void
}) {
  return (
    <Panel
      title="Repository registry"
      subtitle="Select a repository to inspect its task contribution, coverage, and Oracle status."
    >
      <DataTable data={rows} columns={columns} onRowClick={onSelect} name="polycodeeval-dataset" />
    </Panel>
  )
}
