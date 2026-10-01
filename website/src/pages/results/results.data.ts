import { useMemo } from 'react'
import { useTaskResults } from '../../shared/hooks/data'
import { useFiltered } from '../../shared/hooks/query'
import type { AggregatedResult, ResultsFilterState, ResultsRecord } from './results.types'

const shortModel = (model: string) =>
  model.includes('GPT')
    ? 'GPT'
    : model.includes('Sonnet')
      ? 'Sonnet'
      : model.includes('DeepSeek')
        ? 'DeepSeek'
        : model

const resultFields = {
  level: (row: ResultsRecord) => row.level,
  search: (row: ResultsRecord) => `${row.taskId} ${row.project} ${row.method} ${row.model}`,
  language: (row: ResultsRecord) => row.language,
  project: (row: ResultsRecord) => row.project,
  method: (row: ResultsRecord) => row.method,
  model: (row: ResultsRecord) => row.model,
  source: (row: ResultsRecord) => row.sourceType,
  submitter: (row: ResultsRecord) => row.submitter,
  build: (row: ResultsRecord) =>
    row.buildSuccess === null ? 'Unknown' : row.buildSuccess ? 'Success' : 'Failed',
  full: (row: ResultsRecord) =>
    row.fullPass === null ? 'Unknown' : row.fullPass ? 'Passed' : 'Not passed',
  testPass: (row: ResultsRecord) =>
    row.testPassRatio === null
      ? 'Unavailable'
      : row.testPassRatio === 1
        ? '100%'
        : row.testPassRatio === 0
          ? '0%'
          : row.testPassRatio < 0.5
            ? '0.1–49.9%'
            : '50.0–99.9%',
}

export function aggregateResults(rows: ResultsRecord[]): AggregatedResult[] {
  const groups = new Map<
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
  rows.forEach((row) => {
    const label =
      [row.method, shortModel(row.model), row.submitter ? `@${row.submitter}` : '']
        .filter(Boolean)
        .join(' · ') || 'Unspecified'
    const key = `${row.sourceType}|${row.submissionId}|${label}|${row.language}`
    const group = groups.get(key) ?? {
      label,
      language: row.language || 'All',
      n: 0,
      build: 0,
      full: 0,
      test: 0,
      testN: 0,
    }
    group.n += 1
    if (row.buildSuccess) group.build += 1
    if (row.fullPass) group.full += 1
    if (row.buildSuccess && row.testPassRatio !== null) {
      group.test += row.testPassRatio
      group.testN += 1
    }
    groups.set(key, group)
  })
  return [...groups.values()].map((group) => ({
    label: group.label,
    language: group.language,
    n: group.n,
    buildRate: group.build / group.n,
    fullRate: group.full / group.n,
    testRate: group.testN ? group.test / group.testN : 0,
  }))
}

export function useResultsData(filters: ResultsFilterState) {
  const source = useTaskResults(filters.level, filters.language)
  const rows = useFiltered(source.data, filters, resultFields)
  const aggregates = useMemo(() => aggregateResults(rows), [rows])
  return { source, rows, aggregates }
}
