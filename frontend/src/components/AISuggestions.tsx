import { useState } from 'react'
import { api, apiErrorMessage } from '../api/client'
import type { AISuggestion } from '../types'

interface Props {
  taskId: number
  title: string
  description: string
  onAccepted: () => void
}

export default function AISuggestions({ taskId, title, description, onAccepted }: Props) {
  const [suggestions, setSuggestions] = useState<AISuggestion[]>([])
  const [mode, setMode] = useState<'live' | 'mock' | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState<Set<number>>(new Set())
  const [accepting, setAccepting] = useState<number | null>(null)

  async function fetchSuggestions() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.suggestDependencies({ task_id: taskId, title, description })
      setSuggestions(res.suggestions)
      setMode(res.mode)
      setDismissed(new Set())
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not get suggestions right now.'))
    } finally {
      setLoading(false)
    }
  }

  async function accept(suggestion: AISuggestion) {
    setAccepting(suggestion.task_id)
    setError(null)
    try {
      // This goes through the exact same endpoint (and cycle check) as
      // a manually drawn dependency -- the AI never writes to the
      // graph directly, only the deterministic engine does.
      await api.createDependency(suggestion.task_id, taskId)
      setDismissed((prev) => new Set(prev).add(suggestion.task_id))
      onAccepted()
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not add that dependency (it may create a cycle).'))
    } finally {
      setAccepting(null)
    }
  }

  function reject(taskId: number) {
    setDismissed((prev) => new Set(prev).add(taskId))
  }

  const visible = suggestions.filter((s) => !dismissed.has(s.task_id))

  return (
    <div className="mt-4 border-t pt-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">AI Dependency Suggestions</h3>
        <button
          onClick={fetchSuggestions}
          disabled={loading}
          className="text-xs px-2 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? 'Thinking…' : 'Suggest Dependencies'}
        </button>
      </div>

      {mode === 'mock' && (
        <p className="text-[11px] text-amber-600 mt-2">
          Running in mock mode (no ANTHROPIC_API_KEY set on the backend) — showing the closest
          text match instead of a live model call.
        </p>
      )}
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}

      {visible.length === 0 && mode !== null && !loading && (
        <p className="text-xs text-slate-400 mt-2">No candidate prerequisites suggested.</p>
      )}

      <ul className="mt-2 space-y-2">
        {visible.map((s) => (
          <li key={s.task_id} className="bg-indigo-50 border border-indigo-200 rounded-lg p-2 text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-indigo-900">
                Suggested prerequisite: {s.title}
              </span>
              <span className="text-indigo-400">match {Math.round(s.similarity_score * 100)}%</span>
            </div>
            <p className="text-indigo-700 mt-1">{s.reason}</p>
            <div className="mt-2 flex gap-2">
              <button
                onClick={() => accept(s)}
                disabled={accepting === s.task_id}
                className="px-2 py-1 rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
              >
                Accept
              </button>
              <button
                onClick={() => reject(s.task_id)}
                className="px-2 py-1 rounded bg-slate-200 text-slate-700 hover:bg-slate-300"
              >
                Reject
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
