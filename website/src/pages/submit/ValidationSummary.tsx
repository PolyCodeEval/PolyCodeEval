import { AlertTriangle, CheckCircle2, Download, XCircle } from 'lucide-react'
import { Badge, NumberValue, Ratio, Stat } from '../../shared/components'
import type { ValidationReport } from './submit.types'

const size = (bytes: number) =>
  bytes < 1_000_000 ? `${(bytes / 1000).toFixed(1)} KB` : `${(bytes / 1_000_000).toFixed(1)} MB`

export function ValidationSummary({
  report,
  onDownload,
}: {
  report: ValidationReport
  onDownload: () => void
}) {
  const errors = report.issues.filter((issue) => issue.severity === 'error')
  const warnings = report.issues.filter((issue) => issue.severity === 'warning')
  return (
    <>
      <div className={`validation-banner ${report.valid ? 'valid' : 'invalid'}`}>
        {report.valid ? <CheckCircle2 size={24} /> : <XCircle size={24} />}
        <div>
          <strong>
            {report.valid ? 'Results pass the browser precheck' : 'Submission requires changes'}
          </strong>
          <span>
            {report.fileName} · {size(report.archiveBytes)} · {report.fileCount.toLocaleString()}{' '}
            files
          </span>
        </div>
        <button className="button button-quiet" onClick={onDownload}>
          <Download size={15} /> Report
        </button>
      </div>
      <div className="stat-grid compact">
        <Stat
          label="Level"
          value={report.level || '—'}
          note={report.scoringMode || 'Unknown mode'}
          tone="blue"
        />
        <Stat
          label="Submission coverage"
          value={<Ratio value={report.coverageRate} />}
          note={`${report.submittedTasks.toLocaleString()} / ${report.expectedTasks.toLocaleString()} tasks`}
          tone="purple"
        />
        <Stat
          label="Fixed-denominator score"
          value={<NumberValue value={report.metrics?.executionScore ?? null} digits={3} />}
          note={`${report.missingTasks.toLocaleString()} missing tasks scored zero`}
          tone="green"
        />
        <Stat
          label="Summary consistency"
          value={report.summaryConsistent ? 'Verified' : 'Review'}
          note={`${errors.length} errors · ${warnings.length} warnings`}
          tone="orange"
        />
      </div>
      {report.metrics && (
        <div className="metric-preview">
          <div>
            <span>Build success</span>
            <Ratio value={report.metrics.buildSuccessRate} />
          </div>
          <div>
            <span>Full pass</span>
            <Ratio value={report.metrics.fullPassRate} />
          </div>
          <div>
            <span>Test pass if built</span>
            <Ratio value={report.metrics.conditionalTestPassRatio} />
          </div>
          <div>
            <span>Quality eligibility</span>
            <strong>{report.qualityEligible ? 'Eligible' : 'Execution only'}</strong>
          </div>
        </div>
      )}
      {report.perLanguage.length > 0 && (
        <div className="language-preview">
          {report.perLanguage.map((row) => (
            <div key={row.language}>
              <strong>{row.language === 'cpp' ? 'C++' : row.language}</strong>
              <span>
                {row.submitted}/{row.expected} tasks
              </span>
              <Ratio value={row.fullPassRate} />
            </div>
          ))}
        </div>
      )}
      {report.issues.length > 0 && (
        <div className="issue-list">
          {report.issues.map((issue, index) => (
            <div
              key={`${issue.code}-${issue.path}-${index}`}
              className={`issue issue-${issue.severity}`}
            >
              {issue.severity === 'error' ? <XCircle size={16} /> : <AlertTriangle size={16} />}
              <div>
                <strong>{issue.message}</strong>
                <span>{issue.path || issue.code}</span>
              </div>
              <Badge
                tone={issue.severity === 'error' ? 'danger' : 'neutral'}
                value={issue.severity}
              />
            </div>
          ))}
        </div>
      )}
    </>
  )
}
