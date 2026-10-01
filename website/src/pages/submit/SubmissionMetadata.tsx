import { useRef, useState } from 'react'
import { Copy, Download, FileJson2 } from 'lucide-react'
import { parseSubmissionMetadata, scoringModesFor } from './submission-schema'
import type { EvaluationLevel, SubmissionMetadata as Metadata } from './submit.types'

interface Props {
  value: Metadata
  onChange: (value: Metadata) => void
  onDownload: () => void
}

export function SubmissionMetadata({ value, onChange, onDownload }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const [importMessage, setImportMessage] = useState('')
  const [copied, setCopied] = useState(false)
  const importMetadata = async (file?: File) => {
    if (!file) return
    try {
      const parsed = parseSubmissionMetadata(JSON.parse(await file.text()))
      if (!parsed.metadata || parsed.issues.length) {
        setImportMessage(parsed.issues.map((issue) => issue.message).join(' '))
        return
      }
      onChange(parsed.metadata)
      setImportMessage(`Imported ${file.name}`)
    } catch (error) {
      setImportMessage(
        `Unable to import JSON: ${error instanceof Error ? error.message : String(error)}`,
      )
    }
  }
  const changeLevel = (level: EvaluationLevel) =>
    onChange({
      ...value,
      level,
      evaluation: {
        ...value.evaluation,
        scoringMode: level === 'L0' || level === 'L1' ? 'correctness_only' : 'execution',
      },
    })
  const submitter = (key: keyof Metadata['submitter'], next: string) =>
    onChange({ ...value, submitter: { ...value.submitter, [key]: next } })
  const method = (key: keyof Metadata['method'], next: string) =>
    onChange({ ...value, method: { ...value.method, [key]: next } })
  const model = (key: keyof Metadata['model'], next: string) =>
    onChange({ ...value, model: { ...value.model, [key]: next } })
  const evaluation = (key: keyof Metadata['evaluation'], next: string) =>
    onChange({ ...value, evaluation: { ...value.evaluation, [key]: next } })
  const environment = (key: keyof Metadata['evaluation']['environment'], next: string) =>
    onChange({
      ...value,
      evaluation: {
        ...value.evaluation,
        environment: { ...value.evaluation.environment, [key]: next },
      },
    })
  const copy = async () => {
    await navigator.clipboard.writeText(JSON.stringify(value, null, 2))
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div className="submission-form">
      <div className="form-section-title wide">Identity and benchmark</div>
      <label className="wide">
        <span>Submission name</span>
        <input
          value={value.submissionName}
          onChange={(event) => onChange({ ...value, submissionName: event.target.value })}
          placeholder="Method X with Model Y"
        />
        <small>A public label for this leaderboard entry.</small>
      </label>
      <label>
        <span>Level</span>
        <select
          value={value.level}
          onChange={(event) => changeLevel(event.target.value as EvaluationLevel)}
        >
          {['L0', 'L1', 'L2', 'L3'].map((level) => (
            <option key={level}>{level}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Scoring mode</span>
        <select
          value={value.evaluation.scoringMode}
          onChange={(event) => evaluation('scoringMode', event.target.value)}
        >
          {scoringModesFor(value.level).map((mode) => (
            <option key={mode} value={mode}>
              {mode.replace('_', ' ')}
            </option>
          ))}
        </select>
        <small>Controls leaderboard eligibility for L0/L1 quality scores.</small>
      </label>
      <label>
        <span>GitHub user</span>
        <input
          value={value.submitter.github}
          onChange={(event) => submitter('github', event.target.value)}
          placeholder="example-user"
        />
      </label>
      <label className="wide">
        <span>Affiliation</span>
        <input
          value={value.submitter.affiliation}
          onChange={(event) => submitter('affiliation', event.target.value)}
          placeholder="Optional"
        />
      </label>

      <div className="form-section-title wide">Method and model</div>
      <label>
        <span>Method</span>
        <input value={value.method.name} onChange={(event) => method('name', event.target.value)} />
      </label>
      <label>
        <span>Method version</span>
        <input
          value={value.method.version}
          onChange={(event) => method('version', event.target.value)}
        />
      </label>
      <label>
        <span>Paper URL</span>
        <input
          value={value.method.paperUrl}
          onChange={(event) => method('paperUrl', event.target.value)}
          placeholder="Optional"
        />
      </label>
      <label>
        <span>Model</span>
        <input value={value.model.name} onChange={(event) => model('name', event.target.value)} />
      </label>
      <label>
        <span>Model version</span>
        <input
          value={value.model.version}
          onChange={(event) => model('version', event.target.value)}
        />
      </label>
      <label>
        <span>Provider</span>
        <input
          value={value.model.provider}
          onChange={(event) => model('provider', event.target.value)}
          placeholder="Optional"
        />
      </label>
      <label className="wide">
        <span>Code URL</span>
        <input
          value={value.method.codeUrl}
          onChange={(event) => method('codeUrl', event.target.value)}
          placeholder="Optional"
        />
      </label>

      <div className="form-section-title wide">Evaluation</div>
      <label>
        <span>PolyCodeEval commit</span>
        <input
          className="mono"
          value={value.evaluation.polycodeevalCommit}
          onChange={(event) => evaluation('polycodeevalCommit', event.target.value)}
          placeholder="7–40 character Git SHA"
        />
      </label>
      <label>
        <span>Test mode</span>
        <select
          value={value.evaluation.testMode}
          onChange={(event) => evaluation('testMode', event.target.value)}
        >
          <option value="both">both</option>
          <option value="blackbox">blackbox</option>
          <option value="whitebox">whitebox</option>
          <option value="mixed">mixed</option>
        </select>
      </label>
      <label>
        <span>Command</span>
        <input
          value={value.evaluation.command}
          onChange={(event) => evaluation('command', event.target.value)}
          placeholder="Optional"
        />
      </label>
      <label>
        <span>Started at</span>
        <input
          type="datetime-local"
          value={value.evaluation.startedAt}
          onChange={(event) => evaluation('startedAt', event.target.value)}
        />
      </label>
      <label>
        <span>Finished at</span>
        <input
          type="datetime-local"
          value={value.evaluation.finishedAt}
          onChange={(event) => evaluation('finishedAt', event.target.value)}
        />
      </label>
      <label>
        <span>Operating system</span>
        <input
          value={value.evaluation.environment.os}
          onChange={(event) => environment('os', event.target.value)}
          placeholder="Optional"
        />
      </label>
      <label>
        <span>Architecture</span>
        <input
          value={value.evaluation.environment.architecture}
          onChange={(event) => environment('architecture', event.target.value)}
          placeholder="Optional"
        />
      </label>
      <label>
        <span>Python</span>
        <input
          value={value.evaluation.environment.python}
          onChange={(event) => environment('python', event.target.value)}
          placeholder="Optional"
        />
      </label>
      <label>
        <span>Docker</span>
        <input
          value={value.evaluation.environment.docker}
          onChange={(event) => environment('docker', event.target.value)}
          placeholder="Optional"
        />
      </label>
      <label className="wide">
        <span>Notes</span>
        <textarea
          value={value.notes}
          onChange={(event) => onChange({ ...value, notes: event.target.value })}
          rows={3}
          placeholder="Optional evaluation details"
        />
      </label>
      <div className="form-actions wide">
        <input
          ref={input}
          className="metadata-file-input"
          type="file"
          accept="application/json,.json"
          onChange={(event) => importMetadata(event.target.files?.[0])}
        />
        {importMessage && <span className="metadata-import-status">{importMessage}</span>}
        <button className="button button-quiet" onClick={() => input.current?.click()}>
          <FileJson2 size={15} /> Import JSON
        </button>
        <button className="button button-quiet" onClick={copy}>
          <Copy size={15} /> {copied ? 'Copied' : 'Copy JSON'}
        </button>
        <button className="button button-quiet" onClick={onDownload}>
          <Download size={15} /> Download JSON
        </button>
      </div>
    </div>
  )
}
