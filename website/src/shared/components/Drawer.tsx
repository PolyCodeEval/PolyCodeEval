import { useEffect, type ReactNode } from 'react'
import { ExternalLink, X } from 'lucide-react'

export function Drawer({
  title,
  open,
  onClose,
  children,
}: {
  title: string
  open: boolean
  onClose: () => void
  children: ReactNode
}) {
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [onClose])
  if (!open) return null
  return (
    <div className="drawer-layer" role="dialog" aria-modal="true" aria-label={title}>
      <button className="drawer-scrim" onClick={onClose} aria-label="Close details" />
      <aside className="drawer">
        <header>
          <h2>{title}</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close details">
            <X size={20} />
          </button>
        </header>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  )
}

export function DetailList({ entries }: { entries: Array<[string, ReactNode]> }) {
  return (
    <dl className="detail-list">
      {entries.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v || '—'}</dd>
        </div>
      ))}
    </dl>
  )
}
export function SourceLink({ href, label = 'Source JSON' }: { href: string; label?: string }) {
  return href ? (
    <a className="text-link" href={href} target="_blank" rel="noreferrer">
      {label} <ExternalLink size={14} />
    </a>
  ) : (
    <span className="muted">No source link</span>
  )
}
export function RawJson({ value }: { value: unknown }) {
  return (
    <details className="raw">
      <summary>Raw record</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  )
}
