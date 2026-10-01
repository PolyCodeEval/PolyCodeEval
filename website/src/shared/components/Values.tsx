import type { ReactNode } from 'react'

export function Badge({
  value,
  tone,
}: {
  value: ReactNode
  tone?: 'success' | 'danger' | 'neutral' | 'accent'
}) {
  return <span className={`badge badge-${tone ?? 'neutral'}`}>{value}</span>
}
export function Ratio({ value }: { value: number | null }) {
  return <>{value === null ? '—' : `${(value * 100).toFixed(1)}%`}</>
}
export function NumberValue({ value, digits = 2 }: { value: number | null; digits?: number }) {
  return (
    <>{value === null ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: digits })}</>
  )
}
