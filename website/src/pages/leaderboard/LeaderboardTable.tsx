import type { ColumnDef } from '@tanstack/react-table'
import { ExternalLink } from 'lucide-react'
import { Badge, DataTable, NumberValue, Ratio } from '../../shared/components'
import type { RankedEntry } from './leaderboard.types'

const columns: ColumnDef<RankedEntry>[] = [
  {
    accessorKey: 'rank',
    header: 'Rank',
    cell: (cell) => <strong className="rank-value">{String(cell.getValue())}</strong>,
  },
  { accessorKey: 'method', header: 'Method' },
  { accessorKey: 'model', header: 'Model' },
  {
    accessorKey: 'submitter',
    header: 'Submitter',
    cell: (cell) => String(cell.getValue() || '—'),
  },
  {
    accessorKey: 'language',
    header: 'Scope',
    cell: (cell) =>
      cell.getValue() ? (
        <Badge value={String(cell.getValue())} />
      ) : (
        <Badge tone="accent" value="Overall" />
      ),
  },
  {
    accessorKey: 'coverageRate',
    header: 'Coverage',
    cell: (cell) => <Ratio value={Number(cell.getValue())} />,
  },
  {
    accessorKey: 'fullPassRate',
    header: 'Full pass',
    cell: (cell) => <Ratio value={Number(cell.getValue())} />,
  },
  {
    accessorKey: 'executionScore',
    header: 'Execution',
    cell: (cell) => <NumberValue value={Number(cell.getValue())} digits={3} />,
  },
  {
    accessorKey: 'buildSuccessRate',
    header: 'Build',
    cell: (cell) => <Ratio value={Number(cell.getValue())} />,
  },
  {
    accessorKey: 'conditionalTestPassRatio',
    header: 'Test if built',
    cell: (cell) => <Ratio value={cell.getValue() as number | null} />,
  },
  {
    accessorKey: 'overall',
    header: 'Quality',
    cell: (cell) => <NumberValue value={cell.getValue() as number | null} digits={2} />,
  },
  {
    accessorKey: 'sourceType',
    header: 'Source',
    cell: (cell) => (
      <Badge
        tone={cell.getValue() === 'Community Self-Evaluated' ? 'accent' : 'success'}
        value={String(cell.getValue())}
      />
    ),
  },
  {
    accessorKey: 'pullRequestUrl',
    header: 'PR',
    cell: (cell) =>
      cell.getValue() ? (
        <a
          className="icon-link"
          href={String(cell.getValue())}
          target="_blank"
          rel="noreferrer"
          title="Open pull request"
          onClick={(event) => event.stopPropagation()}
        >
          <ExternalLink size={15} />
        </a>
      ) : (
        '—'
      ),
  },
  {
    accessorKey: 'reviewedAt',
    header: 'Reviewed',
    cell: (cell) => {
      const value = cell.getValue()
      return value ? new Date(String(value)).toLocaleDateString('en-CA') : '—'
    },
  },
]

export function LeaderboardTable({ rows, level }: { rows: RankedEntry[]; level: string }) {
  const openResults = (row: RankedEntry) => {
    const params = new URLSearchParams({ level: row.level, method: row.method, model: row.model })
    if (row.language) params.set('language', row.language)
    if (row.sourceType) params.set('source', row.sourceType)
    if (row.submitter) params.set('submitter', row.submitter)
    window.location.hash = `/results?${params.toString()}`
  }
  return (
    <DataTable
      data={rows}
      columns={columns}
      name={`${level.toLowerCase()}-leaderboard`}
      onRowClick={openResults}
    />
  )
}
