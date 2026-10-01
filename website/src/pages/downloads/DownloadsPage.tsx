import { BookOpenText, Database, FileJson2, Github, GitPullRequest } from 'lucide-react'
import { PageHeader, Panel, Stat } from '../../shared/components'
import { DatasetDownloads } from './DatasetDownloads'
import { EvaluationCommands } from './EvaluationCommands'
import { ResultSubmissionKit } from './ResultSubmissionKit'
import { taskCounts } from './downloads.data'
import './downloads.css'

const allCommand = 'python docker/sync_datasets.py pull --all'
const packageTree = [
  'submission.json',
  'evaluation/',
  '  summary.json',
  '  <language>/<project>/<task>.json',
  'logs/                         # optional',
].join('\n')

export function DownloadsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Benchmark resources"
        title="Downloads & Result Submission"
        description="Retrieve the benchmark, evaluate generated artifacts locally, and package the evaluator's native JSON results for a community pull request."
        actions={
          <a className="button button-primary" href="#/submit">
            Validate evaluated results
          </a>
        }
      />
      <div className="stat-grid compact">
        <Stat label="Release" value="pce-1.0" note="Submission schema v2" tone="blue" />
        <Stat label="Repositories" value="58" note="Five languages" tone="purple" />
        <Stat
          label="Tasks"
          value={Object.values(taskCounts)
            .reduce((sum, count) => sum + count, 0)
            .toLocaleString()}
          note="L0–L3 combined"
          tone="green"
        />
        <Stat label="Submission" value="GitHub PR" note="Self-evaluated results" tone="orange" />
      </div>
      <Panel
        title="Dataset images"
        subtitle="Pull one language or synchronize the complete Oracle repository collection."
      >
        <div className="all-download">
          <Database size={18} />
          <div>
            <strong>Complete dataset</strong>
            <code>{allCommand}</code>
          </div>
        </div>
        <DatasetDownloads />
      </Panel>
      <Panel
        title="Run the official evaluator"
        subtitle="Point the precomputed solver at locally generated artifacts and preserve the resulting output directory without modification."
      >
        <EvaluationCommands />
        <p className="command-note">
          <code>&lt;generated-output&gt;</code> contains model-generated artifacts.{' '}
          <code>&lt;evaluation-output&gt;</code> receives <code>summary.json</code> and native
          per-task JSON results.
        </p>
      </Panel>
      <div className="downloads-two-column">
        <Panel
          title="Result Submission Kit"
          subtitle="One metadata file accompanies the evaluator's native output."
        >
          <ResultSubmissionKit />
        </Panel>
        <Panel
          title="References"
          subtitle="Human-readable and machine-readable submission contracts."
        >
          <div className="resource-links">
            <a href={`${import.meta.env.BASE_URL}data/common/manifest.json`} download>
              <FileJson2 size={18} />
              <div>
                <strong>Benchmark manifest</strong>
                <span>Canonical task IDs and fixed denominators</span>
              </div>
            </a>
            <a
              href="https://github.com/PolyCodeEval/PolyCodeEval/blob/main/docs/leaderboard/submission-json-reference.md"
              target="_blank"
              rel="noreferrer"
            >
              <BookOpenText size={18} />
              <div>
                <strong>Submission JSON reference</strong>
                <span>Fields, types, accepted values, and examples</span>
              </div>
            </a>
            <a
              href="https://github.com/PolyCodeEval/PolyCodeEval/blob/main/docs/leaderboard/native-result-format.md"
              target="_blank"
              rel="noreferrer"
            >
              <BookOpenText size={18} />
              <div>
                <strong>Native result format</strong>
                <span>L0/L1 and L2/L3 evaluator fields</span>
              </div>
            </a>
            <a
              href="https://github.com/PolyCodeEval/PolyCodeEval/blob/main/docs/leaderboard/submitting-results.md"
              target="_blank"
              rel="noreferrer"
            >
              <GitPullRequest size={18} />
              <div>
                <strong>Pull request guide</strong>
                <span>Package, validate, and submit community results</span>
              </div>
            </a>
            <a href="https://github.com/PolyCodeEval/PolyCodeEval" target="_blank" rel="noreferrer">
              <Github size={18} />
              <div>
                <strong>Source repository</strong>
                <span>Generation, evaluation, and submission tools</span>
              </div>
            </a>
          </div>
        </Panel>
      </div>
      <Panel
        title="Native result package"
        subtitle="Keep the evaluator output unchanged and add submission.json at the archive root."
      >
        <div className="native-contract">
          <pre>{packageTree}</pre>
          <div>
            <strong>Required</strong>
            <p>One schema-v2 submission.json and the evaluator's summary plus task JSON files.</p>
            <strong>Optional</strong>
            <p>UTF-8 .log, .txt, .json, or .jsonl files, up to 5 MB each and 20 MB total.</p>
            <strong>Ranking policy</strong>
            <p>
              Partial submissions are accepted. Missing tasks receive zero under the fixed level
              denominator.
            </p>
          </div>
        </div>
      </Panel>
    </>
  )
}
