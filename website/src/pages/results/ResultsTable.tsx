import type { ColumnDef } from '@tanstack/react-table'
import { Badge, DataTable, NumberValue, Panel, Ratio } from '../../shared/components'
import type { ResultsRecord } from './results.types'

const columns: ColumnDef<ResultsRecord>[] = [
  {
    accessorKey: 'taskId',
    header: 'Task',
    cell: (cell) => (
      <span className="mono ellipsis" title={String(cell.getValue())}>
        {String(cell.getValue())}
      </span>
    ),
  },
  {
    accessorKey: 'language',
    header: 'Language',
    cell: (cell) => <Badge value={String(cell.getValue())} />,
  },
  { accessorKey: 'project', header: 'Project' },
  { accessorKey: 'method', header: 'Method' },
  { accessorKey: 'model', header: 'Model' },
  {
    accessorKey: 'sourceType',
    header: 'Source',
    cell: (cell) => (
      <Badge
        tone={cell.getValue() === 'Community Self-Evaluated' ? 'accent' : 'neutral'}
        value={String(cell.getValue())}
      />
    ),
  },
  {
    accessorKey: 'buildSuccess',
    header: 'Build',
    cell: (cell) =>
      cell.row.original.missing ? (
        <Badge tone="neutral" value="Not submitted · Score 0" />
      ) : cell.getValue() === null ? (
        '—'
      ) : (
        <Badge
          tone={cell.getValue() ? 'success' : 'danger'}
          value={cell.getValue() ? 'Success' : 'Failed'}
        />
      ),
  },
  {
    accessorKey: 'fullPass',
    header: 'Full pass',
    cell: (cell) =>
      cell.getValue() === null ? (
        '—'
      ) : (
        <Badge
          tone={cell.getValue() ? 'success' : 'neutral'}
          value={cell.getValue() ? 'Passed' : 'No'}
        />
      ),
  },
  {
    accessorKey: 'testPassRatio',
    header: 'Test pass',
    cell: (cell) => <Ratio value={cell.getValue() as number | null} />,
  },
  {
    accessorKey: 'executionScore',
    header: 'Execution',
    cell: (cell) => <NumberValue value={cell.getValue() as number | null} />,
  },
  {
    accessorKey: 'coverageRate',
    header: 'Coverage',
    cell: (cell) => <Ratio value={cell.getValue() as number | null} />,
  },
]

export function ResultsTable({ rows, level }: { rows: ResultsRecord[]; level: string }) {
  return (
    <Panel
      title="Task-level results"
      subtitle="Sort columns, export the current selection, or continue to the Task Explorer for record details."
    >
      <DataTable data={rows} columns={columns} name={`${level.toLowerCase()}-results`} />
    </Panel>
  )
}
