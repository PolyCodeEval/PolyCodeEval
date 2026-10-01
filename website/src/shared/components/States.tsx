import { AlertCircle, LoaderCircle, Search } from 'lucide-react'

export function Loading({ label = 'Loading data' }: { label?: string }) {
  return (
    <div className="state">
      <LoaderCircle className="spin" size={22} />
      <span>{label}</span>
    </div>
  )
}
export function Empty({
  title = 'No data available',
  message = 'The current data snapshot contains no matching records.',
}: {
  title?: string
  message?: string
}) {
  return (
    <div className="state state-column">
      <Search size={25} />
      <strong>{title}</strong>
      <span>{message}</span>
    </div>
  )
}
export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state state-error">
      <AlertCircle size={22} />
      <div>
        <strong>Unable to load this dataset</strong>
        <span>{message}</span>
      </div>
    </div>
  )
}
