import { useMemo } from 'react'
import type { Task, Dependency } from '../types'

interface Props {
  tasks: Task[]
  dependencies: Dependency[]
  criticalPathIds: Set<number>
}

const NODE_W = 150
const NODE_H = 56
const COL_GAP = 90
const ROW_GAP = 24

const STATUS_FILL: Record<string, string> = {
  READY_BACKLOG: '#dcfce7', // light green
  BLOCKED: '#fee2e2', // light red
  IN_PROGRESS: '#dbeafe', // light blue
  DONE: '#e5e7eb', // light gray
}

function fillFor(task: Task): string {
  if (task.status === 'DONE') return STATUS_FILL.DONE
  if (task.status === 'IN_PROGRESS') return STATUS_FILL.IN_PROGRESS
  if (task.readiness === 'BLOCKED') return STATUS_FILL.BLOCKED
  return STATUS_FILL.READY_BACKLOG
}

/**
 * Assigns each task a "level" = the length of the longest chain of
 * prerequisites leading to it (0 for tasks with no predecessors).
 * This is purely a layout computation for drawing left-to-right --
 * it is NOT the scheduling engine (that lives entirely on the
 * backend); the graph view just needs *some* topological ordering to
 * lay nodes out without crossing arrows backwards.
 */
function computeLevels(tasks: Task[], dependencies: Dependency[]): Map<number, number> {
  const predecessorsOf = new Map<number, number[]>()
  tasks.forEach((t) => predecessorsOf.set(t.id, []))
  dependencies.forEach((d) => {
    predecessorsOf.get(d.successor_id)?.push(d.predecessor_id)
  })

  const levels = new Map<number, number>()
  const visiting = new Set<number>()

  function levelOf(taskId: number): number {
    if (levels.has(taskId)) return levels.get(taskId)!
    if (visiting.has(taskId)) return 0 // guards against a stray cycle in stale data
    visiting.add(taskId)
    const preds = predecessorsOf.get(taskId) ?? []
    const level = preds.length === 0 ? 0 : 1 + Math.max(...preds.map(levelOf))
    visiting.delete(taskId)
    levels.set(taskId, level)
    return level
  }

  tasks.forEach((t) => levelOf(t.id))
  return levels
}

export default function DependencyGraph({ tasks, dependencies, criticalPathIds }: Props) {
  const { positions, width, height } = useMemo(() => {
    const levels = computeLevels(tasks, dependencies)
    const byLevel = new Map<number, Task[]>()
    tasks.forEach((t) => {
      const lvl = levels.get(t.id) ?? 0
      if (!byLevel.has(lvl)) byLevel.set(lvl, [])
      byLevel.get(lvl)!.push(t)
    })

    const positions = new Map<number, { x: number; y: number }>()
    let maxLevel = 0
    let maxRows = 1
    byLevel.forEach((tasksInLevel, lvl) => {
      maxLevel = Math.max(maxLevel, lvl)
      maxRows = Math.max(maxRows, tasksInLevel.length)
      tasksInLevel.forEach((t, row) => {
        positions.set(t.id, {
          x: lvl * (NODE_W + COL_GAP) + 20,
          y: row * (NODE_H + ROW_GAP) + 20,
        })
      })
    })

    return {
      positions,
      width: (maxLevel + 1) * (NODE_W + COL_GAP) + 40,
      height: maxRows * (NODE_H + ROW_GAP) + 40,
    }
  }, [tasks, dependencies])

  const isCriticalEdge = (predId: number, succId: number) =>
    criticalPathIds.has(predId) && criticalPathIds.has(succId)

  return (
    <div className="overflow-auto border rounded-xl bg-white p-4">
      <svg width={Math.max(width, 400)} height={Math.max(height, 200)}>
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
          </marker>
          <marker id="arrow-critical" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
          </marker>
        </defs>

        {dependencies.map((d) => {
          const from = positions.get(d.predecessor_id)
          const to = positions.get(d.successor_id)
          if (!from || !to) return null
          const critical = isCriticalEdge(d.predecessor_id, d.successor_id)
          const x1 = from.x + NODE_W
          const y1 = from.y + NODE_H / 2
          const x2 = to.x
          const y2 = to.y + NODE_H / 2
          const midX = (x1 + x2) / 2
          return (
            <path
              key={d.id}
              d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
              fill="none"
              stroke={critical ? '#f59e0b' : '#94a3b8'}
              strokeWidth={critical ? 2.5 : 1.5}
              markerEnd={critical ? 'url(#arrow-critical)' : 'url(#arrow)'}
            />
          )
        })}

        {tasks.map((t) => {
          const pos = positions.get(t.id)
          if (!pos) return null
          const critical = criticalPathIds.has(t.id)
          return (
            <g key={t.id} transform={`translate(${pos.x}, ${pos.y})`}>
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={8}
                fill={fillFor(t)}
                stroke={critical ? '#f59e0b' : '#cbd5e1'}
                strokeWidth={critical ? 2.5 : 1}
              />
              <text x={8} y={20} fontSize={11} fontWeight={600} fill="#1e293b">
                {t.title.length > 20 ? t.title.slice(0, 19) + '…' : t.title}
              </text>
              <text x={8} y={36} fontSize={9} fill="#475569">
                {t.status}{t.status !== 'DONE' ? ` · ${t.readiness}` : ''}
              </text>
              <text x={8} y={48} fontSize={9} fill="#94a3b8">
                {t.start_date} → {t.end_date}
              </text>
            </g>
          )
        })}
      </svg>

      <div className="flex gap-4 mt-3 text-xs text-slate-500 flex-wrap">
        <Legend swatch={STATUS_FILL.READY_BACKLOG} label="Ready" />
        <Legend swatch={STATUS_FILL.BLOCKED} label="Blocked" />
        <Legend swatch={STATUS_FILL.IN_PROGRESS} label="In Progress" />
        <Legend swatch={STATUS_FILL.DONE} label="Done" />
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 h-0.5 bg-amber-500" /> Critical path
        </span>
      </div>
    </div>
  )
}

function Legend({ swatch, label }: { swatch: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: swatch }} />
      {label}
    </span>
  )
}
