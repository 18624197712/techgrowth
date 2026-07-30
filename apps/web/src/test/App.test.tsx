import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from '../App'

const task = {
  id: 'task-1',
  title: '实作：验证模型接口的错误边界',
  topic: '模型接口边界',
  skill_name: 'AI/LLM 工程',
  expected_minutes: 35,
  objective: '实现可测试的模型请求与错误映射',
  curriculum_version: 'v1',
  track_key: 'ai',
  stage_key: 'foundation',
  node_key: 'ai-foundation-model-io',
  prerequisites: ['能够运行 Python 测试'],
  instructions: [
    { action: '创建成功与失败测试样本', minutes: 15, expected_result: '两个样本均可加载' },
    { action: '实现请求并运行测试', minutes: 20, expected_result: '全部断言通过' },
  ],
  source_ids: ['source-1'],
  submission_kinds: ['commit', 'report'],
  deliverables: ['模型客户端实现', '测试报告'],
  acceptance_checks: [
    { method: 'command', instruction: 'pytest -q', expected_result: '全部测试通过' },
    { method: 'inspection', instruction: '检查错误消息', expected_result: '不包含 API Key' },
  ],
  rubric: [
    {
      key: 'correctness',
      label: '实现正确性',
      description: '请求和错误映射符合接口契约',
      critical: true,
      score_anchors: { '0': '无法运行', '1': '只能请求', '2': '成功路径', '3': '覆盖鉴权', '4': '覆盖超时' },
    },
    {
      key: 'testing',
      label: '验证与证据',
      description: '结果可以复现',
      critical: false,
      score_anchors: { '0': '无证据', '1': '口头描述', '2': '单个结果', '3': '测试通过', '4': '失败路径也通过' },
    },
  ],
  remediation_hint: '修复最低分项后重新运行验收检查',
  status: 'ready',
  created_at: '2026-07-30T08:10:00Z',
}

const radarItem = {
  id: 'source-1',
  title: 'Agent Runtime 2.0',
  summary: 'Durable agent execution',
  source_url: 'https://example.com/runtime',
  source_name: 'Official AI',
  topic: 'Agent engineering',
  credibility: 0.95,
  relevance: 0.9,
  relevance_reason: '与当前 Agent 学习阶段相关',
  published_at: '2026-07-29T10:00:00Z',
}

const tutorEvents = [
  'event: intent\ndata: {"intent":"task_coaching","confidence":0.91,"needs_action":false}',
  'event: token\ndata: {"text":"先运行验收命令，再补充最低分项的证据。"}',
  'event: done\ndata: {}',
].join('\n\n') + '\n\n'

function mockFetch(
  authenticated: boolean,
  onRequest?: (url: string, init?: RequestInit) => void,
  tutorBody = tutorEvents,
) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      onRequest?.(url, init)
      if (url.endsWith('/auth/me')) {
        return new Response(
          authenticated ? JSON.stringify({ id: 'u1', email: 'dev@example.com' }) : '',
          { status: authenticated ? 200 : 401, headers: { 'Content-Type': 'application/json' } },
        )
      }
      if (url.endsWith('/tasks/today')) return Response.json(task)
      if (url.endsWith('/radar/status'))
        return Response.json({
          id: 'run-1', status: 'partial', successful_sources: 5,
          failed_sources: ['hacker-news-ai'], inserted_items: 12,
          embedding_failures: 0, created_at: '2026-07-30T08:00:00Z',
        })
      if (url.endsWith('/radar/refresh'))
        return Response.json({
          id: 'run-2', status: 'succeeded', successful_sources: 6,
          failed_sources: [], inserted_items: 3, embedding_failures: 0,
          created_at: '2026-07-30T09:00:00Z',
        })
      if (url.endsWith('/radar')) return Response.json([radarItem])
      if (url.endsWith('/profile')) return Response.json([])
      if (url.endsWith('/repositories')) return Response.json([])
      if (url.endsWith('/weekly-reviews')) return Response.json([])
      if (url.endsWith('/setup'))
        return Response.json({
          provider: {
            chat: { base_url: 'https://chat.example/v1', model: 'chat-model', api_key_configured: true },
            embedding: { base_url: 'https://embed.example/v1', model: 'embed-model', api_key_configured: false },
          },
          icp_number: '',
        })
      if (url.endsWith('/notifications/preferences')) return Response.json([])
      if (url.includes('/analytics/'))
        return Response.json({
          range: '30d',
          metrics: [
            {
              key: 'learning_minutes', label: '有效学习', value: 164, unit: '分钟',
              definition: '通过审阅任务的计划分钟数', components: { passed_tasks: 4 },
            },
            {
              key: 'task_pass_rate', label: '任务通过率', value: 80, unit: '%',
              definition: '通过审阅数除以全部已审任务数', components: { passed: 4, reviewed: 5 },
            },
          ],
          track_progress: [
            { track_key: 'java', label: 'Java + Spring Cloud', completed_nodes: 5, total_nodes: 12, current_stage: 'practice' },
          ],
        })
      if (url.endsWith('/curriculum'))
        return Response.json({
          active_track_key: 'java', algorithm_days_per_week: 2, catalog_version: 'v2',
          tracks: [
            { key: 'java', label: 'Java + Spring Cloud', kind: 'primary', completed_nodes: 5, total_nodes: 12, current_stage: 'practice' },
            { key: 'go', label: 'Go', kind: 'primary', completed_nodes: 0, total_nodes: 12, current_stage: 'foundation' },
            { key: 'algorithms', label: '数据结构与算法', kind: 'secondary', completed_nodes: 2, total_nodes: 24, current_stage: 'foundation' },
          ],
        })
      if (url.endsWith('/curriculum/active-track') || url.endsWith('/curriculum/algorithm-frequency'))
        return Response.json({
          active_track_key: url.endsWith('/active-track') ? 'go' : 'java',
          algorithm_days_per_week: 3,
          catalog_version: 'v2',
          tracks: [],
        })
      if (url.endsWith('/chat/stream'))
        return new Response(tutorBody, { headers: { 'Content-Type': 'text/event-stream' } })
      if (url.includes('/chat/actions/') && url.endsWith('/confirm')) return Response.json(task)
      if (url.includes('/chat/actions/') && url.endsWith('/cancel')) return Response.json({ status: 'cancelled' })
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

  it('renders a concrete curriculum task with checks and score anchors', async () => {
    mockFetch(true)
    render(<App />)

    expect(await screen.findByRole('heading', { name: task.title })).toBeInTheDocument()
    expect(screen.getByText('15 分钟')).toBeInTheDocument()
    expect(screen.getByText('两个样本均可加载')).toBeInTheDocument()
    expect(screen.getByText('pytest -q')).toBeInTheDocument()
    expect(screen.getByText('模型客户端实现')).toBeInTheDocument()
    expect(screen.getByText('覆盖超时')).toBeInTheDocument()
  })

  it('shows radar run status and refreshes it', async () => {
    mockFetch(true)
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: task.title })

    await user.click(screen.getByRole('button', { name: '技术雷达' }))
    expect(await screen.findByText('5/6 个来源成功')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '立即刷新' }))
    expect(await screen.findByText('6/6 个来源成功')).toBeInTheDocument()
  })

  it('renders tutor intent and the streamed model answer', async () => {
    mockFetch(true)
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: task.title })

    await user.click(screen.getByTitle('打开导师'))
    await user.type(screen.getByLabelText('询问导师'), '我该怎么改进？')
    await user.click(screen.getByTitle('发送'))

    expect(await screen.findByText('任务辅导')).toBeInTheDocument()
    expect(screen.getByText('先运行验收命令，再补充最低分项的证据。')).toBeInTheDocument()
  })

  it('executes a tutor action only after confirmation', async () => {
    const requests: string[] = []
    const actionEvents = [
      'event: intent\ndata: {"intent":"radar_to_task","confidence":0.96,"needs_action":true}',
      'event: token\ndata: {"text":"确认后创建任务。"}',
      'event: action_proposal\ndata: {"id":"action-1","summary":"基于雷达创建课程任务","expires_at":"2026-07-30T10:00:00Z"}',
      'event: done\ndata: {}',
    ].join('\n\n') + '\n\n'
    mockFetch(true, (url) => requests.push(url), actionEvents)
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: task.title })

    await user.click(screen.getByTitle('打开导师'))
    await user.type(screen.getByLabelText('询问导师'), '把雷达转成任务')
    await user.click(screen.getByTitle('发送'))
    expect(await screen.findByText('基于雷达创建课程任务')).toBeInTheDocument()
    expect(requests.some((url) => url.includes('/chat/actions/'))).toBe(false)

    await user.click(screen.getByRole('button', { name: '确认' }))
    expect(requests.some((url) => url.endsWith('/chat/actions/action-1/confirm'))).toBe(true)
  })

  it('configures chat and embedding providers independently', async () => {
    let providerBody: unknown
    mockFetch(true, (url, init) => {
      if (url.endsWith('/setup/provider') && init?.method === 'PUT') {
        providerBody = JSON.parse(String(init.body))
      }
    })
    const user = userEvent.setup()
    render(<App />)

    await screen.findByRole('heading', { name: task.title })
    await user.click(screen.getByRole('button', { name: '设置' }))
    expect(screen.getByRole('heading', { name: '聊天模型服务' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Embedding 模型服务' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Embedding API Key'), 'embed-secret')
    await user.click(screen.getByRole('button', { name: '保存模型设置' }))

    expect(providerBody).toEqual({
      chat: { base_url: 'https://chat.example/v1', model: 'chat-model', api_key: '' },
      embedding: { base_url: 'https://embed.example/v1', model: 'embed-model', api_key: 'embed-secret' },
    })
  })

  it('opens the unified data platform with explainable metrics', async () => {
    mockFetch(true)
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: task.title })

    await user.click(screen.getByRole('button', { name: '数据中台' }))

    expect(await screen.findByRole('heading', { name: '成长数据总览' })).toBeInTheDocument()
    expect(screen.getByText('164')).toBeInTheDocument()
    expect(screen.getByText('通过审阅任务的计划分钟数')).toBeInTheDocument()
    expect(screen.getByText('Java + Spring Cloud')).toBeInTheDocument()
  })

  it('switches the selected primary curriculum without clearing progress', async () => {
    let switchBody: unknown
    mockFetch(true, (url, init) => {
      if (url.endsWith('/curriculum/active-track')) switchBody = JSON.parse(String(init?.body))
    })
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: task.title })

    await user.click(screen.getByRole('button', { name: '课程中心' }))
    await screen.findByRole('heading', { name: '选择成长路线' })
    await user.click(screen.getByRole('button', { name: '将 Go 设为主路线' }))

    expect(switchBody).toEqual({ track_key: 'go' })
  })
})
