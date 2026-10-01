export type JsonRecord = Record<string, unknown>

export interface Manifest {
  version: string
  generatedAt: string
  repositories: number
  taskCounts: Record<string, number>
  configurations: unknown[]
}

export interface DatasetRow {
  language: string
  project: string
  difficulty: string
  testFramework: string
  source: string
  loc: number | null
  coverage: number | null
  oracleValidated: boolean | null
  levels: Record<string, number>
  raw: JsonRecord
}

export interface ResultRow {
  level: string
  language: string
  project: string
  taskId: string
  method: string
  model: string
  buildSuccess: boolean | null
  fullPass: boolean | null
  testPassRatio: number | null
  executionScore: number | null
  correctness: number | null
  faithfulness: number | null
  architecture: number | null
  health: number | null
  overall: number | null
  submissionId: string
  submitter: string
  sourceType: string
  submittedTasks: number | null
  expectedTasks: number | null
  coverageRate: number | null
  pullRequestUrl: string
  mergeCommit: string
  scoringMode: string
  qualityEligible: boolean
  missing: boolean
  sourceLink: string
  raw: JsonRecord
}

export interface CoverageRow {
  level: string
  language: string
  project: string
  metric: string
  value: number | null
  raw: JsonRecord
}

export interface PromptQualityRow {
  level: string
  language: string
  project: string
  taskId: string
  judge: string
  score: number | null
  raw: JsonRecord
}

export interface SignificanceRow {
  comparison: string
  level: string
  n: number | null
  statistic: number | null
  difference: number | null
  pValue: number | null
  adjustment: string
  interpretation: string
  raw: JsonRecord
}

export interface TokenRow {
  level: string
  method: string
  model: string
  language: string
  input: number
  output: number
  cacheRead: number
  cacheCreation: number
  draft: number
  embedding: number
  total: number
  cost: number | null
  raw: JsonRecord
}

export interface PromptEntry {
  id: string
  title: string
  category: string
  role: string
  purpose: string
  template: string
  variables: string[]
  outputFormat: string
  example: string
}

export interface LoadState<T> {
  data: T
  loading: boolean
  error: string | null
}
