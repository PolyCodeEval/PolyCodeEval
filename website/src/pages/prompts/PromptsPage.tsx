import { Field, FilterBar, PageHeader, Panel } from '../../shared/components'
import { unique, useQueryFilters } from '../../shared/hooks/query'
import { PromptViewer } from './PromptViewer'
import {
  filterPromptEntries,
  reproductionCommands,
  reproductionSteps,
  usePromptData,
} from './prompts.data'
import type { PromptFilters } from './prompts.types'

const initialFilters: PromptFilters = { category: '', role: '', search: '' }

export function PromptsPage() {
  const source = usePromptData()
  const { filters, update, reset } = useQueryFilters(initialFilters)
  const prompts = filterPromptEntries(source.data, filters)

  return (
    <>
      <PageHeader
        eyebrow="Experimental inputs"
        title="Prompts & Reproduction"
        description="Review the preserved prompt catalog, output contracts, and the reproducible evaluation workflow."
      />
      <FilterBar onReset={reset}>
        <Field
          label="Search"
          value={filters.search}
          onChange={(value) => update('search', value)}
          placeholder="Prompt title or content"
        />
        <Field
          label="Category"
          value={filters.category}
          onChange={(value) => update('category', value)}
          options={unique(source.data.map((prompt) => prompt.category))}
        />
        <Field
          label="Role"
          value={filters.role}
          onChange={(value) => update('role', value)}
          options={unique(source.data.map((prompt) => prompt.role))}
        />
      </FilterBar>
      <div className="prompt-layout">
        <aside className="reproduction">
          <Panel title="Reproduction workflow">
            <ol className="repro-steps">
              {reproductionSteps.map(([title, description], index) => (
                <li key={title}>
                  <span>{index + 1}</span>
                  <div>
                    <strong>{title}</strong>
                    <p>{description}</p>
                  </div>
                </li>
              ))}
            </ol>
          </Panel>
          <Panel title="Canonical commands">
            <pre className="command-code">
              <code>{reproductionCommands}</code>
            </pre>
          </Panel>
          <Panel title="Publish evaluated results">
            <p>
              Run the evaluator locally, preserve its native JSON output, and validate the result
              package before opening a community pull request.
            </p>
            <div className="page-actions">
              <a className="button button-quiet" href="#/downloads">
                Evaluation resources
              </a>
              <a className="button button-primary" href="#/submit">
                Submit Results
              </a>
            </div>
          </Panel>
          <Panel title="Dataset card">
            <p>
              PolyCodeEval supports research on execution-based repository-level code generation
              across Python, JavaScript, Java, Go, and C++. It is intended for model and method
              evaluation under controlled, auditable task construction.
            </p>
            <p>
              Repository licenses, tests, build behavior, project scale, language-specific tooling,
              and provider APIs define the dataset's practical scope. Results should be interpreted
              within these boundaries.
            </p>
          </Panel>
        </aside>
        <PromptViewer prompts={prompts} loading={source.loading} error={source.error} />
      </div>
    </>
  )
}
