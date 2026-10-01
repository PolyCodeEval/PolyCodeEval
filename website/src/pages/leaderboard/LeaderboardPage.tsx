import { useMemo } from 'react'
import { Award, FlaskConical, Layers3, Users } from 'lucide-react'
import { ErrorState, Loading, PageHeader, Panel, Stat } from '../../shared/components'
import { useQueryFilters } from '../../shared/hooks/query'
import { LeaderboardCharts } from './LeaderboardCharts'
import { LeaderboardFilters, type LeaderboardFilterState } from './LeaderboardFilters'
import { LeaderboardTable } from './LeaderboardTable'
import { useLeaderboard } from './leaderboard.data'
import { rankEntries } from './ranking'
import './leaderboard.css'

const defaults: LeaderboardFilterState = {
  level: 'L3',
  language: '',
  method: '',
  model: '',
  source: '',
  submitter: '',
  board: 'Execution',
  search: '',
}

export function LeaderboardPage() {
  const source = useLeaderboard()
  const { filters, update, reset } = useQueryFilters(defaults)
  const qualityBoard =
    filters.board === 'Full Quality' && (filters.level === 'L0' || filters.level === 'L1')
  const levelRows = source.data.records.filter(
    (row) => row.level === filters.level && (!qualityBoard || row.qualityEligible),
  )
  const visible = useMemo(
    () =>
      rankEntries(
        levelRows.filter(
          (row) =>
            row.language === filters.language &&
            (!filters.method || row.method === filters.method) &&
            (!filters.model || row.model === filters.model) &&
            (!filters.source || row.sourceType === filters.source) &&
            (!filters.submitter || row.submitter === filters.submitter) &&
            (!filters.search ||
              `${row.method} ${row.model} ${row.configuration}`
                .toLowerCase()
                .includes(filters.search.toLowerCase())),
        ),
        qualityBoard,
      ),
    [levelRows, filters, qualityBoard],
  )
  const overall = levelRows.filter((row) => !row.language)
  const best = rankEntries(overall, qualityBoard)[0]
  const communityCount = source.data.records.filter(
    (row) => row.sourceType === 'Community Self-Evaluated' && !row.language,
  ).length

  return (
    <>
      <PageHeader
        eyebrow="Community benchmark"
        title="PolyCodeEval Leaderboard"
        description="Maintainer baselines and community self-evaluated submissions ranked independently at each generation level."
        actions={
          <a className="button button-primary" href="#/submit">
            Validate a submission
          </a>
        }
      />
      {source.loading ? (
        <Loading label="Loading leaderboard" />
      ) : source.error ? (
        <ErrorState message={source.error} />
      ) : (
        <>
          <div className="stat-grid compact">
            <Stat
              label="Benchmark release"
              value={source.data.benchmarkVersion || 'pce-1.0'}
              note="Static public snapshot"
              tone="blue"
            />
            <Stat
              label={`${filters.level} configurations`}
              value={overall.length}
              note={`${communityCount} community submissions`}
              tone="purple"
            />
            <Stat
              label="Leading method"
              value={best?.method ?? '—'}
              note={best?.model ?? ''}
              tone="green"
            />
            <Stat
              label={qualityBoard ? 'Quality score' : 'Full-pass rate'}
              value={
                best
                  ? qualityBoard
                    ? (best.overall ?? 0).toFixed(2)
                    : `${(best.fullPassRate * 100).toFixed(1)}%`
                  : '—'
              }
              note="Current overall leader"
              tone="orange"
            />
          </div>
          <LeaderboardFilters rows={levelRows} filters={filters} update={update} reset={reset} />
          <LeaderboardCharts rows={rankEntries(levelRows, qualityBoard)} level={filters.level} />
          <Panel
            title={`${filters.level} ranking`}
            subtitle="Ranks are recomputed over the selected scope. Select a row to inspect its task-level results; quality scores appear when preserved."
            action={
              <span className="leaderboard-note">
                <Award size={14} /> {visible.length} configurations
              </span>
            }
          >
            <LeaderboardTable rows={visible} level={filters.level} />
          </Panel>
          <div className="leaderboard-methodology">
            <span>
              <FlaskConical size={15} /> Execution-based evaluation
            </span>
            <span>
              <Layers3 size={15} /> Separate L0–L3 rankings
            </span>
            <span>
              <Users size={15} /> Self-evaluated, maintainer-reviewed community results
            </span>
          </div>
        </>
      )}
    </>
  )
}
