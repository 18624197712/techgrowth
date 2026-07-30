import { FormEvent, PointerEvent as ReactPointerEvent, useEffect, useRef, useState } from 'react'
import { Bot, Check, Send, X } from 'lucide-react'

import { api, streamChat } from '../api'
import type { ChatIntent } from '../types'

type Proposal = { id: string; summary: string; status: 'pending' | 'executing' | 'done' | 'cancelled' }
type Message = {
  role: 'user' | 'assistant'
  text: string
  intent?: ChatIntent
  error?: string
  proposal?: Proposal
  tools?: Array<{ id: string; name: string; status: 'calling' | 'done' }>
}

const MIN_WIDTH = 320
const MAX_WIDTH = 720
const WIDTH_KEY = 'techgrowth.chat.width'

function initialWidth() {
  const stored = Number(localStorage.getItem(WIDTH_KEY) || 360)
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Number.isFinite(stored) ? stored : 360))
}

const intentLabels: Record<ChatIntent, string> = {
  technical_qa: '技术问答',
  task_coaching: '任务辅导',
  submission_improvement: '成果改进',
  growth_planning: '成长规划',
  radar_to_task: '雷达转任务',
}

export function ChatDrawer({
  open,
  onClose,
  context,
  onActionComplete,
}: {
  open: boolean
  onClose: () => void
  context: Record<string, string>
  onActionComplete: () => Promise<void>
}) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [width, setWidthState] = useState(initialWidth)
  const [mobile, setMobile] = useState(() =>
    window.matchMedia?.('(max-width: 760px)').matches ?? false)
  const drag = useRef<{ x: number; width: number } | null>(null)

  useEffect(() => {
    if (!window.matchMedia) return
    const query = window.matchMedia('(max-width: 760px)')
    const update = () => setMobile(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  function setWidth(value: number) {
    const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, value))
    setWidthState(next)
    localStorage.setItem(WIDTH_KEY, String(next))
  }

  function updateAssistant(update: (message: Message) => Message) {
    setMessages((items) =>
      items.map((item, index) => (index === items.length - 1 ? update(item) : item)),
    )
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const value = input.trim()
    if (!value || busy) return
    setInput('')
    setMessages((items) => [
      ...items,
      { role: 'user', text: value },
      { role: 'assistant', text: '' },
    ])
    setBusy(true)
    try {
      await streamChat(value, context, (event) => {
        if (event.type === 'intent')
          updateAssistant((item) => ({ ...item, intent: event.intent }))
        if (event.type === 'token')
          updateAssistant((item) => ({ ...item, text: item.text + event.text }))
        if (event.type === 'error')
          updateAssistant((item) => ({ ...item, error: event.message }))
        if (event.type === 'action_proposal')
          updateAssistant((item) => ({
            ...item,
            proposal: { id: event.id, summary: event.summary, status: 'pending' },
          }))
        if (event.type === 'tool_call')
          updateAssistant((item) => ({
            ...item,
            tools: [...(item.tools ?? []), { id: event.id, name: event.name, status: 'calling' }],
          }))
        if (event.type === 'tool_result')
          updateAssistant((item) => ({
            ...item,
            tools: [...(item.tools ?? []), { id: event.id, name: event.name, status: 'done' }],
          }))
      })
    } catch (error) {
      updateAssistant((item) => ({
        ...item,
        error: error instanceof Error ? error.message : '导师暂时不可用',
      }))
    } finally {
      setBusy(false)
    }
  }

  async function confirm(proposal: Proposal) {
    updateAssistant((item) => ({ ...item, proposal: { ...proposal, status: 'executing' } }))
    try {
      await api(`/chat/actions/${proposal.id}/confirm`, { method: 'POST' })
      updateAssistant((item) => ({ ...item, proposal: { ...proposal, status: 'done' } }))
      await onActionComplete()
    } catch (error) {
      updateAssistant((item) => ({
        ...item,
        proposal: { ...proposal, status: 'pending' },
        error: error instanceof Error ? error.message : '操作执行失败',
      }))
    }
  }

  async function cancel(proposal: Proposal) {
    await api(`/chat/actions/${proposal.id}/cancel`, { method: 'POST' })
    updateAssistant((item) => ({ ...item, proposal: { ...proposal, status: 'cancelled' } }))
  }

  function startResize(event: ReactPointerEvent<HTMLDivElement>) {
    drag.current = { x: event.clientX, width }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function resize(event: ReactPointerEvent<HTMLDivElement>) {
    if (drag.current) setWidth(drag.current.width + drag.current.x - event.clientX)
  }

  return (
    <aside className={`chat-drawer chat-readable ${open ? 'is-open' : ''}`} aria-hidden={!open} aria-label="上下文导师" style={{ width: mobile ? '100%' : width }}>
      <div
        className="chat-resize-handle"
        role="separator"
        aria-label="调整导师宽度"
        aria-orientation="vertical"
        aria-valuemin={MIN_WIDTH}
        aria-valuemax={MAX_WIDTH}
        aria-valuenow={width}
        tabIndex={0}
        onPointerDown={startResize}
        onPointerMove={resize}
        onPointerUp={() => { drag.current = null }}
        onKeyDown={(event) => {
          if (event.key === 'ArrowLeft') { event.preventDefault(); setWidth(width + 20) }
          if (event.key === 'ArrowRight') { event.preventDefault(); setWidth(width - 20) }
        }}
      />
      <header>
        <div><Bot size={18} aria-hidden="true" /><strong>上下文导师</strong></div>
        <button className="icon-button" onClick={onClose} title="关闭导师"><X size={18} /></button>
      </header>
      <div className="chat-messages">
        {messages.length === 0 && <p className="empty-note">从当前任务的具体问题开始。</p>}
        {messages.map((message, index) => (
          <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
            {message.intent && <span className="intent-label">{intentLabels[message.intent]}</span>}
            <p>{message.text || (busy && index === messages.length - 1 ? '正在分析…' : '')}</p>
            {message.error && <p className="chat-error" role="alert">{message.error}</p>}
            {message.tools && message.tools.length > 0 && <div className="tool-events">{message.tools.map((tool, toolIndex) => <small key={`${tool.id}-${toolIndex}`}>{tool.status === 'calling' ? `调用 ${tool.name}` : `${tool.name} 已完成`}</small>)}</div>}
            {message.proposal && (
              <div className="action-proposal">
                <strong>{message.proposal.summary}</strong>
                {message.proposal.status === 'pending' && (
                  <div>
                    <button onClick={() => void confirm(message.proposal!)}><Check size={15} />确认</button>
                    <button onClick={() => void cancel(message.proposal!)}><X size={15} />取消</button>
                  </div>
                )}
                {message.proposal.status === 'executing' && <small>正在执行…</small>}
                {message.proposal.status === 'done' && <small>已执行</small>}
                {message.proposal.status === 'cancelled' && <small>已取消</small>}
              </div>
            )}
          </div>
        ))}
      </div>
      <form className="chat-input" onSubmit={submit}>
        <input aria-label="询问导师" value={input} onChange={(event) => setInput(event.target.value)} placeholder="输入问题" />
        <button className="icon-button primary-icon" title="发送" disabled={busy}><Send size={17} /></button>
      </form>
    </aside>
  )
}
