import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Task, Dependency } from '../types'

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [dependencies, setDependencies] = useState<Dependency[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [t, d] = await Promise.all([api.listTasks(), api.listDependencies()])
      setTasks(t)
      setDependencies(d)
    } catch (e) {
      setError('Could not reach the TaskFlow Pro API. Is the backend running on port 8000?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { tasks, dependencies, loading, error, refresh, setTasks }
}
