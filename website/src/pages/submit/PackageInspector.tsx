import { useRef, useState } from 'react'
import { FileArchive, LoaderCircle, Upload } from 'lucide-react'
import { validatePackage } from './package-validator'
import type { ReleaseManifest, ValidationReport } from './submit.types'

export function PackageInspector({
  release,
  onValidated,
}: {
  release: ReleaseManifest
  onValidated: (report: ValidationReport) => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [fileName, setFileName] = useState('')
  const inspect = async (file?: File) => {
    if (!file) return
    setBusy(true)
    setFileName(file.name)
    try {
      onValidated(await validatePackage(file, release))
    } catch (error) {
      onValidated({
        valid: false,
        fileName: file.name,
        archiveBytes: file.size,
        fileCount: 0,
        benchmarkVersion: '',
        level: '',
        scoringMode: '',
        expectedTasks: 0,
        submittedTasks: 0,
        missingTasks: 0,
        extraTasks: 0,
        coverageRate: 0,
        summaryConsistent: false,
        qualityEligible: false,
        metrics: null,
        perLanguage: [],
        issues: [
          {
            severity: 'error',
            code: 'archive.read',
            message: error instanceof Error ? error.message : String(error),
          },
        ],
        tasks: [],
        entries: [],
        logs: [],
        metadata: null,
      })
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="package-inspector">
      <input
        ref={input}
        type="file"
        accept=".zip,application/zip"
        onChange={(event) => inspect(event.target.files?.[0])}
      />
      <button className="package-drop" onClick={() => input.current?.click()} disabled={busy}>
        {busy ? (
          <LoaderCircle className="spin" size={28} />
        ) : fileName ? (
          <FileArchive size={28} />
        ) : (
          <Upload size={28} />
        )}
        <strong>{busy ? 'Inspecting package' : fileName || 'Choose a submission ZIP'}</strong>
        <span>Expected contents: submission.json, evaluation/, and optional logs/.</span>
      </button>
    </div>
  )
}
