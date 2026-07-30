import { FormEvent, useState } from 'react'
import { Bot, Send, X } from 'lucide-react'

import { streamChat } from '../api'

export function ChatDrawer({ open, onClose, context }: { open: boolean; onClose: () => void; context: Record<string, string> }) {
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; text: string }[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const value = input.trim()
    if (!value || busy) return
    setInput('')
    setMessages((items) => [...items, { role: 'user', text: value }, { role: 'assistant', text: '' }])
    setBusy(true)
    try {
      await streamChat(value, context, (token) => {
        setMessages((items) => items.map((item, index) => index === items.length - 1 ? { ...item, text: item.text + token } : item))
      })
    } catch (error) {
      setMessages((items) => items.map((item, index) => index === items.length - 1 ? { ...item, text: error instanceof Error ? error.message : '导师暂时不可用' } : item))
    } finally {
      setBusy(false)
    }
  }

  return (
    <aside className={`chat-drawer ${open ? 'is-open' : ''}`} aria-hidden={!open}>
      <header><div><Bot size={18} aria-hidden="true" /><strong>上下文导师</strong></div><button className="icon-button" onClick={onClose} title="关闭导师"><X size={18} /></button></header>
      <div className="chat-messages">
        {messages.length === 0 && <p className="empty-note">从当前任务的具体问题开始。</p>}
        {messages.map((message, index) => <p className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>{message.text || '…'}</p>)}
      </div>
      <form className="chat-input" onSubmit={submit}>
        <input aria-label="询问导师" value={input} onChange={(e) => setInput(e.target.value)} placeholder="输入问题" />
        <button className="icon-button primary-icon" title="发送" disabled={busy}><Send size={17} /></button>
      </form>
    </aside>
  )
}

