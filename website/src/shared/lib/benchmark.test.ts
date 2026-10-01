import { describe, expect, it } from 'vitest'
import { normalizeTokens } from './benchmark'

describe('normalizeTokens', () => {
  it('uses the paper-facing token total and cost when present', () => {
    const [row] = normalizeTokens({
      records: [
        {
          level: 'L3',
          method: 'HCP',
          model: 'GPT-5.4',
          usage: {
            totalTokens: 260_750_000,
            displayedTotalTokens: 97_090_000,
            displayedCostUsd: 165.4,
          },
        },
      ],
    })

    expect(row.total).toBe(97_090_000)
    expect(row.cost).toBe(165.4)
  })
})
