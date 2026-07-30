import type { ChatEvent, ChatIntent } from './types'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

const API_ROOT = '/api/v1'

async function parseError(response: Response): Promise<string> {
  try {
    const payload: unknown = await response.json()
    if (!payload || typeof payload !== 'object' || !('detail' in payload)) return '请求失败'
    const detail = payload.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const messages = detail.flatMap((item) =>
        item && typeof item === 'object' && 'msg' in item && typeof item.msg === 'string'
          ? [item.msg]
          : [],
      )
      if (messages.length) return messages.join('；')
    }
    return '请求失败'
  } catch {
    return '请求失败'
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (init.method && init.method !== 'GET') {
    const csrf = sessionStorage.getItem('tg_csrf')
    if (csrf) headers.set('X-CSRF-Token', csrf)
  }
  const response = await fetch(`${API_ROOT}${path}`, { ...init, headers, credentials: 'include' })
  if (!response.ok) throw new ApiError(response.status, await parseError(response))
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

function decodeEvent(raw: string): ChatEvent | null {
  const eventName = raw.split('\n').find((line) => line.startsWith('event: '))?.slice(7)
  const data = raw.split('\n').find((line) => line.startsWith('data: '))?.slice(6)
  if (!eventName || data === undefined) return null
  try {
    const payload = JSON.parse(data) as Record<string, unknown>
    if (eventName === 'intent')
      return {
        type: 'intent',
        intent: payload.intent as ChatIntent,
        confidence: Number(payload.confidence),
        needs_action: Boolean(payload.needs_action),
      }
    if (eventName === 'token') return { type: 'token', text: String(payload.text ?? '') }
    if (eventName === 'action_proposal')
      return {
        type: 'action_proposal',
        id: String(payload.id),
        summary: String(payload.summary),
        expires_at: String(payload.expires_at),
      }
    if (eventName === 'tool_call')
      return {
        type: 'tool_call', id: String(payload.id), name: String(payload.name),
        arguments: (payload.arguments ?? {}) as Record<string, unknown>,
      }
    if (eventName === 'tool_result')
      return {
        type: 'tool_result', id: String(payload.id), name: String(payload.name),
        result: (payload.result ?? {}) as Record<string, unknown>,
      }
    if (eventName === 'error')
      return { type: 'error', code: String(payload.code), message: String(payload.message) }
    if (eventName === 'done') return { type: 'done' }
  } catch {
    return { type: 'error', code: 'stream_invalid', message: '导师返回了无法解析的数据' }
  }
  return null
}

export async function streamChat(
  message: string,
  pageContext: Record<string, string>,
  onEvent: (event: ChatEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_ROOT}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': sessionStorage.getItem('tg_csrf') || '',
    },
    credentials: 'include',
    body: JSON.stringify({ message, page_context: pageContext }),
  })
  if (!response.ok || !response.body) throw new ApiError(response.status, await parseError(response))
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''
    for (const raw of events) {
      const event = decodeEvent(raw)
      if (event) onEvent(event)
    }
    if (done) break
  }
  if (buffer.trim()) {
    const event = decodeEvent(buffer)
    if (event) onEvent(event)
  }
}
