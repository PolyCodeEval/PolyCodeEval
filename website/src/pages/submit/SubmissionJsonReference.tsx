import { useState } from 'react'
import { Braces, ClipboardList, FileCheck2 } from 'lucide-react'
import type { SubmissionMetadata } from './submit.types'

const fields = [
  ['schemaVersion', 'string', 'Required', 'Submission schema release; must be 2.', 'No'],
  ['benchmarkVersion', 'string', 'Required', 'PolyCodeEval data release; must be pce-1.0.', 'Yes'],
  ['level', 'enum', 'Required', 'One of L0, L1, L2, or L3.', 'Yes'],
  ['submissionName', 'string', 'Required', 'Public leaderboard label.', 'No'],
  ['submitter.github', 'string', 'Required', 'GitHub account opening the pull request.', 'No'],
  ['submitter.affiliation', 'string', 'Optional', 'Public affiliation.', 'No'],
  ['method.name', 'string', 'Required', 'Generation method name.', 'Yes'],
  ['method.version', 'string', 'Required', 'Method version or commit.', 'Yes'],
  ['method.paperUrl / codeUrl', 'URL', 'Optional', 'Public method references.', 'No'],
  ['model.name', 'string', 'Required', 'Model name.', 'Yes'],
  ['model.version', 'string', 'Required', 'Model release or dated version.', 'Yes'],
  ['model.provider', 'string', 'Optional', 'Model provider.', 'No'],
  [
    'evaluation.polycodeevalCommit',
    'Git SHA',
    'Required',
    'Evaluator revision used locally.',
    'Yes',
  ],
  ['evaluation.testMode', 'enum', 'Required', 'both, blackbox, whitebox, or mixed.', 'Yes'],
  [
    'evaluation.scoringMode',
    'enum',
    'Required',
    'execution, correctness_only, or full_quality.',
    'Yes',
  ],
  ['evaluation.command / timestamps', 'string', 'Optional', 'Reproduction details.', 'No'],
  [
    'evaluation.packagedAt / workingTreeDirty',
    'string / boolean',
    'Optional',
    'Packaging time and local repository state recorded by the packaging tool.',
    'No',
  ],
  [
    'evaluation.environment',
    'object',
    'Optional',
    'OS, architecture, Python, and Docker versions.',
    'No',
  ],
  ['notes', 'string', 'Optional', 'Additional public context.', 'No'],
]

export function SubmissionJsonReference({ value }: { value: SubmissionMetadata }) {
  const [tab, setTab] = useState<'example' | 'fields' | 'results'>('example')
  return (
    <section className="json-reference" aria-label="Submission JSON structure">
      <div className="reference-tabs" role="tablist">
        <button className={tab === 'example' ? 'active' : ''} onClick={() => setTab('example')}>
          <Braces size={14} /> Example
        </button>
        <button className={tab === 'fields' ? 'active' : ''} onClick={() => setTab('fields')}>
          <ClipboardList size={14} /> Field Reference
        </button>
        <button className={tab === 'results' ? 'active' : ''} onClick={() => setTab('results')}>
          <FileCheck2 size={14} /> Evaluation Result Fields
        </button>
      </div>
      {tab === 'example' && <pre className="json-preview">{JSON.stringify(value, null, 2)}</pre>}
      {tab === 'fields' && (
        <div className="reference-table-wrap">
          <table className="reference-table">
            <thead>
              <tr>
                <th>Field</th>
                <th>Type</th>
                <th>Use</th>
                <th>Meaning</th>
                <th>Ranking</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((row) => (
                <tr key={row[0]}>
                  {row.map((cell, index) => (
                    <td key={index}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {tab === 'results' && (
        <div className="result-field-reference">
          <div>
            <strong>L0/L1 native task JSON</strong>
            <code>task · passed · build_status · test_details · radar_scores · overall_score</code>
            <p>
              Execution ranking uses build status, full-pass state, task correctness, and the
              conditional test-pass ratio. Faithfulness, architecture, health, and overall are
              included only for full-quality submissions.
            </p>
          </div>
          <div>
            <strong>L2/L3 native task JSON</strong>
            <code>
              task · compile_passed · full_passed · test_pass_ratio · compile_score · test_score ·
              score
            </code>
            <p>
              The validator defines full pass as a successful build with a test-pass ratio of 1.0,
              and checks the 0.5 build component, the 0.5 × test-pass component, and their sum.
              Diagnostic stdout, stderr, duration, and exit status remain available for review and
              do not directly alter ranking scores.
            </p>
          </div>
        </div>
      )}
    </section>
  )
}
