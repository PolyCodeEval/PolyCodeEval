export type EvaluationLevel = 'L0' | 'L1' | 'L2' | 'L3'
export type ScoringMode = 'correctness_only' | 'full_quality' | 'execution'

export interface SubmissionEnvironment {
  os: string
  architecture: string
  python: string
  docker: string
}

export interface SubmissionMetadata {
  schemaVersion: '2'
  benchmarkVersion: string
  level: EvaluationLevel
  submissionName: string
  submitter: { github: string; affiliation: string }
  method: { name: string; version: string; paperUrl: string; codeUrl: string }
  model: { name: string; version: string; provider: string }
  evaluation: {
    polycodeevalCommit: string
    testMode: 'both' | 'blackbox' | 'whitebox' | 'mixed'
    scoringMode: ScoringMode
    command: string
    startedAt: string
    finishedAt: string
    packagedAt?: string
    workingTreeDirty?: boolean
    environment: SubmissionEnvironment
  }
  notes: string
}

export interface ReleaseManifest {
  benchmarkVersion: string
  taskCounts: Record<EvaluationLevel, number>
  tasks: Record<EvaluationLevel, string[]>
}

export interface ValidationIssue {
  severity: 'error' | 'warning'
  code: string
  message: string
  path?: string
}

export interface EvaluationMetrics {
  submitted: number
  expected: number
  buildSuccessRate: number
  fullPassRate: number
  conditionalTestPassRatio: number | null
  executionScore: number
  correctness: number | null
  faithfulness: number | null
  architecture: number | null
  health: number | null
  overall: number | null
}

export interface ValidationTask {
  taskId: string
  language: string
  project: string
  status: 'Submitted' | 'Missing' | 'Extra'
  buildSuccess: boolean
  fullPass: boolean
  testPassRatio: number
  executionScore: number
  correctness: number | null
  qualityEligible: boolean
  sourcePath: string
}

export interface ValidationReport {
  valid: boolean
  fileName: string
  archiveBytes: number
  fileCount: number
  benchmarkVersion: string
  level: EvaluationLevel | ''
  scoringMode: ScoringMode | ''
  expectedTasks: number
  submittedTasks: number
  missingTasks: number
  extraTasks: number
  coverageRate: number
  summaryConsistent: boolean
  qualityEligible: boolean
  metrics: EvaluationMetrics | null
  perLanguage: Array<EvaluationMetrics & { language: string }>
  issues: ValidationIssue[]
  tasks: ValidationTask[]
  entries: string[]
  logs: string[]
  metadata: SubmissionMetadata | null
}
