import {
  CheckCircle2,
  Database,
  Download,
  ExternalLink,
  Layers3,
  Sigma,
  TerminalSquare,
  Trophy,
  Upload,
} from 'lucide-react'
import { Loading, PageHeader, Panel, Stat } from '../../shared/components'
import { OverviewCharts } from './OverviewCharts'
import { useOverviewData } from './overview.data'
import './overview.css'

export function OverviewPage() {
  const { manifest, aggregates, community } = useOverviewData()
  if (manifest.loading) return <Loading label="Loading benchmark summary" />
  const counts = manifest.data.taskCounts
  return (
    <>
      <PageHeader
        eyebrow="Benchmark dashboard"
        title="PolyCodeEval at a glance"
        description="An interactive, execution-grounded view of multi-granularity code generation across repositories, languages, methods, and models."
        actions={
          <>
            <a className="button button-quiet" href="#/downloads">
              <Download size={16} />
              Get the dataset
            </a>
            <a className="button button-primary" href="#/leaderboard">
              <Trophy size={16} />
              View leaderboard
            </a>
          </>
        }
      />
      <div className="stat-grid">
        <Stat
          label="Oracle repositories"
          value={manifest.data.repositories}
          note="Across five languages"
          tone="blue"
        />
        {['L0', 'L1', 'L2', 'L3'].map((level, i) => (
          <Stat
            key={level}
            label={`${level} tasks`}
            value={(counts[level] ?? 0).toLocaleString()}
            note={
              [
                'Project generation',
                'Skeleton-conditioned project',
                'File-level completion',
                'Function-level completion',
              ][i]
            }
            tone={['ink', 'purple', 'green', 'orange'][i]}
          />
        ))}
      </div>
      <div className="overview-grid">
        <OverviewCharts
          rows={aggregates.data}
          loading={aggregates.loading}
          error={aggregates.error}
        />
        <Panel
          title="Evaluation pipeline"
          subtitle="From executable repositories to auditable task-level outcomes"
        >
          <ol className="pipeline">
            {[
              'Repository preparation',
              'L0–L3 task construction',
              'Prompt construction',
              'Oracle validation',
              'Model generation',
              'Execution evaluation',
              'Aggregation and analysis',
            ].map((x, i) => (
              <li key={x}>
                <span>{i + 1}</span>
                <div>{x}</div>
              </li>
            ))}
          </ol>
        </Panel>
      </div>
      <Panel
        title="Explore the evidence"
        subtitle="Each view links aggregate findings to task-level records."
      >
        <div className="link-grid">
          {[
            [
              'Dataset Explorer',
              'Repository composition, LOC, difficulty, coverage, and task density',
              '#/dataset',
              Layers3,
            ],
            [
              'Results Explorer',
              'Filter execution outcomes by level, method, model, language, and project',
              '#/results',
              CheckCircle2,
            ],
            [
              'Statistical Analysis',
              'Inspect paired comparisons, state transitions, and significance tests',
              '#/statistics',
              Sigma,
            ],
            [
              'Prompts & Reproduction',
              'Review prompt templates, output constraints, and reproduction commands',
              '#/prompts',
              TerminalSquare,
            ],
          ].map(([title, desc, href, Icon]) => (
            <a className="link-tile" href={String(href)} key={String(title)}>
              <Icon size={20} />
              <strong>{String(title)}</strong>
              <span>{String(desc)}</span>
              <ExternalLink size={15} />
            </a>
          ))}
        </div>
      </Panel>
      <Panel
        title="Contribute evaluated results"
        subtitle={`Download → Generate → Evaluate → Validate → Submit PR · ${community.data.submissionCount} accepted community submissions`}
      >
        <div className="link-grid community-links">
          {[
            [
              'Leaderboard',
              'Compare maintainer baselines and reviewed community submissions at each level.',
              '#/leaderboard',
              Trophy,
            ],
            [
              'Downloads',
              'Retrieve datasets, evaluator commands, schema, and the result submission kit.',
              '#/downloads',
              Download,
            ],
            [
              'Submit Results',
              'Inspect native evaluation JSON locally and prepare a GitHub pull request.',
              '#/submit',
              Upload,
            ],
          ].map(([title, desc, href, Icon]) => (
            <a className="link-tile" href={String(href)} key={String(title)}>
              <Icon size={20} />
              <strong>{String(title)}</strong>
              <span>{String(desc)}</span>
              <ExternalLink size={15} />
            </a>
          ))}
        </div>
      </Panel>
      <footer className="data-note">
        Data version: {manifest.data.version}
        {manifest.data.generatedAt
          ? ` · Generated ${new Date(manifest.data.generatedAt).toLocaleString()}`
          : ''}
      </footer>
    </>
  )
}
