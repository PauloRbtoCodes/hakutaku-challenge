import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'

export function useOrgContext() {
  const [context, setContext] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.context()
      setContext(data.context)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return { context, loading, error, refresh: load }
}
