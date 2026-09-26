import { useState } from 'react'
import { DndContext, type DragEndEvent, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import Column from './Column'
import { COLUMNS, type Task, type TaskStatus } from '../types'
import { api, apiErrorMessage } from '../api/client'

interface Props {
  tasks: Task[]
  setTasks: React.Dispatch<React.SetStateAction<Task[]>>
  onTaskClick: (task: Task) => void
  onAffected: (ids: number[]) => void
  criticalPathIds: Set<number>
}

export default function KanbanBoard({ tasks, setTasks, onTaskClick, onAffected, criticalPathIds }: Props) {
  const [error, setError] = useState<string | null>(null)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over) return

    const taskId = Number(active.id)
    const newStatus = over.id as TaskStatus
    const task = tasks.find((t) => t.id === taskId)
    if (!task || task.status === newStatus) return

    // Optimistic update so the card moves instantly.
    const previousTasks = tasks
    setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t)))

    try {
      const { task: updated, affected_task_ids } = await api.updateTask(taskId, { status: newStatus })
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)))
      if (affected_task_ids.length > 0) onAffected(affected_task_ids)
    } catch (e) {
      setTasks(previousTasks) // roll back the optimistic move
      setError(apiErrorMessage(e, 'Could not move that task.'))
    }
  }

  const tasksByStatus = (status: TaskStatus) => tasks.filter((t) => t.status === status)

  return (
    <div>
      {error && (
        <div className="mb-3 text-sm bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg">
          {error}
        </div>
      )}
      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="flex gap-3 overflow-x-auto pb-2">
          {COLUMNS.map((col) => (
            <Column
              key={col.key}
              status={col.key}
              label={col.label}
              tasks={tasksByStatus(col.key)}
              onTaskClick={onTaskClick}
              criticalPathIds={criticalPathIds}
            />
          ))}
        </div>
      </DndContext>
    </div>
  )
}
