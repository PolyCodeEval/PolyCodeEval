import { useEffect, useState } from 'react'
import { fetchJson } from '../../shared/lib/benchmark'
import type { LoadState } from '../../shared/types/benchmark'
import type { LeaderboardEntry, LeaderboardSnapshot } from './leaderboard.types'

const languageLabels: Record<string, string> = {
  cpp: 'C++',
  go: 'Go',
  java: 'Java',
  javascript: 'JavaScript',
  python: 'Python',
}

function number(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function optionalNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function normalize(raw: unknown): LeaderboardSnapshot {
  const value = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const rows = Array.isArray(value.records) ? value.records : []
  return {
    benchmarkVersion: String(value.benchmarkVersion ?? ''),
    generatedAt: String(value.generatedAt ?? ''),
    records: rows.flatMap((item) => {
      if (!item || typeof item !== 'object') return []
      const row = item as Record<string, unknown>
      const language = String(row.language ?? '')
      const total = number(row.total ?? row.expectedTasks)
      const submitted = number(row.submittedTasks ?? total)
      const entry: LeaderboardEntry = {
        id: String(row.id ?? row.configuration ?? ''),
        configuration: String(row.configuration ?? row.submissionId ?? ''),
        level: String(row.level ?? ''),
        language: languageLabels[language] ?? language,
        method: String(row.method ?? ''),
        model: String(row.model ?? ''),
        total,
        buildSuccessRate: number(row.buildSuccessRate),
        fullPassRate: number(row.fullPassRate),
        conditionalTestPassRatio: optionalNumber(row.conditionalTestPassRatio),
        executionScore: number(row.executionScore),
        correctness: optionalNumber(row.correctness),
        faithfulness: optionalNumber(row.faithfulness),
        architecture: optionalNumber(row.architecture),
        health: optionalNumber(row.health),
        overall: optionalNumber(row.overall),
        sourceType: String(row.sourceType ?? 'Maintainer Evaluated'),
        submitter: String(row.submitter ?? ''),
        submissionId: String(row.submissionId ?? ''),
        submittedTasks: submitted,
        expectedTasks: number(row.expectedTasks ?? total),
        coverageRate: number(row.coverageRate ?? (total ? submitted / total : 0)),
        pullRequestUrl: String(row.pullRequestUrl ?? ''),
        mergeCommit: String(row.mergeCommit ?? ''),
        scoringMode: String(
          row.scoringMode ?? (String(row.level).match(/^L[01]$/) ? 'full_quality' : 'execution'),
        ),
        qualityEligible: Boolean(row.qualityEligible ?? optionalNumber(row.overall) !== null),
        benchmarkVersion: String(row.benchmarkVersion ?? value.benchmarkVersion ?? ''),
        evaluatedAt: row.evaluatedAt ? String(row.evaluatedAt) : null,
        reviewedAt: row.reviewedAt ? String(row.reviewedAt) : null,
      }
      return [entry]
    }),
  }
}

const empty: LeaderboardSnapshot = { benchmarkVersion: '', generatedAt: '', records: [] }

export function useLeaderboard(): LoadState<LeaderboardSnapshot> {
  const [state, setState] = useState<LoadState<LeaderboardSnapshot>>({
    data: empty,
    loading: true,
    error: null,
  })
  useEffect(() => {
    const controller = new AbortController()
    Promise.allSettled([
      fetchJson('leaderboard/rankings.json', controller.signal),
      fetchJson('community/leaderboard.json', controller.signal),
    ]).then((results) => {
      const snapshots = results.flatMap((result) =>
        result.status === 'fulfilled' ? [normalize(result.value)] : [],
      )
      const records = snapshots.flatMap((snapshot) => snapshot.records)
      const errors = results.flatMap((result) =>
        result.status === 'rejected'
          ? [result.reason instanceof Error ? result.reason.message : String(result.reason)]
          : [],
      )
      setState({
        data: {
          benchmarkVersion: snapshots[0]?.benchmarkVersion ?? 'pce-1.0',
          generatedAt:
            snapshots
              .map((snapshot) => snapshot.generatedAt)
              .filter(Boolean)
              .sort()
              .slice(-1)[0] ?? '',
          records,
        },
        loading: false,
        error: records.length ? null : errors.join('; ') || 'No leaderboard snapshot is available.',
      })
    })
    return () => controller.abort()
  }, [])
  return state
}
