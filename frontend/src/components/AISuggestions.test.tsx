import '@testing-library/jest-dom'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import AISuggestions from './AISuggestions'
import { api } from '../api/client'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<any>()
  return {
    ...actual,
    api: {
      suggestDependencies: vi.fn(),
      createDependency: vi.fn(),
    }
  }
})

describe('AISuggestions', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders suggestions returned by the API', async () => {
    vi.mocked(api.suggestDependencies).mockResolvedValue({
      suggestions: [
        {
          task_id: 10,
          title: 'Design Database',
          reason: 'Because you need a DB first.',
          similarity_score: 0.95
        }
      ],
      mode: 'mock'
    })

    const user = userEvent.setup()
    render(<AISuggestions taskId={5} title="Build API" description="foo" onAccepted={vi.fn()} />)
    
    await user.click(screen.getByText('Suggest Dependencies'))
    
    expect(api.suggestDependencies).toHaveBeenCalledWith({ task_id: 5, title: 'Build API', description: 'foo' })
    
    expect(await screen.findByText('Suggested prerequisite: Design Database')).toBeInTheDocument()
    expect(screen.getByText('lexical overlap 95%')).toBeInTheDocument()
    expect(screen.getByText('Because you need a DB first.')).toBeInTheDocument()
  })

  it('verify clicking Accept calls the existing dependency API correctly', async () => {
    vi.mocked(api.suggestDependencies).mockResolvedValue({
      suggestions: [
        {
          task_id: 10,
          title: 'Design Database',
          reason: 'Because you need a DB first.',
          similarity_score: 0.95
        }
      ],
      mode: 'mock'
    })
    vi.mocked(api.createDependency).mockResolvedValue({} as any)

    const onAccepted = vi.fn()
    const user = userEvent.setup()
    
    render(<AISuggestions taskId={5} title="Build API" description="foo" onAccepted={onAccepted} />)
    await user.click(screen.getByText('Suggest Dependencies'))
    
    const acceptBtn = await screen.findByText('Accept')
    await user.click(acceptBtn)
    
    // API is called: createDependency(predecessor_id, successor_id)
    expect(api.createDependency).toHaveBeenCalledWith(10, 5)
    expect(onAccepted).toHaveBeenCalled()
  })

  it('verify a dependency API failure results in a visible user-facing error', async () => {
    vi.mocked(api.suggestDependencies).mockResolvedValue({
      suggestions: [
        {
          task_id: 10,
          title: 'Design Database',
          reason: 'Because you need a DB first.',
          similarity_score: 0.95
        }
      ],
      mode: 'mock'
    })
    
    vi.mocked(api.createDependency).mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: 'Rejected: this dependency would create a cycle.' } }
    })

    const user = userEvent.setup()
    render(<AISuggestions taskId={5} title="Build API" description="foo" onAccepted={vi.fn()} />)
    await user.click(screen.getByText('Suggest Dependencies'))
    
    const acceptBtn = await screen.findByText('Accept')
    await user.click(acceptBtn)
    
    expect(api.createDependency).toHaveBeenCalledWith(10, 5)
    
    // Error should be visible
    expect(await screen.findByText('Rejected: this dependency would create a cycle.')).toBeInTheDocument()
  })
})
