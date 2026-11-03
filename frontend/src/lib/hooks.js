import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'

// Fetch JSON for a path/params; refetches when they change. Optional polling while the tab is visible.
export function useApi(path, params, { poll = 0, skip = false } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(!skip)
  const key = path + JSON.stringify(params || {})
  const keyRef = useRef(key)
  keyRef.current = key

  const load = useCallback(async (silent = false) => {
    if (skip || !path) return
    if (!silent) setLoading(true)
    try {
      const d = await api.get(path, params)
      if (keyRef.current === key) { setData(d); setError(null) }
    } catch (e) {
      if (keyRef.current === key) setError(e)
    } finally {
      if (keyRef.current === key) setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, skip])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!poll) return
    const id = setInterval(() => { if (document.visibilityState === 'visible') load(true) }, poll)
    const onVis = () => document.visibilityState === 'visible' && load(true)
    document.addEventListener('visibilitychange', onVis)
    return () => { clearInterval(id); document.removeEventListener('visibilitychange', onVis) }
  }, [poll, load])

  return { data, error, loading, reload: load, setData }
}

export function useDebounced(value, ms = 250) {
  const [v, setV] = useState(value)
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t) }, [value, ms])
  return v
}
