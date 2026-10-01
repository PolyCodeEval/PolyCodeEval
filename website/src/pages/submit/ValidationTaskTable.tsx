import type { ColumnDef } from '@tanstack/react-table'
import { Badge, DataTable, NumberValue, Ratio } from '../../shared/components'
import type { ValidationTask } from './submit.types'

const columns: ColumnDef<ValidationTask>[] = [
  {
    accessorKey: 'taskId',
    header: 'Task',
    cell: (cell) => (
      <span className="mono ellipsis" title={String(cell.getValue())}>
        {String(cell.getValue())}
      </span>
    ),
  },
  { accessorKey: 'language', header: 'Language' },
  { accessorKey: 'project', header: 'Project' },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: (cell) => (
      <Badge
        tone={
          cell.getValue() === 'Submitted'
            ? 'success'
            : cell.getValue() === 'Extra'
              ? 'danger'
              : 'neutral'
        }
        value={String(cell.getValue())}
      />
    ),
  },
  {
    accessorKey: 'buildSuccess',
    header: 'Build',
    cell: (cell) => (
      <Badge
        tone={cell.getValue() ? 'success' : 'neutral'}
        value={cell.getValue() ? 'Success' : 'No'}
      />
    ),
  },
  {
    accessorKey: 'fullPass',
    header: 'Full pass',
    cell: (cell) => (
      <Badge
        tone={cell.getValue() ? 'success' : 'neutral'}
        value={cell.getValue() ? 'Passed' : 'No'}
      />
    ),
  },
  {
    accessorKey: 'testPassRatio',
    header: 'Test pass',
    cell: (cell) => <Ratio value={Number(cell.getValue())} />,
  },
  {
    accessorKey: 'executionScore',
    header: 'Execution',
    cell: (cell) => <NumberValue value={Number(cell.getValue())} digits={3} />,
  },
]

export function ValidationTaskTable({ rows }: { rows: ValidationTask[] }) {
  return <DataTable data={rows} columns={columns} name="submission-validation-tasks" />
}
