import type {
  CoverageRow,
  DatasetRow,
  JsonRecord,
  Manifest,
  PromptEntry,
  PromptQualityRow,
  ResultRow,
  SignificanceRow,
  TokenRow,
} from '../types/benchmark'

const BASE = `${import.meta.env.BASE_URL}data/`
const REPO = 'https://github.com/PolyCodeEval/PolyCodeEval/blob/main/'
const languageLabels: Record<string, string> = {
  cpp: 'C++',
  go: 'Go',
  java: 'Java',
  javascript: 'JavaScript',
  typescript: 'JavaScript',
  python: 'Python',
}
const languageLabel = (value: string) => languageLabels[value.toLowerCase()] ?? value
const sourceUrl = (value: string) =>
  !value || /^https?:\/\//.test(value) ? value : `${REPO}${value.replace(/^\//, '')}`
const isObject = (v: unknown): v is JsonRecord =>
  Boolean(v) && typeof v === 'object' && !Array.isArray(v)
const text = (o: JsonRecord, ...keys: string[]) => {
  for (const key of keys) if (o[key] !== undefined && o[key] !== null) return String(o[key])
  return ''
}
const num = (o: JsonRecord, ...keys: string[]) => {
  for (const key of keys) {
    const value = o[key]
    if (value === null || value === undefined || value === '') continue
    const parsed = typeof value === 'number' ? value : Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}
const bool = (o: JsonRecord, ...keys: string[]) => {
  for (const key of keys) {
    const value = o[key]
    if (typeof value === 'boolean') return value
    if (typeof value === 'number') return value > 0
    if (typeof value === 'string') {
      if (['true', 'yes', 'pass', 'passed', 'success', '1'].includes(value.toLowerCase()))
        return true
      if (['false', 'no', 'fail', 'failed', 'error', '0'].includes(value.toLowerCase()))
        return false
    }
  }
  return null
}
const ratio = (o: JsonRecord, ...keys: string[]) => {
  const value = num(o, ...keys)
  return value !== null && value > 1 && value <= 100 ? value / 100 : value
}

export const rowsOf = (value: unknown): JsonRecord[] => {
  if (Array.isArray(value)) return value.filter(isObject)
  if (!isObject(value)) return []
  for (const key of [
    'records',
    'rows',
    'tasks',
    'results',
    'data',
    'projects',
    'entries',
    'tests',
    'comparisons',
    'prompts',
  ]) {
    if (Array.isArray(value[key])) return (value[key] as unknown[]).filter(isObject)
  }
  return Object.entries(value).flatMap(([key, item]) => {
    if (isObject(item)) return [{ _key: key, ...item }]
    return []
  })
}

export async function fetchJson<T = unknown>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { signal })
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

export const normalizeManifest = (raw: unknown): Manifest => {
  const o = isObject(raw) ? raw : {}
  const countsRaw = (
    isObject(o.taskCounts) ? o.taskCounts : isObject(o.task_counts) ? o.task_counts : {}
  ) as JsonRecord
  return {
    version:
      text(o, 'version', 'datasetVersion', 'dataVersion', 'data_version') || 'Unversioned snapshot',
    generatedAt: text(o, 'generatedAt', 'generated_at', 'createdAt', 'created_at'),
    repositories: num(o, 'repositories', 'repositoryCount', 'repository_count') ?? 58,
    taskCounts: {
      L0: Number(countsRaw.L0 ?? countsRaw.l0 ?? 58),
      L1: Number(countsRaw.L1 ?? countsRaw.l1 ?? 58),
      L2: Number(countsRaw.L2 ?? countsRaw.l2 ?? 150),
      L3: Number(countsRaw.L3 ?? countsRaw.l3 ?? 2324),
    },
    configurations: Array.isArray(o.configurations) ? o.configurations : [],
  }
}

export const normalizeDataset = (raw: unknown): DatasetRow[] =>
  rowsOf(raw).map((o) => {
    const levels = isObject(o.levels) ? o.levels : isObject(o.taskCounts) ? o.taskCounts : {}
    return {
      language: languageLabel(text(o, 'languageLabel', 'language', 'lang')),
      project: text(o, 'project', 'repository', 'repo', 'name', '_key'),
      difficulty: text(o, 'difficulty', 'diff'),
      testFramework: text(o, 'testFramework', 'test_framework', 'tests'),
      source: text(o, 'source', 'origin'),
      loc: num(o, 'loc', 'LOC', 'oracleLoc', 'oracle_loc'),
      coverage: ratio(o, 'coverage', 'coverageRate', 'coverage_rate'),
      oracleValidated: bool(o, 'oracleValidated', 'oracle_validated', 'oracle'),
      levels: {
        L0: Number(levels.L0 ?? levels.l0 ?? o.L0 ?? o.l0 ?? 0),
        L1: Number(levels.L1 ?? levels.l1 ?? o.L1 ?? o.l1 ?? 0),
        L2: Number(levels.L2 ?? levels.l2 ?? o.L2 ?? o.l2 ?? 0),
        L3: Number(levels.L3 ?? levels.l3 ?? o.L3 ?? o.l3 ?? 0),
      },
      raw: o,
    }
  })

export const normalizeResults = (raw: unknown, defaults: Partial<ResultRow> = {}): ResultRow[] =>
  rowsOf(raw).map((o) => ({
    level: text(o, 'level') || defaults.level || '',
    language: languageLabel(text(o, 'language', 'lang') || defaults.language || ''),
    project: text(o, 'project', 'repository', 'repo') || defaults.project || '',
    taskId: text(o, 'taskId', 'task_id', 'id', '_key'),
    method: text(o, 'method', 'solver', 'agent') || defaults.method || '',
    model: text(o, 'model', 'backend') || defaults.model || '',
    buildSuccess: bool(o, 'buildSuccess', 'build_success', 'build', 'compile_success'),
    fullPass: bool(o, 'fullPass', 'full_pass', 'all_passed', 'passed'),
    testPassRatio: ratio(o, 'testPassRatio', 'test_pass_ratio', 'pass_rate'),
    executionScore: ratio(o, 'executionScore', 'execution_score', 'score'),
    correctness: num(o, 'correctness'),
    faithfulness: num(o, 'faithfulness'),
    architecture: num(o, 'architecture'),
    health: num(o, 'health'),
    overall: num(o, 'overall', 'overall_score'),
    submissionId: text(o, 'submissionId', 'submission_id'),
    submitter: text(o, 'submitter'),
    sourceType: text(o, 'sourceType', 'source_type') || 'Maintainer Evaluated',
    submittedTasks: num(o, 'submittedTasks', 'submitted_tasks'),
    expectedTasks: num(o, 'expectedTasks', 'expected_tasks'),
    coverageRate: ratio(o, 'coverageRate', 'coverage_rate'),
    pullRequestUrl: text(o, 'pullRequestUrl', 'pull_request_url'),
    mergeCommit: text(o, 'mergeCommit', 'merge_commit'),
    scoringMode: text(o, 'scoringMode', 'scoring_mode'),
    qualityEligible: bool(o, 'qualityEligible', 'quality_eligible') ?? false,
    missing: bool(o, 'missing', 'notSubmitted', 'not_submitted') ?? false,
    sourceLink: sourceUrl(text(o, 'sourceLink', 'source_link', 'source')),
    raw: o,
  }))

export const normalizeCoverage = (raw: unknown): CoverageRow[] => {
  const source =
    isObject(raw) && Array.isArray(raw.tasks) ? raw.tasks.filter(isObject) : rowsOf(raw)
  return source.map((o) => ({
    level: text(o, 'level'),
    language: languageLabel(text(o, 'language', 'lang')),
    project: text(o, 'project', 'repository', 'repo'),
    metric: text(o, 'metric', 'coverageType', 'coverage_type') || 'Coverage',
    value: ratio(o, 'value', 'coverage', 'rate'),
    raw: o,
  }))
}

export const normalizePromptQuality = (raw: unknown): PromptQualityRow[] =>
  rowsOf(raw).flatMap((o) => {
    const base = {
      level: text(o, 'level'),
      language: languageLabel(text(o, 'language', 'lang')),
      project: text(o, 'project', 'repository', 'repo'),
      taskId: text(o, 'taskId', 'task_id', 'id', '_key'),
    }
    if (isObject(o.judges))
      return Object.entries(o.judges).flatMap(([judge, value]) =>
        isObject(value)
          ? [
              {
                ...base,
                judge,
                score: num(value, 'score', 'quality', 'rating'),
                raw: { ...o, judgeResult: value },
              },
            ]
          : [],
      )
    return [
      {
        ...base,
        judge: text(o, 'judge', 'model', 'evaluator'),
        score: num(o, 'score', 'quality', 'rating'),
        raw: o,
      },
    ]
  })

export const normalizeSignificance = (raw: unknown): SignificanceRow[] => {
  const o = isObject(raw) ? raw : {}
  const grouped = ['selectedComparisons', 'l2ToL3ScoreTests', 'l2ToL3FullPassTests'].flatMap(
    (key) =>
      Array.isArray(o[key])
        ? (o[key] as unknown[]).filter(isObject).map((item) => ({ _group: key, ...item }))
        : [],
  )
  return (grouped.length ? grouped : rowsOf(raw)).map((item) => ({
    comparison:
      text(item, 'comparison', 'name') ||
      [text(item, 'model'), text(item, 'scope'), text(item, '_group')].filter(Boolean).join(' · '),
    level: text(item, 'level') || (text(item, '_group').startsWith('l2ToL3') ? 'L2→L3' : ''),
    n: num(item, 'n', 'n_pairs', 'sampleSize', 'sample_size'),
    statistic: num(item, 'statistic', 'wilcoxon_statistic', 'w', 'W'),
    difference: num(item, 'difference', 'mean_delta', 'median_delta', 'delta'),
    pValue: num(item, 'pValue', 'p_value', 'p'),
    adjustment: text(item, 'adjustment'),
    interpretation: text(item, 'interpretation', 'hypothesis', 'finding', 'conclusion'),
    raw: item,
  }))
}

export const normalizeTokens = (raw: unknown): TokenRow[] => {
  const parent = isObject(raw) ? raw : {}
  const records = Array.isArray(parent.records) ? parent.records.filter(isObject) : rowsOf(raw)
  const construction = Array.isArray(parent.construction)
    ? parent.construction
        .filter(isObject)
        .map((o) => ({ level: 'Construction', method: text(o, 'stage'), usage: o }))
    : []
  return [...construction, ...records].map((o) => {
    const usage = isObject(o.usage) ? o.usage : o
    const draft =
      (num(usage, 'draft', 'draftTokens', 'draft_tokens') ?? 0) +
      (num(usage, 'draftInputTokens', 'draft_input_tokens') ?? 0) +
      (num(usage, 'draftOutputTokens', 'draft_output_tokens') ?? 0)
    const input = num(usage, 'input', 'inputTokens', 'input_tokens') ?? 0
    const output = num(usage, 'output', 'outputTokens', 'output_tokens') ?? 0
    const cacheRead =
      num(usage, 'cacheRead', 'cacheReadTokens', 'cache_read', 'cache_read_input_tokens') ?? 0
    const cacheCreation =
      num(
        usage,
        'cacheCreation',
        'cacheCreationTokens',
        'cache_creation',
        'cache_creation_input_tokens',
      ) ?? 0
    const embedding = num(usage, 'embedding', 'embeddingTokens', 'embedding_tokens') ?? 0
    const recordedCost = num(
      usage,
      'displayedCostUsd',
      'cost',
      'costUsd',
      'cost_usd',
      'totalCostUsd',
    )
    return {
      level: text(o, 'level'),
      method: text(o, 'method', 'stage', 'solver', 'agent'),
      model: text(o, 'model', 'backend'),
      language: languageLabel(text(o, 'language', 'lang')),
      input,
      output,
      cacheRead,
      cacheCreation,
      draft,
      embedding,
      total:
        num(usage, 'displayedTotalTokens', 'total', 'totalTokens', 'total_tokens') ??
        input + output + cacheRead + cacheCreation + draft + embedding,
      cost: recordedCost === 0 ? null : recordedCost,
      raw: o,
    }
  })
}

export const normalizePrompts = (raw: unknown): PromptEntry[] =>
  rowsOf(raw).map((o) => ({
    id: text(o, 'id', 'slug', '_key'),
    title: text(o, 'title', 'name'),
    category: text(o, 'category', 'group'),
    role: text(o, 'role', 'type'),
    purpose: text(o, 'purpose', 'description'),
    template: Array.isArray(o.blocks)
      ? o.blocks.map(String).join('\n\n---\n\n')
      : text(o, 'template', 'prompt', 'content'),
    variables: Array.isArray(o.variables) ? o.variables.map(String) : [],
    outputFormat: text(o, 'outputFormat', 'output_format', 'schema'),
    example: text(o, 'example', 'sample'),
  }))

export const taskFiles = [
  'tasks/l0.json',
  'tasks/l1.json',
  'tasks/l2.json',
  'tasks/l3-cpp.json',
  'tasks/l3-go.json',
  'tasks/l3-java.json',
  'tasks/l3-javascript.json',
  'tasks/l3-python.json',
]
