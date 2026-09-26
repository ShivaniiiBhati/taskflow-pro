export type TaskStatus = 'BACKLOG' | 'IN_PROGRESS' | 'REVIEW' | 'DONE'
export type Readiness = 'READY' | 'BLOCKED'

export interface Task {
  id: number
  title: string
  description: string
  status: TaskStatus
  readiness: Readiness
  start_date: string
  end_date: string
  duration_days: number
  dependency_count: number
  created_at: string | null
  updated_at: string | null
}

export interface TaskUpdateResponse {
  task: Task
  affected_task_ids: number[]
}

export interface Dependency {
  id: number
  predecessor_id: number
  successor_id: number
  created_at: string | null
}

export interface CriticalPath {
  task_ids: number[]
  total_duration_days: number
}

export interface AISuggestion {
  task_id: number
  title: string
  reason: string
  similarity_score: number
}

export interface AISuggestResponse {
  suggestions: AISuggestion[]
  mode: 'live' | 'mock'
}

export const COLUMNS: { key: TaskStatus; label: string }[] = [
  { key: 'BACKLOG', label: 'Backlog' },
  { key: 'IN_PROGRESS', label: 'In Progress' },
  { key: 'REVIEW', label: 'Review' },
  { key: 'DONE', label: 'Done' },
]
