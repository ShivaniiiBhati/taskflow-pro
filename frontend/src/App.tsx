import { useEffect, useState } from 'react'
import KanbanBoard from './components/KanbanBoard'
import DependencyGraph from './components/DependencyGraph'
import TaskModal from './components/TaskModal'
import { useTasks } from './hooks/useTasks'
import { api, apiErrorMessage } from './api/client'
import type { Task, CriticalPath } from './types'

type Tab = 'board' | 'graph'

export default function App() {
  const { tasks, dependencies, loading, error, refresh, setTasks } = useTasks()
  const [tab, setTab] = useState<Tab>('board')
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [showNewTask, setShowNewTask] = useState(false)
  const [criticalPath, setCriticalPath] = useState<CriticalPath | null>(null)
  const [showCriticalPath, setShowCriticalPath] = useState(false)

  // New-task form state
  const [newTitle, setNewTitle] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [newStart, setNewStart] = useState(new Date().toISOString().slice(0, 10))
  const [newDuration, setNewDuration] = useState(1)
  const [createError, setCreateError] = useState<string | null>(null)

  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 4000)
      return () => clearTimeout(t)
    }
  }, [toast])

  // Keep the modal's task in sync with the latest fetched list.
  useEffect(() => {
    if (selectedTask) {
      const fresh = tasks.find((t: Task) => t.id === selectedTask.id)
      if (fresh) setSelectedTask(fresh)
    }
  }, [tasks]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleAffected(ids: number[]) {
    if (ids.length === 0) return
    setToast(`Propagated to ${ids.length} downstream task${ids.length === 1 ? '' : 's'}.`)
    refresh()
  }

  async function loadCriticalPath() {
    try {
      const cp = await api.criticalPath()
      setCriticalPath(cp)
      setShowCriticalPath(true)
    } catch {
      setToast('Could not compute the critical path.')
    }
  }

  async function createTask() {
    setCreateError(null)
    if (!newTitle.trim()) {
      setCreateError('Title is required.')
      return
    }
    try {
      await api.createTask({
        title: newTitle,
        description: newDescription,
        start_date: newStart,
        duration_days: newDuration,
      })
      setNewTitle('')
      setNewDescription('')
      setNewDuration(1)
      setShowNewTask(false)
      refresh()
    } catch (e) {
      setCreateError(apiErrorMessage(e, 'Could not create task.'))
    }
  }

  const criticalPathIds = new Set<number>(showCriticalPath ? criticalPath?.task_ids ?? [] : [])

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-7xl mx-auto">
      <header className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h1 className="text-xl font-bold text-slate-900">TaskFlow Pro</h1>
          <p className="text-xs text-slate-500">Dependency-aware workflow &amp; DAG scheduling engine</p>
        </div>
        <div className="flex gap-2 items-center">
          <div className="flex bg-slate-200 rounded-lg p-1 text-sm">
            <button
              onClick={() => setTab('board')}
              className={`px-3 py-1 rounded-md ${tab === 'board' ? 'bg-white shadow font-medium' : 'text-slate-600'}`}
            >
              Board
            </button>
            <button
              onClick={() => setTab('graph')}
              className={`px-3 py-1 rounded-md ${tab === 'graph' ? 'bg-white shadow font-medium' : 'text-slate-600'}`}
            >
              Dependency Graph
            </button>
          </div>
          {tab === 'graph' && (
            <button
              onClick={showCriticalPath ? () => setShowCriticalPath(false) : loadCriticalPath}
              className={`text-sm px-3 py-1.5 rounded-lg border ${
                showCriticalPath ? 'bg-amber-500 text-white border-amber-500' : 'bg-white border-slate-300'
              }`}
            >
              {showCriticalPath ? 'Hide critical path' : 'Show critical path'}
            </button>
          )}
          <button
            onClick={() => setShowNewTask(true)}
            className="text-sm px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700"
          >
            + New Task
          </button>
        </div>
      </header>

      {error && <div className="mb-4 text-sm bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg">{error}</div>}
      {loading && <p className="text-sm text-slate-500">Loading board…</p>}

      {!loading && !error && tab === 'board' && (
        <KanbanBoard
          tasks={tasks}
          setTasks={setTasks}
          onTaskClick={setSelectedTask}
          onAffected={handleAffected}
          criticalPathIds={criticalPathIds}
        />
      )}

      {!loading && !error && tab === 'graph' && (
        <DependencyGraph tasks={tasks} dependencies={dependencies} criticalPathIds={criticalPathIds} />
      )}

      {selectedTask && (
        <TaskModal
          task={selectedTask}
          allTasks={tasks}
          dependencies={dependencies}
          onClose={() => setSelectedTask(null)}
          onRefresh={refresh}
          onAffected={handleAffected}
        />
      )}

      {showNewTask && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-5">
            <h2 className="font-semibold text-lg mb-3">New Task</h2>
            {createError && <p className="text-xs text-red-600 mb-2">{createError}</p>}
            <input
              className="w-full border rounded-lg p-2 mb-2 text-sm"
              placeholder="Title"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
            />
            <textarea
              className="w-full border rounded-lg p-2 mb-2 text-sm"
              placeholder="Description"
              rows={3}
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
            />
            <div className="flex gap-2 mb-3">
              <label className="flex-1 text-xs text-slate-500">
                Start date
                <input
                  type="date"
                  className="w-full border rounded-lg p-1.5 mt-1 text-sm"
                  value={newStart}
                  onChange={(e) => setNewStart(e.target.value)}
                />
              </label>
              <label className="flex-1 text-xs text-slate-500">
                Duration (days)
                <input
                  type="number"
                  min={1}
                  className="w-full border rounded-lg p-1.5 mt-1 text-sm"
                  value={newDuration}
                  onChange={(e) => setNewDuration(Number(e.target.value))}
                />
              </label>
            </div>
            <div className="flex gap-2">
              <button onClick={createTask} className="px-3 py-1.5 text-sm rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">
                Create
              </button>
              <button
                onClick={() => setShowNewTask(false)}
                className="px-3 py-1.5 text-sm rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200"
              >
                Cancel
              </button>
            </div>
            <p className="text-[11px] text-slate-400 mt-3">
              You can add prerequisite dependencies and get AI suggestions after creating the task.
            </p>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-4 right-4 bg-slate-900 text-white text-sm px-4 py-2 rounded-lg shadow-lg">
          {toast}
        </div>
      )}
    </div>
  )
}
