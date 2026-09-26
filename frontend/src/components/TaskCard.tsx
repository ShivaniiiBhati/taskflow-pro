import { useDraggable } from '@dnd-kit/core'
import type { Task } from '../types'

const READINESS_STYLES: Record<Task['readiness'], string> = {
  READY: 'bg-green-100 text-green-800 border border-green-300',
  BLOCKED: 'bg-red-100 text-red-800 border border-red-300',
}

interface Props {
  task: Task
  onClick: () => void
  isOnCriticalPath: boolean
}

export default function TaskCard({ task, onClick, isOnCriticalPath }: Props) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
  })

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      onClick={onClick}
      className={`card-shadow rounded-lg bg-white p-3 mb-2 cursor-pointer select-none
        border-l-4 ${isOnCriticalPath ? 'border-l-amber-500' : 'border-l-transparent'}
        ${isDragging ? 'opacity-50' : 'opacity-100'}
        hover:shadow-md transition-shadow`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-medium text-sm text-slate-800">{task.title}</span>
        <span className="text-xs text-slate-400 shrink-0">#{task.id}</span>
      </div>

      {task.status !== 'DONE' && (
        <span
          className={`inline-block mt-2 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full ${READINESS_STYLES[task.readiness]}`}
        >
          {task.readiness === 'READY' ? '● Ready' : '● Blocked'}
        </span>
      )}
      {task.status === 'DONE' && task.readiness === 'BLOCKED' && (
        <span
          className="inline-block mt-2 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300"
          title="A prerequisite regressed after this task was marked Done."
        >
          ● Done, prerequisite at risk
        </span>
      )}

      <div className="mt-2 text-[11px] text-slate-500 flex justify-between">
        <span>{task.start_date} → {task.end_date}</span>
        <span>{task.dependency_count} dep{task.dependency_count === 1 ? '' : 's'}</span>
      </div>
    </div>
  )
}
