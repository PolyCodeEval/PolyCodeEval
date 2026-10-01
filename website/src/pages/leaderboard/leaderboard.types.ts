export interface LeaderboardEntry {
  id: string
  configuration: string
  level: string
  scopeType?: 'all' | 'language'
  scope?: string
  language: string
  method: string
  model: string
  total: number
  buildSuccessCount?: number
  fullPassCount?: number
  buildSuccessRate: number
  fullPassRate: number
  conditionalTestPassRatio: number | null
  executionScore: number
  correctness: number | null
  faithfulness: number | null
  architecture: number | null
  health: number | null
  overall: number | null
  sourceType: string
  submitter: string
  submissionId: string
  submittedTasks: number
  expectedTasks: number
  coverageRate: number
  pullRequestUrl: string
  mergeCommit: string
  scoringMode: string
  qualityEligible: boolean
  benchmarkVersion: string
  evaluatedAt: string | null
  reviewedAt?: string | null
}

export interface RankedEntry extends LeaderboardEntry {
  rank: number
}

export interface LeaderboardSnapshot {
  benchmarkVersion: string
  generatedAt: string
  records: LeaderboardEntry[]
}
