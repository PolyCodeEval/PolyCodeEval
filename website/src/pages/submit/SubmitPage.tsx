import { useEffect, useMemo, useState } from 'react'
import { FileCheck2, GitPullRequest, LockKeyhole } from 'lucide-react'
import { ErrorState, Loading, PageHeader, Panel } from '../../shared/components'
import { useJson } from '../../shared/hooks/data'
import { ArchivePreview } from './ArchivePreview'
import { PackageInspector } from './PackageInspector'
import { SubmissionJsonReference } from './SubmissionJsonReference'
import { SubmissionMetadata } from './SubmissionMetadata'
import { ValidationSummary } from './ValidationSummary'
import { ValidationTaskTable } from './ValidationTaskTable'
import { emptySubmission } from './submission-schema'
import type {
  ReleaseManifest,
  SubmissionMetadata as Metadata,
  ValidationReport,
} from './submit.types'
import './submit.css'

const emptyRelease: ReleaseManifest = {
  benchmarkVersion: '',
  taskCounts: { L0: 0, L1: 0, L2: 0, L3: 0 },
  tasks: { L0: [], L1: [], L2: [], L3: [] },
}
const normalizeRelease = (raw: unknown): ReleaseManifest => raw as ReleaseManifest

function downloadJson(name: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2) + '\n'], { type: 'application/json' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = name
  link.click()
  URL.revokeObjectURL(link.href)
}

const slug = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 48) || 'submission'

export function SubmitPage() {
  const release = useJson('common/manifest.json', normalizeRelease, emptyRelease)
  const [metadata, setMetadata] = useState<Metadata>(emptySubmission())
  const [report, setReport] = useState<ValidationReport | null>(null)
  useEffect(() => {
    if (release.data.benchmarkVersion)
      setMetadata((current) => ({ ...current, benchmarkVersion: release.data.benchmarkVersion }))
  }, [release.data.benchmarkVersion])
  const validated = (next: ValidationReport) => {
    setReport(next)
    if (next.metadata) setMetadata(next.metadata)
  }
  const submissionId = useMemo(() => slug(metadata.submissionName), [metadata.submissionName])
  const target = `community-results/pce-1.0/${metadata.level}/${metadata.submitter.github || '<github-user>'}/${submissionId}/`
  const branch = `submission/${metadata.level.toLowerCase()}-${submissionId}`

  return (
    <>
      <PageHeader
        eyebrow="Community submissions"
        title="Submit Evaluated Results"
        description="Run PolyCodeEval locally, package its native evaluation output, verify the result archive in this browser, and submit it through a GitHub pull request."
        actions={
          <a className="button button-primary" href="#/downloads">
            Evaluation resources
          </a>
        }
      />
      <div className="local-validation-note">
        <LockKeyhole size={18} />
        <div>
          <strong>Private browser precheck</strong>
          <span>
            The selected archive remains on this device. The page reads JSON and text logs without
            executing any submitted content.
          </span>
        </div>
      </div>
      {release.loading ? (
        <Loading label="Loading benchmark manifest" />
      ) : release.error ? (
        <ErrorState message={release.error} />
      ) : (
        <div className="submit-layout">
          <div className="submit-main">
            <Panel
              title="1. Describe the submission"
              subtitle="submission.json is the only additional JSON required beside the evaluator's native output."
            >
              <SubmissionMetadata
                value={metadata}
                onChange={setMetadata}
                onDownload={() => downloadJson('submission.json', metadata)}
              />
            </Panel>
            <Panel
              title="JSON Structure"
              subtitle="The example follows the selected level and scoring mode; the reference defines every accepted field."
            >
              <SubmissionJsonReference value={metadata} />
            </Panel>
            <Panel
              title="2. Inspect evaluation results"
              subtitle="Choose a ZIP containing submission.json, evaluation/summary.json, native per-task JSON files, and optional logs/."
            >
              <PackageInspector release={release.data} onValidated={validated} />
            </Panel>
            {report && (
              <Panel
                title="3. Validate and preview"
                subtitle="Metrics are recomputed from task JSON using the complete benchmark task count as the denominator."
              >
                <ValidationSummary
                  report={report}
                  onDownload={() =>
                    downloadJson(
                      `${report.fileName.replace(/\.zip$/i, '')}-validation-report.json`,
                      report,
                    )
                  }
                />
                <ArchivePreview entries={report.entries} />
                {report.tasks.length > 0 && <ValidationTaskTable rows={report.tasks} />}
              </Panel>
            )}
            <Panel
              title="4. Submit through GitHub"
              subtitle="Open one pull request that adds one immutable community result directory."
            >
              <div className="pr-guide">
                <div className="pr-target">
                  <GitPullRequest size={20} />
                  <div>
                    <strong>Target directory</strong>
                    <code>{target}</code>
                  </div>
                </div>
                <ol>
                  <li>
                    Fork the PolyCodeEval repository and create a branch named <code>{branch}</code>
                    .
                  </li>
                  <li>
                    Place <code>submission.json</code>, <code>evaluation/</code>, and optional{' '}
                    <code>logs/</code> in the target directory.
                  </li>
                  <li>
                    Commit only this new submission directory and push the branch to your fork.
                  </li>
                  <li>
                    Open a pull request titled{' '}
                    <code>
                      [Results] {metadata.level}:{' '}
                      {metadata.submissionName || 'Method X with Model Y'}
                    </code>
                    .
                  </li>
                  <li>
                    Wait for automatic validation, then address maintainer review. Accepted entries
                    are marked <strong>Self-evaluated</strong>.
                  </li>
                </ol>
                <a
                  className="button button-primary"
                  href="https://github.com/PolyCodeEval/PolyCodeEval/compare"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open pull request
                </a>
              </div>
            </Panel>
          </div>
          <aside className="submit-guide">
            <Panel title="Submission contents">
              <ol className="compact-steps">
                <li>
                  <span>1</span>
                  <div>
                    <strong>Native results</strong>
                    <p>Keep summary.json and every per-task JSON unchanged.</p>
                  </div>
                </li>
                <li>
                  <span>2</span>
                  <div>
                    <strong>One metadata file</strong>
                    <p>
                      Add submission.json for method, model, evaluator, and submitter information.
                    </p>
                  </div>
                </li>
                <li>
                  <span>3</span>
                  <div>
                    <strong>Optional logs</strong>
                    <p>Use UTF-8 .log, .txt, .json, or .jsonl files without credentials.</p>
                  </div>
                </li>
                <li>
                  <span>4</span>
                  <div>
                    <strong>Partial results allowed</strong>
                    <p>Missing tasks receive zero in the fixed-denominator ranking.</p>
                  </div>
                </li>
              </ol>
            </Panel>
            <Panel title="Release">
              <div className="release-summary">
                <FileCheck2 size={20} />
                <div>
                  <strong>{release.data.benchmarkVersion}</strong>
                  <span>
                    {Object.values(release.data.taskCounts)
                      .reduce((sum, count) => sum + count, 0)
                      .toLocaleString()}{' '}
                    tasks across L0–L3
                  </span>
                </div>
              </div>
            </Panel>
          </aside>
        </div>
      )}
    </>
  )
}
