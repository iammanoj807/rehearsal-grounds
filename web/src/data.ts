import { useCallback, useEffect, useState } from 'react'

/** URL of a file in public/data, respecting the deploy base path. */
export function dataUrl(path: string): string {
  return `${import.meta.env.BASE_URL}data/${path}`
}

const cache = new Map<string, Promise<unknown>>()

function fetchJson<T>(path: string, force = false): Promise<T> {
  if (force) cache.delete(path)
  let p = cache.get(path) as Promise<T> | undefined
  if (!p) {
    p = fetch(dataUrl(path)).then(async (res) => {
      if (!res.ok) throw new Error(`${res.status} ${res.statusText} while loading ${path}`)
      return (await res.json()) as T
    })
    p.catch(() => cache.delete(path))
    cache.set(path, p)
  }
  return p
}

export interface Loaded<T> {
  data: T | null
  error: string | null
  loading: boolean
  retry: () => void
}

/** Load a JSON file from public/data with loading, error and retry state. */
export function useJson<T>(path: string | null): Loaded<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: path !== null,
  })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (path === null) return
    let alive = true
    setState((s) => ({ ...s, loading: true, error: null }))
    fetchJson<T>(path, attempt > 0)
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((err: unknown) =>
        alive && setState({ data: null, error: err instanceof Error ? err.message : String(err), loading: false }),
      )
    return () => {
      alive = false
    }
  }, [path, attempt])

  const retry = useCallback(() => setAttempt((a) => a + 1), [])
  return { ...state, retry }
}

export const fmt = (value: number | null | undefined, digits = 1, unit = ''): string =>
  value === null || value === undefined || Number.isNaN(value) ? '–' : `${value.toFixed(digits)}${unit}`

export const pct = (value: number | null | undefined, digits = 0): string =>
  value === null || value === undefined ? '–' : `${(value * 100).toFixed(digits)}%`

export const bodyLabel = (body: string): string => (body === 'moon' ? 'Moon' : body === 'mars' ? 'Mars' : 'Earth')

export function latLon(lat: number, lon: number): string {
  const ns = lat >= 0 ? 'N' : 'S'
  const ew = lon >= 0 ? 'E' : 'W'
  return `${Math.abs(lat).toFixed(3)}° ${ns}, ${Math.abs(lon).toFixed(3)}° ${ew}`
}
