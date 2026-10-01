export interface OutcomeAggregate {
  level: string
  label: string
  buildRate: number
  fullRate: number
  testRate: number
  scope: string
}

export interface CommunitySummary {
  submissionCount: number
  generatedAt: string
}
