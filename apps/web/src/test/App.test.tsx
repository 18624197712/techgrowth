import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from '../App'

const task = {
  id: 'task-1',
  title: '构建一个 RAG 评测器',
  topic: 'RAG 评测',
  skill_name: 'RAG evaluation',
  expected_minutes: 35,
  objective: '验证检索回答的可靠性',
  instructions: ['创建固定样例', '实现评分器', '提交结果'],
  source_ids: ['source-1'],
  submission_kinds: ['commit'],
  rubric: [
    { key: 'correctness', label: '实现正确性', critical: true },
    { key: 'testing', label: '验证与测试', critical: false },
  ],
  status: 'ready',
  created_at: '2026-07-30T08:00:00Z',
}

function mockFetch(authenticated: boolean) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) {
        return new Response(
          authenticated ? JSON.stringify({ id: 'u1', email: 'dev@example.com' }) : '',
          { status: authenticated ? 200 : 401, headers: { 'Content-Type': 'application/json' } },
        )
      }
      if (url.endsWith('/tasks/today')) return Response.json(task)
      if (url.endsWith('/radar'))
        return Response.json([
          {
            id: 'source-1',
            title: 'Agent Runtime 2.0',
            summary: 'Durable agent execution',
            source_url: 'https://example.com/runtime',
            source_name: 'Official AI',
            topic: 'Agent engineering',
            credibility: 0.95,
            relevance: 0.9,
            relevance_reason: '与你的 Agent 学习方向相关',
            published_at: '2026-07-29T10:00:00Z',
          },
        ])
      if (url.endsWith('/profile')) return Response.json([])
      if (url.endsWith('/repositories')) return Response.json([])
      if (url.endsWith('/weekly-reviews')) return Response.json([])
      if (url.endsWith('/setup'))
        return Response.json({ provider: { api_key_configured: false }, icp_number: '' })
      if (url.endsWith('/notifications/preferences')) return Response.json([])
      return Response.json({})
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  sessionStorage.clear()
})

describe('TechGrowth app', () => {
  it('shows administrator login when there is no session', async () => {
    mockFetch(false)
    render(<App />)

    expect(await screen.findByRole('heading', { name: '登录 TechGrowth' })).toBeInTheDocument()
    expect(screen.getByLabelText('邮箱')).toBeInTheDocument()
    expect(screen.getByLabelText('密码')).toBeInTheDocument()
  })

  it('renders the daily workbench for an authenticated user', async () => {
    mockFetch(true)
    render(<App />)

    expect(await screen.findByRole('heading', { name: '构建一个 RAG 评测器' })).toBeInTheDocument()
    expect(screen.getByText('35 分钟')).toBeInTheDocument()
    expect(screen.getByText('实现正确性')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '技术雷达' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '成长证据' })).toBeInTheDocument()
  })

  it('renders FastAPI validation details as readable text', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).endsWith('/auth/me')) return new Response('', { status: 401 })
        return Response.json(
          { detail: [{ msg: '请输入可用于登录的邮箱地址' }] },
          { status: 422 },
        )
      }),
    )
    const user = userEvent.setup()
    render(<App />)

    await user.type(await screen.findByLabelText('邮箱'), 'dev@techgrowth.local')
    await user.type(screen.getByLabelText('密码'), 'DevelopmentPassword123!')
    await user.click(screen.getByRole('button', { name: '登录' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('请输入可用于登录的邮箱地址')
  })

  it('shows recovery codes before entering the workbench on first TOTP setup', async () => {
    let meCalls = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.endsWith('/auth/me')) {
          meCalls += 1
          return meCalls === 1
            ? new Response('', { status: 401 })
            : Response.json({ id: 'u1', email: 'developer@example.com', totp_enabled: true })
        }
        if (url.endsWith('/auth/login')) return Response.json({ next: 'totp_setup' })
        if (url.endsWith('/auth/totp/setup')) return Response.json({ secret: 'TESTSECRET' })
        if (url.endsWith('/auth/totp/confirm')) {
          return Response.json({
            csrf_token: 'csrf-token',
            recovery_codes: ['alpha-111', 'bravo-222'],
          })
        }
        return Response.json({})
      }),
    )
    const user = userEvent.setup()
    render(<App />)

    await user.type(await screen.findByLabelText('邮箱'), 'developer@example.com')
    await user.type(screen.getByLabelText('密码'), 'DevelopmentPassword123!')
    await user.click(screen.getByRole('button', { name: '登录' }))
    await user.type(await screen.findByLabelText('动态验证码'), '123456')
    await user.click(screen.getByRole('button', { name: '验证' }))

    expect(await screen.findByRole('heading', { name: '保存恢复码' })).toBeInTheDocument()
    expect(screen.getByText('alpha-111')).toBeInTheDocument()
    expect(screen.getByText('bravo-222')).toBeInTheDocument()
  })
})
