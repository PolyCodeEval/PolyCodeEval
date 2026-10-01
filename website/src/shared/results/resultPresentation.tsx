import type { ColumnDef } from '@tanstack/react-table'
import { Badge, Field, FilterBar, NumberValue, Ratio } from '../components'
import { unique } from '../hooks/query'
import type { ResultRow } from '../types/benchmark'

const shortModel = (model: string) =>
  model.includes('GPT')
    ? 'GPT'
    : model.includes('Sonnet')
      ? 'Sonnet'
      : model.includes('DeepSeek')
        ? 'DeepSeek'
        : model

export const resultFields = {
  level: (r: ResultRow) => r.level,
  search: (r: ResultRow) => `${r.taskId} ${r.project} ${r.method} ${r.model}`,
  language: (r: ResultRow) => r.language,
  project: (r: ResultRow) => r.project,
  method: (r: ResultRow) => r.method,
  model: (r: ResultRow) => r.model,
  source: (r: ResultRow) => r.sourceType,
  submitter: (r: ResultRow) => r.submitter,
  build: (r: ResultRow) =>
    r.buildSuccess === null ? 'Unknown' : r.buildSuccess ? 'Success' : 'Failed',
  full: (r: ResultRow) => (r.fullPass === null ? 'Unknown' : r.fullPass ? 'Passed' : 'Not passed'),
  testPass: (r: ResultRow) =>
    r.testPassRatio === null
      ? 'Unavailable'
      : r.testPassRatio === 1
        ? '100%'
        : r.testPassRatio === 0
          ? '0%'
          : r.testPassRatio < 0.5
            ? '0.1–49.9%'
            : '50.0–99.9%',
}

export const resultColumns: ColumnDef<ResultRow>[] = [
  {
    accessorKey: 'taskId',
    header: 'Task',
    cell: (x) => (
      <span className="mono ellipsis" title={String(x.getValue())}>
        {String(x.getValue())}
      </span>
    ),
  },
  {
    accessorKey: 'language',
    header: 'Language',
    cell: (x) => <Badge value={String(x.getValue())} />,
  },
  { accessorKey: 'project', header: 'Project' },
  { accessorKey: 'method', header: 'Method' },
  { accessorKey: 'model', header: 'Model' },
  {
    accessorKey: 'sourceType',
    header: 'Source',
    cell: (x) => (
      <Badge
        tone={x.getValue() === 'Community Self-Evaluated' ? 'accent' : 'neutral'}
        value={String(x.getValue())}
      />
    ),
  },
  {
    accessorKey: 'buildSuccess',
    header: 'Build',
    cell: (x) =>
      x.row.original.missing ? (
        <Badge tone="neutral" value="Not submitted · Score 0" />
      ) : x.getValue() === null ? (
        '—'
      ) : (
        <Badge
          tone={x.getValue() ? 'success' : 'danger'}
          value={x.getValue() ? 'Success' : 'Failed'}
        />
      ),
  },
  {
    accessorKey: 'fullPass',
    header: 'Full pass',
    cell: (x) =>
      x.getValue() === null ? (
        '—'
      ) : (
        <Badge tone={x.getValue() ? 'success' : 'neutral'} value={x.getValue() ? 'Passed' : 'No'} />
      ),
  },
  {
    accessorKey: 'testPassRatio',
    header: 'Test pass',
    cell: (x) => <Ratio value={x.getValue() as number | null} />,
  },
  {
    accessorKey: 'executionScore',
    header: 'Execution',
    cell: (x) => <NumberValue value={x.getValue() as number | null} />,
  },
]

export function aggregateResults(rows: ResultRow[]) {
  const map = new Map<
    string,
    {
      label: string
      language: string
      n: number
      build: number
      full: number
      test: number
      testN: number
    }
  >()
  rows.forEach((r) => {
    const label =
      [r.method, shortModel(r.model), r.submitter ? `@${r.submitter}` : '']
        .filter(Boolean)
        .join(' · ') || 'Unspecified'
    const key = `${r.sourceType}|${r.submissionId}|${label}|${r.language}`
    const current = map.get(key) ?? {
      label,
      language: r.language || 'All',
      n: 0,
      build: 0,
      full: 0,
      test: 0,
      testN: 0,
    }
    current.n += 1
    if (r.buildSuccess) current.build += 1
    if (r.fullPass) current.full += 1
    if (r.buildSuccess && r.testPassRatio !== null) {
      current.test += r.testPassRatio
      current.testN += 1
    }
    map.set(key, current)
  })
  return [...map.values()].map((v) => ({
    ...v,
    buildRate: v.build / v.n,
    fullRate: v.full / v.n,
    testRate: v.testN ? v.test / v.testN : 0,
  }))
}

type ResultFilterKey =
  | 'level'
  | 'search'
  | 'language'
  | 'project'
  | 'method'
  | 'model'
  | 'source'
  | 'submitter'
  | 'build'
  | 'full'
  | 'testPass'

export function ResultsFilters({
  rows,
  filters,
  update,
  reset,
}: {
  rows: ResultRow[]
  filters: Record<ResultFilterKey, string>
  update: (key: ResultFilterKey, value: string) => void
  reset: () => void
}) {
  return (
    <FilterBar onReset={reset}>
      <Field
        label="Search"
        value={filters.search}
        onChange={(v) => update('search', v)}
        placeholder="Task or project"
      />
      <Field
        label="Language"
        value={filters.language}
        onChange={(v) => update('language', v)}
        options={unique(rows.map((r) => r.language))}
      />
      <Field
        label="Project"
        value={filters.project}
        onChange={(v) => update('project', v)}
        options={unique(rows.map((r) => r.project))}
      />
      <Field
        label="Method"
        value={filters.method}
        onChange={(v) => update('method', v)}
        options={unique(rows.map((r) => r.method))}
      />
      <Field
        label="Model"
        value={filters.model}
        onChange={(v) => update('model', v)}
        options={unique(rows.map((r) => r.model))}
      />
      <Field
        label="Source"
        value={filters.source}
        onChange={(v) => update('source', v)}
        options={unique(rows.map((r) => r.sourceType))}
      />
      <Field
        label="Submitter"
        value={filters.submitter}
        onChange={(v) => update('submitter', v)}
        options={unique(rows.map((r) => r.submitter))}
      />
      <Field
        label="Build"
        value={filters.build}
        onChange={(v) => update('build', v)}
        options={['Success', 'Failed', 'Unknown']}
      />
      <Field
        label="Full pass"
        value={filters.full}
        onChange={(v) => update('full', v)}
        options={['Passed', 'Not passed', 'Unknown']}
      />
      <Field
        label="Test pass"
        value={filters.testPass}
        onChange={(v) => update('testPass', v)}
        options={['0%', '0.1–49.9%', '50.0–99.9%', '100%', 'Unavailable']}
      />
    </FilterBar>
  )
}
