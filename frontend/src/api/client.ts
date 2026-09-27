import axios from 'axios'
import type {
  Task, TaskUpdateResponse, Dependency, CriticalPath, AISuggestResponse,
} from '../types'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_TOKEN = import.meta.env.VITE_API_TOKEN || ''

const http = axios.create({
  baseURL: BASE_URL,
  headers: { Authorization: `Bearer ${API_TOKEN}` },
})

export const api = {
  listTasks: async (): Promise<Task[]> => (await http.get('/tasks')).data,

  getTask: async (id: number): Promise<Task> => (await http.get(`/tasks/${id}`)).data,

  createTask: async (payload: {
    title: string
    description: string
    start_date: string
    duration_days: number
  }): Promise<Task> => (await http.post('/tasks', payload)).data,

  updateTask: async (
    id: number,
    payload: Partial<{
      title: string
      description: string
      status: string
      start_date: string
      duration_days: number
    }>,
  ): Promise<TaskUpdateResponse> => (await http.patch(`/tasks/${id}`, payload)).data,

  deleteTask: async (id: number): Promise<void> => {
    await http.delete(`/tasks/${id}`)
  },

  listDependencies: async (): Promise<Dependency[]> => (await http.get('/dependencies')).data,

  createDependency: async (predecessor_id: number, successor_id: number): Promise<Dependency> =>
    (await http.post('/dependencies', { predecessor_id, successor_id })).data,

  deleteDependency: async (id: number): Promise<void> => {
    await http.delete(`/dependencies/${id}`)
  },

  criticalPath: async (): Promise<CriticalPath> => (await http.get('/dependencies/critical-path')).data,

  suggestDependencies: async (body: {
    task_id?: number
    title?: string
    description?: string
  }): Promise<AISuggestResponse> => (await http.post('/ai/suggest-dependencies', body)).data,
}

/**
 * Axios throws on 4xx/5xx; API error bodies look like {"detail": "..."}.
 * This pulls that message out so components can show it directly instead
 * of a generic "Request failed with status code 409".
 */
export function apiErrorMessage(err: unknown, fallback = 'Something went wrong.'): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail)
  }
  return fallback
}
