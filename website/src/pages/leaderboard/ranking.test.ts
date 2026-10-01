import { describe, expect, it } from 'vitest'
import { rankEntries } from './ranking'
import type { LeaderboardEntry } from './leaderboard.types'

const row = (
  configuration: string,
  fullPassRate: number,
  executionScore: number,
  buildSuccessRate: number,
): LeaderboardEntry => ({
  id: configuration,
  configuration,
  level: 'L3',
  language: '',
  method: configuration,
  model: 'model',
  total: 2324,
  fullPassRate,
  executionScore,
  buildSuccessRate,
  conditionalTestPassRatio: null,
  correctness: null,
  faithfulness: null,
  architecture: null,
  health: null,
  overall: null,
  sourceType: 'Maintainer Evaluated',
  submitter: 'PolyCodeEval Maintainers',
  submissionId: '',
  submittedTasks: 2324,
  expectedTasks: 2324,
  coverageRate: 1,
  pullRequestUrl: '',
  mergeCommit: '',
  scoringMode: 'execution',
  qualityEligible: false,
  benchmarkVersion: 'pce-1.0',
  evaluatedAt: null,
})

describe('rankEntries', () => {
  it('orders by full pass, execution, build, then configuration', () => {
    const ranked = rankEntries([
      row('D', 0.4, 0.7, 0.8),
      row('C', 0.5, 0.6, 0.9),
      row('B', 0.5, 0.7, 0.8),
      row('A', 0.5, 0.7, 0.8),
    ])
    expect(ranked.map((item) => item.configuration)).toEqual(['A', 'B', 'C', 'D'])
    expect(ranked.map((item) => item.rank)).toEqual([1, 2, 3, 4])
  })

  it('does not mutate the source records', () => {
    const source = [row('B', 0.4, 0.7, 0.8), row('A', 0.5, 0.7, 0.8)]
    rankEntries(source)
    expect(source.map((item) => item.configuration)).toEqual(['B', 'A'])
  })

  it('orders the quality board by the documented quality dimensions', () => {
    const first = {
      ...row('A', 0.1, 0.1, 0.1),
      overall: 4,
      correctness: 3,
      faithfulness: 5,
      architecture: 4,
      health: 4,
    }
    const second = {
      ...row('B', 1, 1, 1),
      overall: 4,
      correctness: 3,
      faithfulness: 4,
      architecture: 5,
      health: 5,
    }
    expect(rankEntries([second, first], true).map((item) => item.configuration)).toEqual(['A', 'B'])
  })
})
