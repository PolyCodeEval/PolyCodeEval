import type { DatasetRow } from '../../shared/types/benchmark'

export interface DatasetFiltersState extends Record<string, string> {
  search: string
  language: string
  difficulty: string
  framework: string
  source: string
  level: string
}

export interface LanguageSummary {
  language: string
  repositories: number
  loc: number
}

export type DatasetRecord = DatasetRow
