import { useDroppable } from '@dnd-kit/core'
import type { Task, TaskStatus } from '../types'
import TaskCard from './TaskCard'

interface Props {
  status: TaskStatus
  label: string
  tasks: Task[]
  onTaskClick: (task: Task) => void
  criticalPathIds: Set<number>
}

export default function Column({ status, label, tasks, onTaskClick, criticalPathIds }: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: status })

  return (
    <div
      ref={setNodeRef}
      className={`flex-1 min-w-[260px] rounded-xl p-3 transition-colors ${
        isOver ? 'bg-slate-200' : 'bg-slate-50'
      }`}
    >
      <div className="flex items-center justify-between mb-3 px-1">
        <h2 className="font-semibold text-sm text-slate-700 uppercase tracking-wide">{label}</h2>
        <span className="text-xs text-slate-400 bg-white rounded-full px-2 py-0.5 border">
          {tasks.length}
        </span>
      </div>
      <div className="min-h-[60px]">
        {tasks.map((t) => (
          <TaskCard
            key={t.id}
            task={t}
            onClick={() => onTaskClick(t)}
            isOnCriticalPath={criticalPathIds.has(t.id)}
          />
        ))}
        {tasks.length === 0 && (
          <div className="text-xs text-slate-400 italic px-1 py-4 text-center">Drop a task here</div>
        )}
      </div>
    </div>
  )
}
