import { describe, expect, it } from 'vitest'
import { emptySubmission, parseSubmissionMetadata } from './submission-schema'

describe('parseSubmissionMetadata', () => {
  it('accepts complete schema-v2 metadata', () => {
    const value = emptySubmission()
    value.submissionName = 'Example run'
    value.submitter.github = 'example-user'
    value.method.name = 'Example method'
    value.method.version = 'abc123'
    value.model.name = 'Example model'
    value.model.version = '2026-09-01'
    value.evaluation.polycodeevalCommit = '1234567'
    expect(parseSubmissionMetadata(value).issues).toEqual([])
  })

  it('requires the submitter, versions, and evaluator commit', () => {
    const value = emptySubmission()
    value.submissionName = 'Example run'
    value.method.name = 'Example method'
    value.model.name = 'Example model'
    const codes = parseSubmissionMetadata(value).issues.map((issue) => issue.code)
    expect(codes).toEqual(
      expect.arrayContaining([
        'metadata.submitter.github',
        'metadata.method.version',
        'metadata.model.version',
        'metadata.evaluation.polycodeevalCommit',
      ]),
    )
  })

  it('enforces level-specific scoring modes', () => {
    const value = emptySubmission()
    value.level = 'L2'
    value.evaluation.scoringMode = 'full_quality'
    const result = parseSubmissionMetadata(value)
    expect(result.issues.map((issue) => issue.code)).toContain('metadata.evaluation.scoringMode')
  })
})
