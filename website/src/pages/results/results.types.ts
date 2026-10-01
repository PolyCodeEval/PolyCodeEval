import type { ResultRow } from '../../shared/types/benchmark'

export interface ResultsFilterState extends Record<string, string> {
  level: string
  search: string
  language: string
  project: string
  method: string
  model: string
  source: string
  submitter: string
  build: string
  full: string
  testPass: string
}

export interface AggregatedResult {
  label: string
  language: string
  n: number
  buildRate: number
  fullRate: number
  testRate: number
}

export type ResultsRecord = ResultRow
