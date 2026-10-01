import type { CoverageRow, PromptQualityRow } from '../../shared/types/benchmark'

export interface QualityFilters {
  level: string
  language: string
  project: string
  judge: string
}

export interface CoverageDistribution {
  groups: string[]
  values: number[][]
}

export interface PromptQualitySummary {
  groups: string[]
  averages: number[]
}

export interface QualityPageData {
  coverageRows: CoverageRow[]
  qualityRows: PromptQualityRow[]
  coverageDistribution: CoverageDistribution
  promptQualitySummary: PromptQualitySummary
}

export interface CommunityQualityRow {
  submissionId: string
  submitter: string
  level: string
  method: string
  model: string
  coverageRate: number
  correctness: number | null
  faithfulness: number | null
  architecture: number | null
  health: number | null
  overall: number | null
}
