import { Badge, Empty, ErrorState, Loading } from '../../shared/components'
import type { PromptEntry } from '../../shared/types/benchmark'

interface PromptViewerProps {
  prompts: PromptEntry[]
  loading: boolean
  error: string | null
}

export function PromptViewer({ prompts, loading, error }: PromptViewerProps) {
  return (
    <main className="prompt-catalog">
      <div className="section-summary">
        <strong>{prompts.length} prompt entries</strong>
        <span>Templates are displayed verbatim from the published catalog.</span>
      </div>
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorState message={error} />
      ) : prompts.length ? (
        prompts.map((prompt) => <PromptCard key={prompt.id || prompt.title} prompt={prompt} />)
      ) : (
        <Empty />
      )}
    </main>
  )
}

function PromptCard({ prompt }: { prompt: PromptEntry }) {
  return (
    <article className="prompt-card">
      <header>
        <div>
          <span className="eyebrow">{prompt.category}</span>
          <h2>{prompt.title}</h2>
        </div>
        <Badge tone="accent" value={prompt.role || 'Prompt'} />
      </header>
      {prompt.purpose && <p>{prompt.purpose}</p>}
      {prompt.variables.length > 0 && (
        <div className="variables">
          <strong>Variables</strong>
          {prompt.variables.map((variable) => (
            <code key={variable}>{variable}</code>
          ))}
        </div>
      )}
      <pre className="prompt-code">
        <code>{prompt.template || 'No template text is available in this snapshot.'}</code>
      </pre>
      {prompt.outputFormat && (
        <details>
          <summary>Output contract</summary>
          <pre>{prompt.outputFormat}</pre>
        </details>
      )}
      {prompt.example && (
        <details>
          <summary>Example</summary>
          <pre>{prompt.example}</pre>
        </details>
      )}
    </article>
  )
}
