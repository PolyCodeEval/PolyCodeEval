import type { ColumnDef } from '@tanstack/react-table'
import {
  DataTable,
  Field,
  FilterBar,
  NumberValue,
  PageHeader,
  Panel,
} from '../../shared/components'
import { unique, useQueryFilters } from '../../shared/hooks/query'
import type { PromptQualityRow } from '../../shared/types/benchmark'
import { QualityCharts } from './QualityCharts'
import { deriveQualityPageData, useQualityData } from './quality.data'
import type { CommunityQualityRow, QualityFilters } from './quality.types'

const qualityColumns: ColumnDef<PromptQualityRow>[] = [
  { accessorKey: 'taskId', header: 'Task' },
  { accessorKey: 'level', header: 'Level' },
  { accessorKey: 'language', header: 'Language' },
  { accessorKey: 'project', header: 'Project' },
  { accessorKey: 'judge', header: 'Judge' },
  {
    accessorKey: 'score',
    header: 'Score',
    cell: (cell) => <NumberValue value={cell.getValue() as number | null} />,
  },
]

const initialFilters: QualityFilters = { level: '', language: '', project: '', judge: '' }

const communityQualityColumns: ColumnDef<CommunityQualityRow>[] = [
  { accessorKey: 'submissionId', header: 'Submission' },
  { accessorKey: 'submitter', header: 'Submitter' },
  { accessorKey: 'level', header: 'Level' },
  { accessorKey: 'method', header: 'Method' },
  { accessorKey: 'model', header: 'Model' },
  ...(['correctness', 'faithfulness', 'architecture', 'health', 'overall'] as const).map(
    (field) => ({
      accessorKey: field,
      header: field.charAt(0).toUpperCase() + field.slice(1),
      cell: (cell: { getValue: () => unknown }) => (
        <NumberValue value={cell.getValue() as number | null} />
      ),
    }),
  ),
]

export function QualityPage() {
  const { coverage, quality, communityQuality } = useQualityData()
  const { filters, update, reset } = useQueryFilters(initialFilters)
  const pageData = deriveQualityPageData(coverage.data, quality.data, filters)

  return (
    <>
      <PageHeader
        eyebrow="Input and test quality"
        title="Quality & Coverage"
        description="Examine prompt-quality assessments and executable test coverage at project, file, and function granularity."
      />
      <FilterBar onReset={reset}>
        <Field
          label="Level"
          value={filters.level}
          onChange={(value) => update('level', value)}
          options={['L0', 'L1', 'L2', 'L3']}
        />
        <Field
          label="Language"
          value={filters.language}
          onChange={(value) => update('language', value)}
          options={unique([...coverage.data, ...quality.data].map((row) => row.language))}
        />
        <Field
          label="Project"
          value={filters.project}
          onChange={(value) => update('project', value)}
          options={unique([...coverage.data, ...quality.data].map((row) => row.project))}
        />
        <Field
          label="Judge"
          value={filters.judge}
          onChange={(value) => update('judge', value)}
          options={unique(quality.data.map((row) => row.judge))}
        />
      </FilterBar>
      <QualityCharts
        coverage={pageData.coverageDistribution}
        coverageLoading={coverage.loading}
        coverageError={coverage.error}
        promptQuality={pageData.promptQualitySummary}
        promptQualityLoading={quality.loading}
        promptQualityError={quality.error}
      />
      <Panel title="Prompt-quality records">
        <DataTable data={pageData.qualityRows} columns={qualityColumns} name="prompt-quality" />
      </Panel>
      {communityQuality.data.length > 0 && (
        <Panel
          title="Community full-quality results"
          subtitle="Only L0/L1 submissions evaluated with full_quality are included."
        >
          <DataTable
            data={communityQuality.data}
            columns={communityQualityColumns}
            name="community-full-quality"
          />
        </Panel>
      )}
    </>
  )
}
