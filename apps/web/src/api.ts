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
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  })
  if (!response.ok) throw new ApiError(response.status, await parseError(response))
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function streamChat(
  message: string,
  pageContext: Record<string, string>,
  onToken: (text: string) => void,
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
  if (!response.ok || !response.body) throw new ApiError(response.status, '导师暂时不可用')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''
    for (const event of events) {
      const data = event.split('\n').find((line) => line.startsWith('data:'))
      if (!data || event.includes('event: done')) continue
      onToken(JSON.parse(data.slice(5).trim()).text)
    }
  }
}
