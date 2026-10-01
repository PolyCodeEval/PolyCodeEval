import { DataTable, Panel } from '../../shared/components'
import { resultColumns } from '../../shared/results/resultPresentation'
import type { ResultRow } from '../../shared/types/benchmark'

export function TasksTable({
  rows,
  level,
  onSelect,
}: {
  rows: ResultRow[]
  level: string
  onSelect: (row: ResultRow) => void
}) {
  return (
    <Panel
      title={`${level} task matrix`}
      subtitle="Select a row to inspect all available metrics and the normalized source record."
    >
      <DataTable
        data={rows}
        columns={resultColumns}
        onRowClick={onSelect}
        name={`${level.toLowerCase()}-tasks`}
      />
    </Panel>
  )
}
