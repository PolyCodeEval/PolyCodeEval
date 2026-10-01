import { BlobWriter, TextReader, ZipWriter } from '@zip.js/zip.js'
import { describe, expect, it } from 'vitest'
import { validatePackage } from './package-validator'
import type { EvaluationLevel, ReleaseManifest, SubmissionMetadata } from './submit.types'

const release: ReleaseManifest = {
  benchmarkVersion: 'pce-1.0',
  taskCounts: { L0: 1, L1: 1, L2: 1, L3: 2 },
  tasks: {
    L0: ['python/demo/L0_demo'],
    L1: ['python/demo/L1_demo'],
    L2: ['python/demo/L2_module'],
    L3: ['python/demo/L3_module__solve', 'python/demo/L3_module__other'],
  },
}

const metadata = (level: EvaluationLevel): SubmissionMetadata => ({
  schemaVersion: '2',
  benchmarkVersion: 'pce-1.0',
  level,
  submissionName: 'Example run',
  submitter: { github: 'example-user', affiliation: '' },
  method: { name: 'Method', version: 'abc123', paperUrl: '', codeUrl: '' },
  model: { name: 'Model', version: '2026-09-01', provider: '' },
  evaluation: {
    polycodeevalCommit: '1234567',
    testMode: level === 'L0' || level === 'L1' ? 'blackbox' : 'both',
    scoringMode: level === 'L0' || level === 'L1' ? 'correctness_only' : 'execution',
    command: '',
    startedAt: '',
    finishedAt: '',
    environment: { os: '', architecture: '', python: '', docker: '' },
  },
  notes: '',
})

async function archive(
  level: EvaluationLevel,
  files: Record<string, unknown>,
  custom?: SubmissionMetadata,
) {
  const writer = new ZipWriter(new BlobWriter('application/zip'))
  await writer.add('submission.json', new TextReader(JSON.stringify(custom ?? metadata(level))))
  for (const [path, content] of Object.entries(files))
    await writer.add(path, new TextReader(JSON.stringify(content)))
  const blob = await writer.close()
  return new File([blob], 'submission.zip', { type: 'application/zip' })
}

const l3Result = (task: string) => ({
  task,
  passed: true,
  compile_passed: true,
  full_passed: true,
  test_pass_ratio: 1,
  compile_score: 0.5,
  test_score: 0.5,
  score: 1,
  test_details: { passed: 1, failed: 0, total: 1 },
  test_mode: 'both',
})

describe('validatePackage', () => {
  it('accepts native L3 results and penalizes a missing task', async () => {
    const task = 'python/demo/L3_module__solve'
    const file = await archive('L3', {
      'evaluation/summary.json': { total: 1, compile_passed: 1, full_passed: 1 },
      'evaluation/python/demo/L3_module__solve.json': l3Result(task),
    })
    const report = await validatePackage(file, release)
    expect(report.valid).toBe(true)
    expect(report.submittedTasks).toBe(1)
    expect(report.missingTasks).toBe(1)
    expect(report.metrics?.fullPassRate).toBe(0.5)
  })

  it('rejects an inconsistent L3 score formula', async () => {
    const task = 'python/demo/L3_module__solve'
    const file = await archive('L3', {
      'evaluation/summary.json': { total: 1, compile_passed: 1, full_passed: 1 },
      'evaluation/python/demo/L3_module__solve.json': { ...l3Result(task), score: 0.25 },
    })
    const report = await validatePackage(file, release)
    expect(report.valid).toBe(false)
    expect(report.issues.map((issue) => issue.code)).toContain('result.executionFormula')
  })

  it('normalizes L2/L3 full pass from build and test-pass ratio', async () => {
    const task = 'python/demo/L3_module__solve'
    const file = await archive('L3', {
      'evaluation/summary.json': { total: 1, compile_passed: 1, full_passed: 1 },
      'evaluation/python/demo/L3_module__solve.json': {
        ...l3Result(task),
        passed: false,
        full_passed: false,
      },
    })
    const report = await validatePackage(file, release)
    expect(report.valid).toBe(true)
    expect(report.metrics?.fullPassRate).toBe(0.5)
  })

  it('recomputes native summary rates and rejects a mismatch', async () => {
    const task = 'python/demo/L3_module__solve'
    const file = await archive('L3', {
      'evaluation/summary.json': {
        total: 1,
        compile_passed: 1,
        full_passed: 1,
        full_pass_rate: 0,
      },
      'evaluation/python/demo/L3_module__solve.json': l3Result(task),
    })
    const report = await validatePackage(file, release)
    expect(report.valid).toBe(false)
    expect(report.summaryConsistent).toBe(false)
    expect(report.issues.map((issue) => issue.code)).toContain('summary.inconsistent')
  })

  it('accepts a native L0 correctness-only result', async () => {
    const task = 'python/demo/L0_demo'
    const file = await archive('L0', {
      'evaluation/summary.json': { total: 1, passed: 0 },
      'evaluation/python/demo/L0_demo.json': {
        task,
        build_status: 'ok',
        passed: false,
        test_mode: 'blackbox',
        test_details: { passed: 8, failed: 2, total: 10 },
        radar_scores: { Correctness: 4 },
      },
    })
    const report = await validatePackage(file, release)
    expect(report.valid).toBe(true)
    expect(report.metrics?.correctness).toBe(4)
    expect(report.qualityEligible).toBe(false)
  })

  it('rejects generated-code directories', async () => {
    const file = await archive('L2', {
      'evaluation/summary.json': { total: 0 },
      'outputs/python/demo/L2_module.txt': 'generated code',
    })
    const report = await validatePackage(file, release)
    expect(report.issues.map((issue) => issue.code)).toContain('archive.unexpected')
  })
})
