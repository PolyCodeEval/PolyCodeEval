import { FolderTree } from 'lucide-react'

export function ArchivePreview({ entries }: { entries: string[] }) {
  if (!entries.length) return null
  const visible = entries.slice(0, 200)
  return (
    <details className="archive-preview">
      <summary>
        <FolderTree size={15} />
        Archive contents <span>{entries.length.toLocaleString()} entries</span>
      </summary>
      <pre>
        {visible.join('\n')}
        {entries.length > visible.length
          ? `\n... ${entries.length - visible.length} additional entries`
          : ''}
      </pre>
    </details>
  )
}
