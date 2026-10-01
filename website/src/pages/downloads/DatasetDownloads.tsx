import { Copy, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { datasets } from './downloads.data'

export function DatasetDownloads() {
  const [copied, setCopied] = useState('')
  const copy = async (id: string, value: string) => {
    await navigator.clipboard.writeText(value)
    setCopied(id)
    window.setTimeout(() => setCopied(''), 1200)
  }
  return (
    <div className="dataset-download-grid">
      {datasets.map((dataset) => {
        const Icon = dataset.icon
        const command = `python docker/sync_datasets.py pull --language ${dataset.id}`
        return (
          <article className="dataset-download" key={dataset.id}>
            <header>
              <span className="dataset-icon">
                <Icon size={18} />
              </span>
              <div>
                <strong>{dataset.label}</strong>
                <small>{dataset.repositories} repositories</small>
              </div>
              <a
                href={`https://hub.docker.com/r/${dataset.image}`}
                target="_blank"
                rel="noreferrer"
                title="Open DockerHub image"
                aria-label={`Open ${dataset.label} image on DockerHub`}
              >
                <ExternalLink size={16} />
              </a>
            </header>
            <div className="command-row">
              <code>{command}</code>
              <button
                className="icon-button"
                onClick={() => copy(dataset.id, command)}
                title="Copy command"
                aria-label={`Copy ${dataset.label} download command`}
              >
                <Copy size={15} />
              </button>
            </div>
            {copied === dataset.id && <span className="copy-status">Copied</span>}
          </article>
        )
      })}
    </div>
  )
}
