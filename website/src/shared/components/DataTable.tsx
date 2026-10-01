import { useState } from 'react'
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type PaginationState,
  type SortingState,
  type VisibilityState,
} from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ChevronsUpDown, Columns3, Download } from 'lucide-react'
import { Empty } from './States'

const display = (value: unknown) =>
  value === null || value === undefined || value === ''
    ? '—'
    : typeof value === 'boolean'
      ? value
        ? 'Yes'
        : 'No'
      : String(value)

export function DataTable<T extends object>({
  data,
  columns,
  pageSize = 20,
  onRowClick,
  name = 'data',
}: {
  data: T[]
  columns: ColumnDef<T>[]
  pageSize?: 20 | 50 | 100
  onRowClick?: (row: T) => void
  name?: string
}) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize })
  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnVisibility, pagination },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  })
  const exportCsv = () => {
    const headers = columns.map((c) =>
      typeof c.header === 'string'
        ? c.header
        : String(c.id ?? ('accessorKey' in c ? c.accessorKey : 'Value')),
    )
    const rows = data.map((item) =>
      columns
        .map((c) => {
          const key = 'accessorKey' in c ? String(c.accessorKey) : String(c.id ?? '')
          return JSON.stringify(display((item as Record<string, unknown>)[key]))
        })
        .join(','),
    )
    const blob = new Blob([[headers.join(','), ...rows].join('\n')], {
      type: 'text/csv;charset=utf-8',
    })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${name}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }
  if (!data.length) return <Empty />
  return (
    <div className="table-block">
      <div className="table-toolbar">
        <span>{data.length.toLocaleString()} records</span>
        <div className="table-actions">
          <details className="column-menu">
            <summary className="button button-quiet">
              <Columns3 size={15} />
              Columns
            </summary>
            <div>
              {table.getAllLeafColumns().map((column) => (
                <label key={column.id}>
                  <input
                    type="checkbox"
                    checked={column.getIsVisible()}
                    onChange={column.getToggleVisibilityHandler()}
                  />
                  <span>
                    {typeof column.columnDef.header === 'string'
                      ? column.columnDef.header
                      : column.id}
                  </span>
                </label>
              ))}
            </div>
          </details>
          <button className="button button-quiet" onClick={exportCsv}>
            <Download size={15} />
            Export CSV
          </button>
        </div>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => (
                  <th
                    key={header.id}
                    onClick={header.column.getToggleSortingHandler()}
                    className={header.column.getCanSort() ? 'sortable' : ''}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                    {header.column.getCanSort() &&
                      (header.column.getIsSorted() === 'asc' ? (
                        <ArrowUp size={13} />
                      ) : header.column.getIsSorted() === 'desc' ? (
                        <ArrowDown size={13} />
                      ) : (
                        <ChevronsUpDown size={13} />
                      ))}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                onClick={() => onRowClick?.(row.original)}
                className={onRowClick ? 'clickable' : ''}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <div className="pagination-summary">
          <span>
            Page {table.getState().pagination.pageIndex + 1} of {Math.max(table.getPageCount(), 1)}
          </span>
          <label>
            Rows per page
            <select
              aria-label="Rows per page"
              value={table.getState().pagination.pageSize}
              onChange={(event) => {
                table.setPageSize(Number(event.target.value))
                table.setPageIndex(0)
              }}
            >
              {[20, 50, 100].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div>
          <button
            className="button button-quiet"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Previous
          </button>
          <button
            className="button button-quiet"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
