import '@testing-library/jest-dom'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import App from './App'
import { api } from './api/client'
import { Task } from './types'

// Mock the API client
vi.mock('./api/client', async (importOriginal) => {
  const actual = await importOriginal<any>()
  return {
    ...actual,
    api: {
      listTasks: vi.fn(),
      listDependencies: vi.fn(),
      updateTask: vi.fn(),
    }
  }
})

// Mock dnd-kit to expose a stable way to trigger drag end
vi.mock('@dnd-kit/core', async (importOriginal) => {
  const actual = await importOriginal<any>()
  return {
    ...actual,
    DndContext: ({ children, onDragEnd }: any) => {
      return (
        <div data-testid="mock-dnd-context">
          <button 
            data-testid="mock-drag"
            onClick={(e) => {
              const activeId = Number(e.currentTarget.getAttribute('data-active-id'))
              const overId = e.currentTarget.getAttribute('data-over-id')
              if (onDragEnd) onDragEnd({ active: { id: activeId }, over: { id: overId } } as any)
            }}
          >Mock Drag</button>
          {children}
        </div>
      )
    },
    useSensor: () => ({}),
    useSensors: () => ({})
  }
})

const mockTasks: Task[] = [
  {
    id: 1,
    title: 'Task 1',
    description: '',
    start_date: '2026-09-27',
    end_date: '2026-09-28',
    duration_days: 1,
    status: 'BACKLOG',
    readiness: 'READY',
    dependency_count: 0,
    created_at: '2026-09-27T10:00:00Z',
    updated_at: '2026-09-27T10:00:00Z',
  },
  {
    id: 2,
    title: 'Task 2',
    description: '',
    start_date: '2026-09-27',
    end_date: '2026-09-28',
    duration_days: 1,
    status: 'IN_PROGRESS',
    readiness: 'BLOCKED',
    dependency_count: 1,
    created_at: '2026-09-27T10:00:00Z',
    updated_at: '2026-09-27T10:00:00Z',
  }
]

describe('Kanban Application', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(api.listTasks).mockResolvedValue([...mockTasks])
    vi.mocked(api.listDependencies).mockResolvedValue([])
  })

  it('renders the four required columns', async () => {
    render(<App />)
    await waitFor(() => expect(screen.queryByText('Loading board…')).not.toBeInTheDocument())
    
    expect(screen.getByText('Backlog')).toBeInTheDocument()
    expect(screen.getByText('In Progress')).toBeInTheDocument()
    expect(screen.getByText('Review')).toBeInTheDocument()
    expect(screen.getByText('Done')).toBeInTheDocument()
  })

  it('renders tasks in the correct column based on their status and shows visual indicators', async () => {
    render(<App />)
    await waitFor(() => expect(screen.queryByText('Loading board…')).not.toBeInTheDocument())
    
    // Check Task 1 is in Backlog column
    const backlogCol = screen.getByText('Backlog').parentElement!.parentElement!
    expect(within(backlogCol).getByText('Task 1')).toBeInTheDocument()
    expect(within(backlogCol).getByText('● Ready')).toBeInTheDocument()

    // Check Task 2 is in In Progress column
    const inProgressCol = screen.getByText('In Progress').parentElement!.parentElement!
    expect(within(inProgressCol).getByText('Task 2')).toBeInTheDocument()
    expect(within(inProgressCol).getByText('● Blocked')).toBeInTheDocument()
  })

  it('verify moving a task results in correct API call and updates UI optimistically', async () => {
    vi.mocked(api.updateTask).mockResolvedValue({
      task: { ...mockTasks[0], status: 'IN_PROGRESS' },
      affected_task_ids: []
    })

    const user = userEvent.setup()
    render(<App />)
    await waitFor(() => expect(screen.queryByText('Loading board…')).not.toBeInTheDocument())

    // Trigger drag via our mock
    const dragButton = screen.getByTestId('mock-drag')
    dragButton.setAttribute('data-active-id', '1') // Task 1
    dragButton.setAttribute('data-over-id', 'IN_PROGRESS')
    
    await user.click(dragButton)

    // Verify API called correctly
    expect(api.updateTask).toHaveBeenCalledWith(1, { status: 'IN_PROGRESS' })

    // Verify UI updated - Task 1 should now be in In Progress
    const inProgressCol = screen.getByText('In Progress').parentElement!.parentElement!
    expect(within(inProgressCol).getByText('Task 1')).toBeInTheDocument()
  })

  it('mock an API failure and verify optimistic UI is reverted and toast shown', async () => {
    vi.mocked(api.updateTask).mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: 'Cannot move blocked task.' } }
    })

    const user = userEvent.setup()
    render(<App />)
    await waitFor(() => expect(screen.queryByText('Loading board…')).not.toBeInTheDocument())

    // Trigger drag
    const dragButton = screen.getByTestId('mock-drag')
    dragButton.setAttribute('data-active-id', '2') // Task 2
    dragButton.setAttribute('data-over-id', 'REVIEW')
    
    await user.click(dragButton)

    // Verify API called
    expect(api.updateTask).toHaveBeenCalledWith(2, { status: 'REVIEW' })

    // Verify error toast appears
    expect(await screen.findByText('Cannot move blocked task.')).toBeInTheDocument()

    // Verify task is reverted to In Progress (it should NOT be in Review)
    const inProgressCol = screen.getByText('In Progress').parentElement!.parentElement!
    expect(within(inProgressCol).getByText('Task 2')).toBeInTheDocument()
    
    const reviewCol = screen.getByText('Review').parentElement!.parentElement!
    expect(within(reviewCol).queryByText('Task 2')).not.toBeInTheDocument()
  })
})
