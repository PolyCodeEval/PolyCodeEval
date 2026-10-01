import type {
  EvaluationLevel,
  ScoringMode,
  SubmissionMetadata,
  ValidationIssue,
} from './submit.types'

export const levels: EvaluationLevel[] = ['L0', 'L1', 'L2', 'L3']
export const testModes = ['both', 'blackbox', 'whitebox', 'mixed'] as const
export const scoringModes: ScoringMode[] = ['correctness_only', 'full_quality', 'execution']

export const scoringModesFor = (level: EvaluationLevel): ScoringMode[] =>
  level === 'L0' || level === 'L1' ? ['correctness_only', 'full_quality'] : ['execution']

export const emptySubmission = (benchmarkVersion = 'pce-1.0'): SubmissionMetadata => ({
  schemaVersion: '2',
  benchmarkVersion,
  level: 'L3',
  submissionName: '',
  submitter: { github: '', affiliation: '' },
  method: { name: '', version: '', paperUrl: '', codeUrl: '' },
  model: { name: '', version: '', provider: '' },
  evaluation: {
    polycodeevalCommit: '',
    testMode: 'both',
    scoringMode: 'execution',
    command: '',
    startedAt: '',
    finishedAt: '',
    environment: { os: '', architecture: '', python: '', docker: '' },
  },
  notes: '',
})

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)

const allowed = {
  top: new Set([
    'schemaVersion',
    'benchmarkVersion',
    'level',
    'submissionName',
    'submitter',
    'method',
    'model',
    'evaluation',
    'notes',
  ]),
  submitter: new Set(['github', 'affiliation']),
  method: new Set(['name', 'version', 'paperUrl', 'codeUrl']),
  model: new Set(['name', 'version', 'provider']),
  evaluation: new Set([
    'polycodeevalCommit',
    'testMode',
    'scoringMode',
    'command',
    'startedAt',
    'finishedAt',
    'packagedAt',
    'workingTreeDirty',
    'environment',
  ]),
  environment: new Set(['os', 'architecture', 'python', 'docker']),
}

function unknownFields(
  value: Record<string, unknown>,
  accepted: Set<string>,
  prefix: string,
  issues: ValidationIssue[],
) {
  Object.keys(value)
    .filter((key) => !accepted.has(key))
    .forEach((key) =>
      issues.push({
        severity: 'error',
        code: `${prefix}.additionalProperty`,
        message: `Unknown field: ${prefix.replace('metadata.', '')}.${key}.`,
      }),
    )
}

function requiredText(name: string, value: unknown, issues: ValidationIssue[], pattern?: RegExp) {
  const normalized = String(value ?? '').trim()
  if (!normalized)
    issues.push({ severity: 'error', code: `metadata.${name}`, message: `${name} is required.` })
  else if (pattern && !pattern.test(normalized))
    issues.push({
      severity: 'error',
      code: `metadata.${name}`,
      message: `${name} has an invalid format.`,
    })
}

function optionalText(name: string, value: unknown, issues: ValidationIssue[], url = false) {
  if (value === undefined) return
  if (typeof value !== 'string') {
    issues.push({
      severity: 'error',
      code: `metadata.${name}`,
      message: `${name} must be a string.`,
    })
    return
  }
  if (url && value && !/^https?:\/\//.test(value))
    issues.push({
      severity: 'error',
      code: `metadata.${name}`,
      message: `${name} must be an HTTP(S) URL.`,
    })
}

export function parseSubmissionMetadata(value: unknown): {
  metadata: SubmissionMetadata | null
  issues: ValidationIssue[]
} {
  const issues: ValidationIssue[] = []
  if (!isRecord(value))
    return {
      metadata: null,
      issues: [
        {
          severity: 'error',
          code: 'metadata.type',
          message: 'submission.json must contain a JSON object.',
        },
      ],
    }

  const submitter = isRecord(value.submitter) ? value.submitter : {}
  const method = isRecord(value.method) ? value.method : {}
  const model = isRecord(value.model) ? value.model : {}
  const evaluation = isRecord(value.evaluation) ? value.evaluation : {}
  const environment = isRecord(evaluation.environment) ? evaluation.environment : {}
  const level = String(value.level ?? '')
  const testMode = String(evaluation.testMode ?? '')
  const scoringMode = String(evaluation.scoringMode ?? '')

  unknownFields(value, allowed.top, 'metadata', issues)
  unknownFields(submitter, allowed.submitter, 'metadata.submitter', issues)
  unknownFields(method, allowed.method, 'metadata.method', issues)
  unknownFields(model, allowed.model, 'metadata.model', issues)
  unknownFields(evaluation, allowed.evaluation, 'metadata.evaluation', issues)
  unknownFields(environment, allowed.environment, 'metadata.evaluation.environment', issues)

  if (value.schemaVersion !== '2')
    issues.push({
      severity: 'error',
      code: 'metadata.schemaVersion',
      message: 'schemaVersion must be "2".',
    })
  if (value.benchmarkVersion !== 'pce-1.0')
    issues.push({
      severity: 'error',
      code: 'metadata.benchmarkVersion',
      message: 'benchmarkVersion must be "pce-1.0".',
    })
  if (!levels.includes(level as EvaluationLevel))
    issues.push({
      severity: 'error',
      code: 'metadata.level',
      message: 'level must be L0, L1, L2, or L3.',
    })
  if (!testModes.includes(testMode as (typeof testModes)[number]))
    issues.push({
      severity: 'error',
      code: 'metadata.evaluation.testMode',
      message: 'evaluation.testMode must be both, blackbox, whitebox, or mixed.',
    })
  if (!scoringModes.includes(scoringMode as ScoringMode))
    issues.push({
      severity: 'error',
      code: 'metadata.evaluation.scoringMode',
      message: 'evaluation.scoringMode is invalid.',
    })
  if (
    levels.includes(level as EvaluationLevel) &&
    scoringModes.includes(scoringMode as ScoringMode) &&
    !scoringModesFor(level as EvaluationLevel).includes(scoringMode as ScoringMode)
  )
    issues.push({
      severity: 'error',
      code: 'metadata.evaluation.scoringMode',
      message: `${level} does not support scoring mode ${scoringMode}.`,
    })

  requiredText('submissionName', value.submissionName, issues)
  requiredText(
    'submitter.github',
    submitter.github,
    issues,
    /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/,
  )
  requiredText('method.name', method.name, issues)
  requiredText('method.version', method.version, issues)
  requiredText('model.name', model.name, issues)
  requiredText('model.version', model.version, issues)
  requiredText(
    'evaluation.polycodeevalCommit',
    evaluation.polycodeevalCommit,
    issues,
    /^(?:[0-9a-fA-F]{7,40}|unknown)$/,
  )
  optionalText('submitter.affiliation', submitter.affiliation, issues)
  optionalText('method.paperUrl', method.paperUrl, issues, true)
  optionalText('method.codeUrl', method.codeUrl, issues, true)
  optionalText('model.provider', model.provider, issues)
  optionalText('evaluation.command', evaluation.command, issues)
  optionalText('evaluation.startedAt', evaluation.startedAt, issues)
  optionalText('evaluation.finishedAt', evaluation.finishedAt, issues)
  optionalText('evaluation.packagedAt', evaluation.packagedAt, issues)
  optionalText('notes', value.notes, issues)
  if (evaluation.workingTreeDirty !== undefined && typeof evaluation.workingTreeDirty !== 'boolean')
    issues.push({
      severity: 'error',
      code: 'metadata.evaluation.workingTreeDirty',
      message: 'evaluation.workingTreeDirty must be a boolean.',
    })
  if (evaluation.environment !== undefined && !isRecord(evaluation.environment))
    issues.push({
      severity: 'error',
      code: 'metadata.evaluation.environment',
      message: 'evaluation.environment must be an object.',
    })
  for (const key of ['os', 'architecture', 'python', 'docker'] as const)
    optionalText(`evaluation.environment.${key}`, environment[key], issues)

  for (const [name, raw] of [
    ['submitter', value.submitter],
    ['method', value.method],
    ['model', value.model],
    ['evaluation', value.evaluation],
  ] as const)
    if (!isRecord(raw))
      issues.push({
        severity: 'error',
        code: `metadata.${name}`,
        message: `${name} must be an object.`,
      })

  if (
    issues.some((issue) =>
      [
        'metadata.level',
        'metadata.evaluation.testMode',
        'metadata.evaluation.scoringMode',
      ].includes(issue.code),
    )
  )
    return { metadata: null, issues }

  return {
    metadata: {
      schemaVersion: '2',
      benchmarkVersion: String(value.benchmarkVersion ?? ''),
      level: level as EvaluationLevel,
      submissionName: String(value.submissionName ?? ''),
      submitter: {
        github: String(submitter.github ?? ''),
        affiliation: String(submitter.affiliation ?? ''),
      },
      method: {
        name: String(method.name ?? ''),
        version: String(method.version ?? ''),
        paperUrl: String(method.paperUrl ?? ''),
        codeUrl: String(method.codeUrl ?? ''),
      },
      model: {
        name: String(model.name ?? ''),
        version: String(model.version ?? ''),
        provider: String(model.provider ?? ''),
      },
      evaluation: {
        polycodeevalCommit: String(evaluation.polycodeevalCommit ?? ''),
        testMode: testMode as SubmissionMetadata['evaluation']['testMode'],
        scoringMode: scoringMode as ScoringMode,
        command: String(evaluation.command ?? ''),
        startedAt: String(evaluation.startedAt ?? ''),
        finishedAt: String(evaluation.finishedAt ?? ''),
        packagedAt: evaluation.packagedAt ? String(evaluation.packagedAt) : undefined,
        workingTreeDirty:
          typeof evaluation.workingTreeDirty === 'boolean'
            ? evaluation.workingTreeDirty
            : undefined,
        environment: {
          os: String(environment.os ?? ''),
          architecture: String(environment.architecture ?? ''),
          python: String(environment.python ?? ''),
          docker: String(environment.docker ?? ''),
        },
      },
      notes: String(value.notes ?? ''),
    },
    issues,
  }
}
