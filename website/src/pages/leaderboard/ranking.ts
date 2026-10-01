import type { LeaderboardEntry, RankedEntry } from './leaderboard.types'

export function rankEntries(rows: LeaderboardEntry[], quality = false): RankedEntry[] {
  return [...rows]
    .sort((left, right) => {
      if (quality) {
        for (const field of [
          'overall',
          'correctness',
          'faithfulness',
          'architecture',
          'health',
        ] as const) {
          const delta = (right[field] ?? -1) - (left[field] ?? -1)
          if (delta) return delta
        }
        return left.configuration.localeCompare(right.configuration)
      }
      return (
        right.fullPassRate - left.fullPassRate ||
        right.executionScore - left.executionScore ||
        right.buildSuccessRate - left.buildSuccessRate ||
        left.configuration.localeCompare(right.configuration)
      )
    })
    .map((row, index) => ({ ...row, rank: index + 1 }))
}
