import { BlobReader, TextWriter, Uint8ArrayWriter, ZipReader, type Entry } from '@zip.js/zip.js'
import { parseSubmissionMetadata } from './submission-schema'
import type {
  EvaluationLevel,
  EvaluationMetrics,
  ReleaseManifest,
  SubmissionMetadata,
  ValidationIssue,
  ValidationReport,
  ValidationTask,
} from './submit.types'

const MAX_ARCHIVE_ENTRIES = 100_000
const MAX_RESULT_BYTES = 10_000_000
const MAX_LOG_BYTES = 5_000_000
const MAX_LOG_TOTAL_BYTES = 20_000_000
const LOG_EXTENSIONS = new Set(['log', 'txt', 'json', 'jsonl'])
const EPSILON = 1e-6

type JsonObject = Record<string, unknown>

interface ParsedTask {
  taskId: string
  language: string
  project: string
  buildSuccess: boolean
  fullPass: boolean
  testPassRatio: number
  executionScore: number
  correctness: number | null
  faithfulness: number | null
  architecture: number | null
  health: number | null
  overall: number | null
  qualityEligible: boolean
  sourcePath: string
  testMode: string
  testCasesPassed: number | null
  testCasesFailed: number | null
  testCasesTotal: number | null
}

const isObject = (value: unknown): value is JsonObject =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)

const asNumber = (value: unknown): number | null => {
  if (typeof value === 'boolean') return null
  const parsed = Number(value)
  return value === null || value === undefined || value === '' || !Number.isFinite(parsed)
    ? null
    : parsed
}

const pathIsUnsafe = (path: string) =>
  path.startsWith('/') ||
  /^[A-Za-z]:[\\/]/.test(path) ||
  path.includes('\\') ||
  path.includes('\0') ||
  path.split('/').includes('..')

const isSymlink = (entry: Entry) =>
  !entry.msDosCompatible && ((entry.externalFileAttributes >>> 16) & 0o170000) === 0o120000

async function readUtf8(entry: Entry): Promise<string> {
  if (entry.directory) return ''
  const bytes = await entry.getData(new Uint8ArrayWriter())
  return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
}

function taskFromPath(path: string): string | null {
  const parts = path.split('/').filter(Boolean)
  if (parts.length !== 4 || parts[0] !== 'evaluation' || !parts[3].endsWith('.json')) return null
  return `${parts[1]}/${parts[2]}/${parts[3].slice(0, -5)}`
}

function ratioFromL0(row: JsonObject, sourcePath: string, issues: ValidationIssue[]): number {
  if (!isObject(row.test_details))
    issues.push({
      severity: 'error',
      code: 'result.testDetails',
      message: 'test_details must be an object.',
      path: sourcePath,
    })
  const details = isObject(row.test_details) ? row.test_details : {}
  const passed = asNumber(details.passed)
  const failed = asNumber(details.failed)
  const total = asNumber(details.total)
  for (const [field, value] of [
    ['passed', passed],
    ['failed', failed],
    ['total', total],
  ] as const)
    if (value === null || !Number.isInteger(value) || value < 0)
      issues.push({
        severity: 'error',
        code: 'result.testDetails',
        message: `test_details.${field} must be a non-negative integer.`,
        path: sourcePath,
      })
  if (passed !== null && failed !== null && total !== null && passed + failed > total)
    issues.push({
      severity: 'error',
      code: 'result.testDetails',
      message: 'test_details.passed + failed cannot exceed total.',
      path: sourcePath,
    })
  return passed !== null && total ? passed / total : 0
}

function parseL0L1(
  row: JsonObject,
  taskId: string,
  sourcePath: string,
  scoringMode: SubmissionMetadata['evaluation']['scoringMode'],
  issues: ValidationIssue[],
): ParsedTask {
  const radar = isObject(row.radar_scores) ? row.radar_scores : {}
  let correctness = asNumber(radar.Correctness)
  const faithfulness = asNumber(radar.Faithfulness)
  const architecture = asNumber(radar.Architecture)
  const health = asNumber(radar.Health)
  const overall = asNumber(row.overall_score)
  if (row.build_status !== undefined && typeof row.build_status !== 'string')
    issues.push({
      severity: 'error',
      code: 'result.buildStatus',
      message: 'build_status must be a string.',
      path: sourcePath,
    })
  for (const [field, value] of [
    ['Correctness', correctness],
    ['Faithfulness', faithfulness],
    ['Architecture', architecture],
    ['Health', health],
    ['overall_score', overall],
  ] as const)
    if (value !== null && (value < 0 || value > 5))
      issues.push({
        severity: 'error',
        code: 'result.scoreRange',
        message: `${field} must be within [0, 5].`,
        path: sourcePath,
      })
  const completeQuality = [correctness, faithfulness, architecture, health, overall].every(
    (value) => value !== null,
  )
  if (typeof row.passed !== 'boolean')
    issues.push({
      severity: 'error',
      code: 'result.passed',
      message: 'passed must be a boolean.',
      path: sourcePath,
    })
  const fullPass = Boolean(row.passed)
  let testPassRatio = ratioFromL0(row, sourcePath, issues)
  const testDetails = isObject(row.test_details) ? row.test_details : {}
  if (scoringMode === 'full_quality' && fullPass && asNumber(testDetails.total) === 0)
    testPassRatio = 1
  const expectedCorrectness = 5 * testPassRatio
  if (correctness === null) {
    issues.push({
      severity: 'error',
      code: 'result.correctness',
      message: 'Correctness is required in radar_scores.',
      path: sourcePath,
    })
    correctness = expectedCorrectness
  } else if (Math.abs(correctness - expectedCorrectness) > 0.011)
    issues.push({
      severity: 'error',
      code: 'result.correctnessFormula',
      message: 'Correctness must equal 5 × the test-pass ratio.',
      path: sourcePath,
    })
  if (scoringMode === 'full_quality' && !completeQuality)
    issues.push({
      severity: 'error',
      code: 'result.qualityFields',
      message: 'full_quality requires all four radar dimensions and overall_score.',
      path: sourcePath,
    })
  if (
    scoringMode === 'full_quality' &&
    [faithfulness, architecture, health, overall].every((value) => value !== null)
  ) {
    const expectedOverall = Number(
      (
        0.4 * correctness +
        0.25 * (faithfulness ?? 0) +
        0.25 * (architecture ?? 0) +
        0.1 * (health ?? 0)
      ).toFixed(2),
    )
    if (Math.abs((overall ?? 0) - expectedOverall) > 0.011)
      issues.push({
        severity: 'error',
        code: 'result.overallFormula',
        message: 'overall_score does not match the weighted quality formula.',
        path: sourcePath,
      })
  }
  const buildSuccess =
    fullPass ||
    testPassRatio > 0 ||
    ['ok', 'success', 'passed'].includes(String(row.build_status ?? ''))
  if (testPassRatio < 0 || testPassRatio > 1)
    issues.push({
      severity: 'error',
      code: 'result.testPassRatio',
      message: 'The test-pass ratio must be within [0, 1].',
      path: sourcePath,
    })
  return {
    taskId,
    language: taskId.split('/')[0],
    project: taskId.split('/')[1],
    buildSuccess,
    fullPass,
    testPassRatio: Math.min(1, Math.max(0, testPassRatio)),
    executionScore: testPassRatio,
    correctness,
    faithfulness,
    architecture,
    health,
    overall,
    qualityEligible: scoringMode === 'full_quality' && completeQuality,
    sourcePath,
    testMode: String(row.test_mode ?? ''),
    testCasesPassed: asNumber(isObject(row.test_details) ? row.test_details.passed : null),
    testCasesFailed: asNumber(isObject(row.test_details) ? row.test_details.failed : null),
    testCasesTotal: asNumber(isObject(row.test_details) ? row.test_details.total : null),
  }
}

function parseL2L3(
  row: JsonObject,
  taskId: string,
  sourcePath: string,
  issues: ValidationIssue[],
): ParsedTask {
  const passed = typeof row.passed === 'boolean' ? row.passed : false
  if (typeof row.passed !== 'boolean')
    issues.push({
      severity: 'error',
      code: 'result.passed',
      message: 'passed must be a boolean.',
      path: sourcePath,
    })
  const nativeStatus = (field: 'compile_passed' | 'full_passed') => {
    if (typeof row[field] === 'boolean') return row[field]
    if (row[field] === undefined && row.passed === false) {
      issues.push({
        severity: 'warning',
        code: 'result.derivedStatus',
        message: `${field} is missing from a failed result and was normalized to false.`,
        path: sourcePath,
      })
      return false
    }
    issues.push({
      severity: 'error',
      code: 'result.status',
      message: `${field} must be a boolean.`,
      path: sourcePath,
    })
    return false
  }
  const buildSuccess = nativeStatus('compile_passed')
  const reportedFullPass = nativeStatus('full_passed')
  const details = isObject(row.test_details) ? row.test_details : null
  const detailsPassed = details ? asNumber(details.passed) : null
  const detailsFailed = details ? asNumber(details.failed) : null
  const detailsTotal = details ? asNumber(details.total) : null
  if (!details && buildSuccess)
    issues.push({
      severity: 'error',
      code: 'result.testDetails',
      message: 'test_details must be an object for a build-successful result.',
      path: sourcePath,
    })
  else if (!details)
    issues.push({
      severity: 'warning',
      code: 'result.testDetails',
      message: 'test_details is missing from a failed result and was normalized to zero.',
      path: sourcePath,
    })
  if (details)
    for (const [field, value] of [
      ['passed', detailsPassed],
      ['failed', detailsFailed],
      ['total', detailsTotal],
    ] as const)
      if (value === null || !Number.isInteger(value) || value < 0)
        issues.push({
          severity: 'error',
          code: 'result.testDetails',
          message: `test_details.${field} must be a non-negative integer.`,
          path: sourcePath,
        })
  if (
    detailsPassed !== null &&
    detailsFailed !== null &&
    detailsTotal !== null &&
    detailsPassed + detailsFailed > detailsTotal
  )
    issues.push({
      severity: 'error',
      code: 'result.testDetails',
      message: 'test_details.passed + failed cannot exceed total.',
      path: sourcePath,
    })
  const detailsRatio = detailsPassed !== null && detailsTotal ? detailsPassed / detailsTotal : 0
  const providedRatio = asNumber(row.test_pass_ratio)
  const testPassRatio = providedRatio ?? detailsRatio
  const fullPass = buildSuccess && testPassRatio >= 1 - EPSILON
  const expectedCompile = buildSuccess ? 0.5 : 0
  const expectedTest = buildSuccess ? Number((0.5 * testPassRatio).toFixed(4)) : 0
  const expectedScore = Number((expectedCompile + expectedTest).toFixed(4))
  if (testPassRatio < 0 || testPassRatio > 1)
    issues.push({
      severity: 'error',
      code: 'result.testPassRatio',
      message: 'test_pass_ratio must be within [0, 1].',
      path: sourcePath,
    })
  if (typeof row.passed === 'boolean' && passed !== reportedFullPass)
    issues.push({
      severity: 'error',
      code: 'result.fullPassMismatch',
      message: 'passed and full_passed must agree.',
      path: sourcePath,
    })
  if (details && providedRatio !== null && Math.abs(detailsRatio - testPassRatio) > 1.5e-4)
    issues.push({
      severity: 'error',
      code: 'result.testDetailsRatio',
      message: 'test_pass_ratio does not match test_details.',
      path: sourcePath,
    })
  const scoreValues = [
    ['compile_score', asNumber(row.compile_score), expectedCompile],
    ['test_score', asNumber(row.test_score), expectedTest],
    ['score', asNumber(row.score), expectedScore],
  ] as const
  for (const [field, actual, expected] of scoreValues) {
    if (actual === null)
      issues.push({
        severity: 'warning',
        code: 'result.derivedScore',
        message: `${field} is missing and was normalized to ${expected.toFixed(4)}.`,
        path: sourcePath,
      })
    else if (Math.abs(actual - expected) > EPSILON)
      issues.push({
        severity: 'error',
        code: 'result.executionFormula',
        message: `${field}=${actual}; expected ${expected}.`,
        path: sourcePath,
      })
  }
  if (!buildSuccess && Math.abs(testPassRatio) > EPSILON)
    issues.push({
      severity: 'error',
      code: 'result.testWithoutBuild',
      message: 'test_pass_ratio must be zero when compilation fails.',
      path: sourcePath,
    })
  return {
    taskId,
    language: taskId.split('/')[0],
    project: taskId.split('/')[1],
    buildSuccess,
    fullPass,
    testPassRatio: Math.min(1, Math.max(0, testPassRatio)),
    executionScore: asNumber(row.score) ?? expectedScore,
    correctness: null,
    faithfulness: null,
    architecture: null,
    health: null,
    overall: null,
    qualityEligible: false,
    sourcePath,
    testMode: String(row.test_mode ?? ''),
    testCasesPassed: detailsPassed,
    testCasesFailed: detailsFailed,
    testCasesTotal: detailsTotal,
  }
}

function aggregate(
  rows: ParsedTask[],
  expected: number,
  scoringMode: SubmissionMetadata['evaluation']['scoringMode'],
): EvaluationMetrics {
  const buildRows = rows.filter((row) => row.buildSuccess)
  const mean = (field: keyof ParsedTask): number | null => {
    const values = rows.flatMap((row) =>
      typeof row[field] === 'number' ? [row[field] as number] : [],
    )
    return values.length ? values.reduce((sum, value) => sum + value, 0) / expected : null
  }
  return {
    submitted: rows.length,
    expected,
    buildSuccessRate: rows.filter((row) => row.buildSuccess).length / expected,
    fullPassRate: rows.filter((row) => row.fullPass).length / expected,
    conditionalTestPassRatio: buildRows.length
      ? buildRows.reduce((sum, row) => sum + row.testPassRatio, 0) / buildRows.length
      : null,
    executionScore: rows.reduce((sum, row) => sum + row.executionScore, 0) / expected,
    correctness: mean('correctness'),
    faithfulness: scoringMode === 'full_quality' ? mean('faithfulness') : null,
    architecture: scoringMode === 'full_quality' ? mean('architecture') : null,
    health: scoringMode === 'full_quality' ? mean('health') : null,
    overall: scoringMode === 'full_quality' ? mean('overall') : null,
  }
}

function nativeSummary(rows: ParsedTask[], scoringMode: string): Record<string, number | null> {
  const count = rows.length
  const denominator = count || 1
  const sum = (field: keyof ParsedTask) =>
    rows.reduce(
      (total, row) => total + (typeof row[field] === 'number' ? (row[field] as number) : 0),
      0,
    )
  const mean = (field: keyof ParsedTask) => sum(field) / denominator
  const build = rows.filter((row) => row.buildSuccess).length
  const full = rows.filter((row) => row.fullPass).length
  return {
    total: count,
    passed: full,
    full_passed: full,
    compile_passed: build,
    pass_rate: full / denominator,
    full_pass_rate: full / denominator,
    compile_pass_rate: build / denominator,
    avg_score: sum('executionScore') / denominator,
    total_score: sum('executionScore'),
    compile_score: build * 0.5,
    test_score: rows.reduce(
      (total, row) => total + (row.buildSuccess ? 0.5 * row.testPassRatio : 0),
      0,
    ),
    avg_correctness: mean('correctness'),
    avg_faithfulness: scoringMode === 'full_quality' ? mean('faithfulness') : null,
    avg_architecture: scoringMode === 'full_quality' ? mean('architecture') : null,
    avg_health: scoringMode === 'full_quality' ? mean('health') : null,
    avg_overall_score: scoringMode === 'full_quality' ? mean('overall') : null,
  }
}

function compareSummaryScope(
  native: JsonObject,
  computed: Record<string, number | null>,
  fields: string[],
  issues: ValidationIssue[],
  scope: string,
) {
  for (const field of fields) {
    const actual = asNumber(native[field])
    const expected = computed[field]
    if (actual === null || expected === null || expected === undefined) continue
    const tolerance = Number.isInteger(actual) ? 0 : 1.5e-4
    if (Math.abs(actual - expected) > tolerance)
      issues.push({
        severity: 'error',
        code: 'summary.inconsistent',
        message: `${scope}.${field}=${actual}; task results produce ${expected}.`,
        path: 'evaluation/summary.json',
      })
  }
}

function checkSummary(
  summary: JsonObject,
  rows: ParsedTask[],
  level: EvaluationLevel,
  scoringMode: SubmissionMetadata['evaluation']['scoringMode'],
  issues: ValidationIssue[],
): boolean {
  const before = issues.length
  const fields =
    level === 'L0' || level === 'L1'
      ? [
          'total',
          'passed',
          'pass_rate',
          'avg_correctness',
          'avg_faithfulness',
          'avg_architecture',
          'avg_health',
          'avg_overall_score',
        ]
      : [
          'total',
          'full_passed',
          'compile_passed',
          'full_pass_rate',
          'compile_pass_rate',
          'avg_score',
          'total_score',
          'compile_score',
          'test_score',
        ]
  compareSummaryScope(summary, nativeSummary(rows, scoringMode), fields, issues, 'overall')

  for (const [nativeKey, groupKey] of [
    ['by_language', (row: ParsedTask) => row.language],
    ['by_project', (row: ParsedTask) => `${row.language}/${row.project}`],
  ] as const) {
    const nativeGroup = summary[nativeKey]
    if (!isObject(nativeGroup)) continue
    for (const [key, value] of Object.entries(nativeGroup)) {
      if (!isObject(value)) continue
      const scoped = rows.filter((row) => groupKey(row) === key)
      if (!scoped.length) {
        issues.push({
          severity: 'error',
          code: 'summary.inconsistent',
          message: `${nativeKey}.${key} does not match a submitted task scope.`,
          path: 'evaluation/summary.json',
        })
        continue
      }
      compareSummaryScope(
        value,
        nativeSummary(scoped, scoringMode),
        fields,
        issues,
        `${nativeKey}.${key}`,
      )
    }
  }

  if (level === 'L2' || level === 'L3') {
    const nativeTasks = summary.by_task
    if (isObject(nativeTasks))
      for (const [taskId, value] of Object.entries(nativeTasks)) {
        if (!isObject(value)) continue
        const row = rows.find((candidate) => candidate.taskId === taskId)
        if (!row) {
          issues.push({
            severity: 'error',
            code: 'summary.inconsistent',
            message: `by_task.${taskId} does not match a submitted task.`,
            path: 'evaluation/summary.json',
          })
          continue
        }
        compareSummaryScope(
          value,
          {
            score: row.executionScore,
            compile_score: row.buildSuccess ? 0.5 : 0,
            test_score: row.buildSuccess ? 0.5 * row.testPassRatio : 0,
            test_pass_ratio: row.testPassRatio,
          },
          ['score', 'compile_score', 'test_score', 'test_pass_ratio'],
          issues,
          `by_task.${taskId}`,
        )
      }
  } else if (isObject(summary.test_case_stats)) {
    for (const [projectId, value] of Object.entries(summary.test_case_stats)) {
      if (!isObject(value)) continue
      const row = rows.find(
        (candidate) => `${candidate.language}/${candidate.project}` === projectId,
      )
      if (!row) continue
      compareSummaryScope(
        value,
        {
          passed: row.testCasesPassed,
          failed: row.testCasesFailed,
          total: row.testCasesTotal,
        },
        ['passed', 'failed', 'total'],
        issues,
        `test_case_stats.${projectId}`,
      )
    }
  }
  return !issues.slice(before).some((issue) => issue.code === 'summary.inconsistent')
}

function scanSensitive(path: string, text: string, issues: ValidationIssue[]) {
  if (
    /(?:sk|ghp|github_pat|xox[baprs])[-_A-Za-z0-9]{16,}/i.test(text) ||
    /(?:api[_-]?key|access[_-]?token|secret)["'\s:=]+[A-Za-z0-9_\-]{12,}/i.test(text)
  )
    issues.push({
      severity: 'error',
      code: 'privacy.secret',
      message: 'A possible credential or access token was detected.',
      path,
    })
  if (/\/(?:Users|home)\/[^/\s]+\//.test(text) || /(?:^|\/)\.env(?:$|\s|\/)/m.test(text))
    issues.push({
      severity: 'warning',
      code: 'privacy.localPath',
      message: 'A local user path or .env reference was detected; review it before publishing.',
      path,
    })
}

export async function validatePackage(
  file: File,
  release: ReleaseManifest,
): Promise<ValidationReport> {
  const reader = new ZipReader(new BlobReader(file))
  const issues: ValidationIssue[] = []
  let metadata: SubmissionMetadata | null = null
  try {
    const entries = await reader.getEntries()
    if (entries.length > MAX_ARCHIVE_ENTRIES)
      issues.push({
        severity: 'error',
        code: 'archive.entries',
        message: `Archives may contain at most ${MAX_ARCHIVE_ENTRIES.toLocaleString()} entries.`,
      })
    const files = entries.filter((entry) => !entry.directory)
    const names = files.map((entry) => entry.filename)
    const seen = new Set<string>()
    for (const entry of files) {
      const path = entry.filename
      if (seen.has(path))
        issues.push({
          severity: 'error',
          code: 'archive.duplicate',
          message: 'Duplicate archive entry.',
          path,
        })
      seen.add(path)
      if (pathIsUnsafe(path))
        issues.push({
          severity: 'error',
          code: 'archive.path',
          message: 'Unsafe archive path.',
          path,
        })
      if (isSymlink(entry))
        issues.push({
          severity: 'error',
          code: 'archive.symlink',
          message: 'Symbolic links are not accepted.',
          path,
        })
      if (entry.encrypted)
        issues.push({
          severity: 'error',
          code: 'archive.encrypted',
          message: 'Encrypted entries are not accepted.',
          path,
        })
      if (
        path !== 'submission.json' &&
        path !== 'evaluation/summary.json' &&
        !path.startsWith('evaluation/') &&
        !path.startsWith('logs/')
      )
        issues.push({
          severity: 'error',
          code: 'archive.unexpected',
          message: 'Only submission.json, evaluation/, and optional logs/ are accepted.',
          path,
        })
    }

    const metadataEntry = files.find((entry) => entry.filename === 'submission.json')
    if (!metadataEntry)
      issues.push({
        severity: 'error',
        code: 'metadata.missing',
        message: 'submission.json is missing from the archive root.',
      })
    else {
      try {
        const source = await metadataEntry.getData(new TextWriter())
        scanSensitive('submission.json', source, issues)
        const parsed = parseSubmissionMetadata(JSON.parse(source))
        metadata = parsed.metadata
        issues.push(...parsed.issues)
      } catch (error) {
        issues.push({
          severity: 'error',
          code: 'metadata.json',
          message: `submission.json is invalid: ${error instanceof Error ? error.message : String(error)}`,
        })
      }
    }

    const summaryEntry = files.find((entry) => entry.filename === 'evaluation/summary.json')
    let summary: JsonObject | null = null
    if (!summaryEntry)
      issues.push({
        severity: 'error',
        code: 'summary.missing',
        message: 'evaluation/summary.json is required.',
      })
    else
      try {
        const source = await summaryEntry.getData(new TextWriter())
        scanSensitive(summaryEntry.filename, source, issues)
        const parsed = JSON.parse(source)
        if (!isObject(parsed)) throw new Error('the document must be a JSON object')
        summary = parsed
      } catch (error) {
        issues.push({
          severity: 'error',
          code: 'summary.json',
          message: `summary.json is invalid: ${error instanceof Error ? error.message : String(error)}`,
          path: 'evaluation/summary.json',
        })
      }

    const logEntries = files.filter((entry) => entry.filename.startsWith('logs/'))
    const logBytes = logEntries.reduce((sum, entry) => sum + entry.uncompressedSize, 0)
    if (logBytes > MAX_LOG_TOTAL_BYTES)
      issues.push({
        severity: 'error',
        code: 'logs.totalSize',
        message: 'Optional logs may use at most 20 MB in total.',
      })
    for (const entry of logEntries) {
      const extension = entry.filename.split('.').pop()?.toLowerCase() ?? ''
      if (!LOG_EXTENSIONS.has(extension))
        issues.push({
          severity: 'error',
          code: 'logs.extension',
          message: 'Logs must use .log, .txt, .json, or .jsonl.',
          path: entry.filename,
        })
      if (entry.uncompressedSize > MAX_LOG_BYTES)
        issues.push({
          severity: 'error',
          code: 'logs.fileSize',
          message: 'Each optional log must be 5 MB or smaller.',
          path: entry.filename,
        })
      if (entry.uncompressedSize <= MAX_LOG_BYTES)
        try {
          scanSensitive(entry.filename, await readUtf8(entry), issues)
        } catch {
          issues.push({
            severity: 'error',
            code: 'logs.encoding',
            message: 'Logs must be valid UTF-8 text.',
            path: entry.filename,
          })
        }
    }

    const level = metadata?.level ?? ''
    const expectedIds = level ? (release.tasks[level] ?? []) : []
    const expected = new Set(expectedIds)
    const parsedTasks = new Map<string, ParsedTask>()
    const resultEntries = files.filter(
      (entry) =>
        entry.filename.startsWith('evaluation/') && entry.filename !== 'evaluation/summary.json',
    )
    for (const entry of resultEntries) {
      const pathTaskId = taskFromPath(entry.filename)
      if (!pathTaskId) {
        issues.push({
          severity: 'error',
          code: 'result.path',
          message: 'Task results must use evaluation/<language>/<project>/<task>.json.',
          path: entry.filename,
        })
        continue
      }
      if (entry.uncompressedSize > MAX_RESULT_BYTES) {
        issues.push({
          severity: 'error',
          code: 'result.size',
          message: 'A task result exceeds the 10 MB browser validation limit.',
          path: entry.filename,
        })
        continue
      }
      try {
        const source = await readUtf8(entry)
        scanSensitive(entry.filename, source, issues)
        const value = JSON.parse(source)
        if (!isObject(value)) throw new Error('the document must be a JSON object')
        const taskId = String(value.task ?? pathTaskId)
        if (taskId !== pathTaskId)
          issues.push({
            severity: 'error',
            code: 'result.taskPath',
            message: `The task field (${taskId}) does not match the result path (${pathTaskId}).`,
            path: entry.filename,
          })
        if (parsedTasks.has(taskId))
          issues.push({
            severity: 'error',
            code: 'result.duplicateTask',
            message: 'Multiple result files resolve to the same task.',
            path: taskId,
          })
        if (level) {
          const task =
            level === 'L0' || level === 'L1'
              ? parseL0L1(
                  value,
                  taskId,
                  entry.filename,
                  metadata?.evaluation.scoringMode ?? 'correctness_only',
                  issues,
                )
              : parseL2L3(value, taskId, entry.filename, issues)
          parsedTasks.set(taskId, task)
        }
      } catch (error) {
        issues.push({
          severity: 'error',
          code: 'result.json',
          message: `Task result is invalid: ${error instanceof Error ? error.message : String(error)}`,
          path: entry.filename,
        })
      }
    }

    const submitted = [...parsedTasks.values()].filter((row) => expected.has(row.taskId))
    const extra = [...parsedTasks.values()].filter((row) => !expected.has(row.taskId))
    const missing = expectedIds.filter((taskId) => !parsedTasks.has(taskId))
    if (extra.length)
      issues.push({
        severity: 'error',
        code: 'coverage.extra',
        message: `${extra.length} task IDs do not belong to ${level} in ${release.benchmarkVersion}.`,
      })
    if (metadata && submitted.length === 0)
      issues.push({
        severity: 'error',
        code: 'coverage.empty',
        message: 'No valid task results were found below evaluation/.',
      })
    if (missing.length)
      issues.push({
        severity: 'warning',
        code: 'coverage.partial',
        message: `${missing.length} missing tasks will receive zero in the fixed-denominator ranking.`,
      })

    if (metadata) {
      const observedModes = new Set(
        [...parsedTasks.values()].map((row) => row.testMode).filter(Boolean),
      )
      if (!observedModes.size)
        issues.push({
          severity: 'warning',
          code: 'result.testMode',
          message: 'No task result records a test_mode value.',
        })
      else {
        const inferredMode =
          observedModes.size === 1 ? ([...observedModes][0] ?? '') : ('mixed' as const)
        if (metadata.evaluation.testMode !== inferredMode)
          issues.push({
            severity: 'error',
            code: 'result.testMode',
            message: `submission.json declares testMode=${metadata.evaluation.testMode}; native results imply ${inferredMode}.`,
          })
      }
    }

    const summaryConsistent =
      summary && level
        ? checkSummary(
            summary,
            submitted,
            level,
            metadata?.evaluation.scoringMode ?? 'execution',
            issues,
          )
        : false
    const expectedByLanguage = new Map<string, number>()
    for (const taskId of expectedIds) {
      const language = taskId.split('/')[0]
      expectedByLanguage.set(language, (expectedByLanguage.get(language) ?? 0) + 1)
    }
    const scoringMode = metadata?.evaluation.scoringMode ?? 'execution'
    const metrics = level ? aggregate(submitted, expectedIds.length || 1, scoringMode) : null
    const perLanguage = [...expectedByLanguage.entries()].map(([language, count]) => ({
      language,
      ...aggregate(
        submitted.filter((row) => row.language === language),
        count,
        scoringMode,
      ),
    }))
    const qualityEligible =
      Boolean(metadata) &&
      (level === 'L0' || level === 'L1') &&
      metadata?.evaluation.scoringMode === 'full_quality' &&
      submitted.every((row) => row.qualityEligible)
    const tasks: ValidationTask[] = [
      ...submitted.map((row) => ({ ...row, status: 'Submitted' as const })),
      ...missing.map((taskId) => ({
        taskId,
        language: taskId.split('/')[0],
        project: taskId.split('/')[1],
        status: 'Missing' as const,
        buildSuccess: false,
        fullPass: false,
        testPassRatio: 0,
        executionScore: 0,
        correctness: 0,
        qualityEligible: false,
        sourcePath: '',
      })),
      ...extra.map((row) => ({ ...row, status: 'Extra' as const })),
    ]
    return {
      valid: !issues.some((issue) => issue.severity === 'error'),
      fileName: file.name,
      archiveBytes: file.size,
      fileCount: files.length,
      benchmarkVersion: metadata?.benchmarkVersion ?? '',
      level,
      scoringMode: metadata?.evaluation.scoringMode ?? '',
      expectedTasks: expectedIds.length,
      submittedTasks: submitted.length,
      missingTasks: missing.length,
      extraTasks: extra.length,
      coverageRate: expectedIds.length ? submitted.length / expectedIds.length : 0,
      summaryConsistent,
      qualityEligible,
      metrics,
      perLanguage,
      issues,
      tasks,
      entries: names.slice(0, 5000),
      logs: logEntries.map((entry) => entry.filename),
      metadata,
    }
  } finally {
    await reader.close()
  }
}
