import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'

import { ChatDrawer } from '../components/ChatDrawer'

afterEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
})

it('persists an accessible keyboard-resizable tutor width', () => {
  localStorage.setItem('techgrowth.chat.width', '700')
  render(<ChatDrawer open onClose={() => undefined} context={{}} onActionComplete={async () => undefined} />)

  const drawer = screen.getByLabelText('上下文导师')
  const separator = screen.getByRole('separator', { name: '调整导师宽度' })
  expect(drawer).toHaveStyle({ width: '700px' })
  fireEvent.keyDown(separator, { key: 'ArrowLeft' })
  expect(drawer).toHaveStyle({ width: '720px' })
  fireEvent.keyDown(separator, { key: 'ArrowRight' })
  expect(localStorage.getItem('techgrowth.chat.width')).toBe('700')
  expect(drawer).toHaveClass('chat-readable')
})

it('renders generic tool call and result events', async () => {
  const events = [
    'event: tool_call\ndata: {"id":"call-1","name":"get_curriculum_state","arguments":{}}',
    'event: tool_result\ndata: {"id":"call-1","name":"get_curriculum_state","result":{"active_track":"go"}}',
    'event: token\ndata: {"text":"当前主路线是 Go。"}',
    'event: done\ndata: {}',
  ].join('\n\n') + '\n\n'
  vi.stubGlobal('fetch', vi.fn(async () => new Response(events, { headers: { 'Content-Type': 'text/event-stream' } })))
  const user = userEvent.setup()
  render(<ChatDrawer open onClose={() => undefined} context={{}} onActionComplete={async () => undefined} />)

  await user.type(screen.getByLabelText('询问导师'), '当前路线是什么')
  await user.click(screen.getByTitle('发送'))

  expect(await screen.findByText('调用 get_curriculum_state')).toBeInTheDocument()
  expect(screen.getByText('get_curriculum_state 已完成')).toBeInTheDocument()
  expect(screen.getByText('当前主路线是 Go。')).toBeInTheDocument()
})

it('ignores the stored desktop width on mobile', () => {
  localStorage.setItem('techgrowth.chat.width', '700')
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })))

  render(<ChatDrawer open onClose={() => undefined} context={{}} onActionComplete={async () => undefined} />)

  expect(screen.getByLabelText('上下文导师')).toHaveStyle({ width: '100%' })
})
