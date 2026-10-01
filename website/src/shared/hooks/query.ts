import { useEffect, useMemo, useState } from 'react'

type StringState<T> = { [K in keyof T]: string }

export function useQueryFilters<T extends StringState<T>>(defaults: T) {
  const read = () => {
    const query = window.location.hash.split('?')[1] ?? ''
    const params = new URLSearchParams(query)
    const keys = Object.keys(defaults) as Array<keyof T & string>
    return Object.fromEntries(keys.map((key) => [key, params.get(key) ?? defaults[key]])) as T
  }
  const [filters, setFilters] = useState<T>(read)
  useEffect(() => {
    const sync = () => setFilters(read())
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])
  const update = (key: keyof T, value: string) => {
    const next = { ...filters, [key]: value }
    setFilters(next)
    const [path] = window.location.hash.split('?')
    const params = new URLSearchParams()
    Object.entries(next).forEach(([k, v]) => v && params.set(k, v))
    history.replaceState(
      null,
      '',
      `${location.pathname}${location.search}${path}${params.size ? `?${params}` : ''}`,
    )
  }
  const reset = () => {
    setFilters(defaults)
    const [path] = window.location.hash.split('?')
    history.replaceState(null, '', `${location.pathname}${location.search}${path}`)
  }
  return { filters, update, reset }
}
export const unique = (values: string[]) =>
  [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b))
export function useFiltered<T>(
  rows: T[],
  filters: Record<string, string>,
  fields: Record<string, (row: T) => unknown>,
) {
  return useMemo(
    () =>
      rows.filter((row) =>
        Object.entries(filters).every(([key, expected]) => {
          if (!expected) return true
          const actual = fields[key]?.(row)
          if (key === 'search')
            return String(actual ?? '')
              .toLowerCase()
              .includes(expected.toLowerCase())
          return String(actual ?? '').toLowerCase() === expected.toLowerCase()
        }),
      ),
    [rows, filters, fields],
  )
}
