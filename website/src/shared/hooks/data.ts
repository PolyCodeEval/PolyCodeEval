import { useEffect, useMemo, useState } from 'react'
import { fetchJson, normalizeResults } from '../lib/benchmark'
import type { LoadState, ResultRow } from '../types/benchmark'

export function useJson<T>(path: string, normalize: (raw: unknown) => T, initial: T): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({ data: initial, loading: true, error: null })
  useEffect(() => {
    const controller = new AbortController()
    setState((s) => ({ ...s, loading: true, error: null }))
    fetchJson(path, controller.signal)
      .then((raw) => setState({ data: normalize(raw), loading: false, error: null }))
      .catch((error) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState({
          data: initial,
          loading: false,
          error: `${path}: ${error instanceof Error ? error.message : String(error)}`,
        })
      })
    return () => controller.abort()
  }, [path])
  return state
}

export function useFirstJson<T>(
  paths: string[],
  normalize: (raw: unknown) => T,
  initial: T,
): LoadState<T> {
  const key = paths.join('|')
  const [state, setState] = useState<LoadState<T>>({ data: initial, loading: true, error: null })
  useEffect(() => {
    const controller = new AbortController()
    const run = async () => {
      const errors: string[] = []
      for (const path of paths) {
        try {
          setState((s) => ({ ...s, loading: true, error: null }))
          const raw = await fetchJson(path, controller.signal)
          setState({ data: normalize(raw), loading: false, error: null })
          return
        } catch (error) {
          if (error instanceof DOMException && error.name === 'AbortError') return
          errors.push(`${path}: ${error instanceof Error ? error.message : String(error)}`)
        }
      }
      setState({ data: initial, loading: false, error: errors.join('; ') })
    }
    run()
    return () => controller.abort()
  }, [key])
  return state
}

const l3Files: Record<string, string> = {
  'C++': 'cpp',
  Go: 'go',
  Java: 'java',
  JavaScript: 'javascript',
  Python: 'python',
}

export function useTaskResults(level: string, language = ''): LoadState<ResultRow[]> {
  const files = useMemo(() => {
    if (level !== 'L3')
      return [
        `results/tasks/${level.toLowerCase()}.json`,
        `community/tasks/${level.toLowerCase()}.json`,
      ]
    if (language && l3Files[language])
      return [
        `results/tasks/l3-${l3Files[language]}.json`,
        `community/tasks/l3-${l3Files[language]}.json`,
      ]
    return Object.values(l3Files).flatMap((v) => [
      `results/tasks/l3-${v}.json`,
      `community/tasks/l3-${v}.json`,
    ])
  }, [level, language])
  const key = files.join('|')
  const [state, setState] = useState<LoadState<ResultRow[]>>({
    data: [],
    loading: true,
    error: null,
  })
  useEffect(() => {
    const controller = new AbortController()
    setState({ data: [], loading: true, error: null })
    Promise.allSettled(files.map((path) => fetchJson(path, controller.signal))).then((results) => {
      const rows = results.flatMap((result, index) =>
        result.status === 'fulfilled'
          ? normalizeResults(result.value, {
              level,
              language: level === 'L3' && language ? language : '',
            })
          : [],
      )
      const failures = results.flatMap((result, index) =>
        result.status === 'rejected'
          ? [
              `${files[index]}: ${result.reason instanceof Error ? result.reason.message : String(result.reason)}`,
            ]
          : [],
      )
      setState({
        data: rows,
        loading: false,
        error: rows.length ? null : failures.join('; ') || null,
      })
    })
    return () => controller.abort()
  }, [key, level, language])
  return state
}
