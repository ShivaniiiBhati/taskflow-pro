import { useState } from 'react'
import { api, apiErrorMessage } from '../api/client'
import type { Task, Dependency } from '../types'
import AISuggestions from './AISuggestions'

interface Props {
  task: Task
  allTasks: Task[]
  dependencies: Dependency[]
  onClose: () => void
  onRefresh: () => void
  onAffected: (ids: number[]) => void
}

export default function TaskModal({ task, allTasks, dependencies, onClose, onRefresh, onAffected }: Props) {
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description)
  const [startDate, setStartDate] = useState(task.start_date)
  const [durationDays, setDurationDays] = useState(task.duration_days)
  const [selectedPredecessor, setSelectedPredecessor] = useState<number | ''>('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const predecessorEdges = dependencies.filter((d) => d.successor_id === task.id)
  const predecessorTasks = predecessorEdges
    .map((edge) => ({ edge, task: allTasks.find((t) => t.id === edge.predecessor_id) }))
    .filter((x) => x.task)

  const candidateOptions = allTasks.filter(
    (t) => t.id !== task.id && !predecessorEdges.some((e) => e.predecessor_id === t.id),
  )

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const { affected_task_ids } = await api.updateTask(task.id, {
        title,
        description,
        start_date: startDate,
        duration_days: durationDays,
      })
      if (affected_task_ids.length > 0) onAffected(affected_task_ids)
      onRefresh()
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not save changes.'))
    } finally {
      setSaving(false)
    }
  }

  async function addDependency() {
    if (selectedPredecessor === '') return
    setError(null)
    try {
      await api.createDependency(Number(selectedPredecessor), task.id)
      setSelectedPredecessor('')
      onRefresh()
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not add that dependency.'))
    }
  }

  async function removeDependency(edgeId: number) {
    setError(null)
    try {
      await api.deleteDependency(edgeId)
      onRefresh()
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not remove that dependency.'))
    }
  }

  async function remove() {
    if (!confirm(`Delete "${task.title}"? This also removes its dependency edges.`)) return
    try {
      await api.deleteTask(task.id)
      onRefresh()
      onClose()
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not delete this task.'))
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-5">
        <div className="flex justify-between items-start mb-3">
          <span className="text-xs text-slate-400">#TASK-{task.id}</span>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-lg leading-none">
            ×
          </button>
        </div>

        {error && (
          <div className="mb-3 text-xs bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg">
            {error}
          </div>
        )}

        <input
          className="w-full font-semibold text-lg border-b pb-1 mb-3 focus:outline-none focus:border-indigo-500"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        <textarea
          className="w-full text-sm border rounded-lg p-2 mb-3 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />

        <div className="flex gap-3 mb-3">
          <label className="flex-1 text-xs text-slate-500">
            Start date
            <input
              type="date"
              className="w-full border rounded-lg p-1.5 mt-1 text-sm"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </label>
          <label className="flex-1 text-xs text-slate-500">
            Duration (days)
            <input
              type="number"
              min={1}
              className="w-full border rounded-lg p-1.5 mt-1 text-sm"
              value={durationDays}
              onChange={(e) => setDurationDays(Number(e.target.value))}
            />
          </label>
        </div>

        <div className="flex gap-2 mb-4">
          <button
            onClick={save}
            disabled={saving}
            className="px-3 py-1.5 text-sm rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save changes'}
          </button>
          <button onClick={remove} className="px-3 py-1.5 text-sm rounded-lg bg-red-50 text-red-600 hover:bg-red-100">
            Delete task
          </button>
        </div>

        <div className="border-t pt-3">
          <h3 className="text-sm font-semibold text-slate-700 mb-2">
            Prerequisites ({predecessorTasks.length})
          </h3>
          {predecessorTasks.length === 0 && (
            <p className="text-xs text-slate-400 mb-2">No prerequisites — this task is unblocked by nothing.</p>
          )}
          <ul className="space-y-1 mb-2">
            {predecessorTasks.map(({ edge, task: p }) => (
              <li key={edge.id} className="flex items-center justify-between text-xs bg-slate-50 rounded-lg px-2 py-1.5">
                <span>
                  {p!.title}{' '}
                  <span className={p!.status === 'DONE' ? 'text-green-600' : 'text-slate-400'}>
                    ({p!.status})
                  </span>
                </span>
                <button onClick={() => removeDependency(edge.id)} className="text-red-500 hover:text-red-700">
                  Remove
                </button>
              </li>
            ))}
          </ul>

          <div className="flex gap-2">
            <select
              className="flex-1 text-xs border rounded-lg p-1.5"
              value={selectedPredecessor}
              onChange={(e) => setSelectedPredecessor(e.target.value ? Number(e.target.value) : '')}
            >
              <option value="">Add a prerequisite…</option>
              {candidateOptions.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title}
                </option>
              ))}
            </select>
            <button
              onClick={addDependency}
              disabled={selectedPredecessor === ''}
              className="px-2 py-1 text-xs rounded-lg bg-slate-700 text-white hover:bg-slate-800 disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </div>

        <AISuggestions taskId={task.id} title={title} description={description} onAccepted={onRefresh} />
      </div>
    </div>
  )
}
