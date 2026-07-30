import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  BarChart3, Bell, Bot, CheckCircle2, ChevronRight, CircleGauge, Code2, ExternalLink,
  FileCheck2, GitBranch, History, LoaderCircle, LogOut, Menu, Radar, RefreshCw,
  Route, Save, Settings, ShieldCheck, Sparkles, Target, XCircle,
} from 'lucide-react'

import { ApiError, api } from '../api'
import { decodeVapidPublicKey } from '../push'
import type {
  LearningTask, NotificationPreference, RadarItem, RadarStatus, Repository,
  SetupStatus, SkillProfile, User, WeeklyReview,
} from '../types'
import { ChatDrawer } from './ChatDrawer'
import { CurriculumCenter } from './CurriculumCenter'
import { DataPlatform } from './DataPlatform'

type View = 'today' | 'analytics' | 'curriculum' | 'radar' | 'repositories' | 'growth' | 'weekly' | 'settings'
const navItems: { id: View; label: string; icon: typeof Target }[] = [
  { id: 'today', label: '今日任务', icon: Target },
  { id: 'analytics', label: '数据中台', icon: BarChart3 },
  { id: 'curriculum', label: '课程中心', icon: Route },
  { id: 'radar', label: '技术雷达', icon: Radar },
  { id: 'repositories', label: '项目与仓库', icon: GitBranch },
  { id: 'growth', label: '成长证据', icon: CircleGauge },
  { id: 'weekly', label: '周复盘', icon: History },
  { id: 'settings', label: '设置', icon: Settings },
]

export function Workbench({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [view, setView] = useState<View>('today')
  const [task, setTask] = useState<LearningTask | null>(null)
  const [radar, setRadar] = useState<RadarItem[]>([])
  const [selectedRadar, setSelectedRadar] = useState('')
  const [profile, setProfile] = useState<SkillProfile[]>([])
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [weekly, setWeekly] = useState<WeeklyReview[]>([])
  const [setup, setSetup] = useState<SetupStatus | null>(null)
  const [preferences, setPreferences] = useState<NotificationPreference[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [chatOpen, setChatOpen] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const taskRequest = api<LearningTask>('/tasks/today').catch((reason) => {
        if (reason instanceof ApiError && reason.status === 404) return null
        throw reason
      })
      const [today, radarItems, skills, repos, reviews, setupStatus, notificationPrefs] =
        await Promise.all([
          taskRequest, api<RadarItem[]>('/radar'), api<SkillProfile[]>('/profile'),
          api<Repository[]>('/repositories'), api<WeeklyReview[]>('/weekly-reviews'),
          api<SetupStatus>('/setup'), api<NotificationPreference[]>('/notifications/preferences'),
        ])
      setTask(today)
      setRadar(radarItems)
      setSelectedRadar((current) => current || radarItems[0]?.id || '')
      setProfile(skills)
      setRepositories(repos)
      setWeekly(reviews)
      setSetup(setupStatus)
      setPreferences(notificationPrefs)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法载入工作台')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  async function logout() {
    await api('/auth/logout', { method: 'POST' }).catch(() => undefined)
    sessionStorage.removeItem('tg_csrf')
    onLogout()
  }

  const content = useMemo(() => {
    if (loading) return <div className="loading-state"><LoaderCircle className="spin" /><span>正在载入</span></div>
    if (error) return <div className="error-state"><XCircle /><p>{error}</p><button onClick={() => void load()}><RefreshCw size={16} />重试</button></div>
    if (view === 'today') return <TodayView task={task} radar={radar} onTask={setTask} onProfile={setProfile} />
    if (view === 'analytics') return <DataPlatform />
    if (view === 'curriculum') return <CurriculumCenter />
    if (view === 'radar') return <RadarView items={radar} selected={selectedRadar} onSelect={setSelectedRadar} onReload={load} />
    if (view === 'repositories') return <RepositoryView items={repositories} onReload={async () => setRepositories(await api<Repository[]>('/repositories'))} />
    if (view === 'growth') return <GrowthView skills={profile} />
    if (view === 'weekly') return <WeeklyView items={weekly} onReload={load} />
    return <SettingsView setup={setup} preferences={preferences} onSaved={load} />
  }, [error, loading, preferences, profile, radar, repositories, selectedRadar, setup, task, view, weekly])

  const chatConfigured = setup?.provider.chat.api_key_configured ?? false
  const embeddingConfigured = setup?.provider.embedding.api_key_configured ?? false
  const providerStatus = chatConfigured && embeddingConfigured
    ? '模型已连接'
    : chatConfigured || embeddingConfigured ? '模型部分配置' : '待配置模型'
  let chatContext: Record<string, string> = { view }
  if (view === 'radar' && selectedRadar) chatContext = { view, radar_item_id: selectedRadar }
  if (view === 'today' && task) chatContext = { view, task_id: task.id }

  return (
    <div className={`app-shell ${chatOpen ? 'chat-visible' : ''}`}>
      <header className="topbar">
        <button className="icon-button mobile-menu" title="打开导航" onClick={() => setMobileNavOpen(!mobileNavOpen)}><Menu size={19} /></button>
        <div className="product-lockup"><span className="product-symbol"><Code2 size={18} /></span><strong>TechGrowth</strong><span>技术成长智能体</span></div>
        <div className="topbar-actions">
          <span className={`status-dot ${chatConfigured && embeddingConfigured ? 'online' : 'warning'}`}>{providerStatus}</span>
          <button className="icon-button" title="打开导师" onClick={() => setChatOpen(true)}><Bot size={19} /></button>
          <button className="icon-button" title="退出登录" onClick={() => void logout()}><LogOut size={18} /></button>
        </div>
      </header>
      <nav className={`sidebar ${mobileNavOpen ? 'is-open' : ''}`} aria-label="主导航">
        <div className="sidebar-user"><span>{user.email.slice(0, 1).toUpperCase()}</span><div><strong>{user.email}</strong><small>个人工作区</small></div></div>
        {navItems.map((item) => {
          const Icon = item.icon
          return <button key={item.id} className={view === item.id ? 'active' : ''} onClick={() => { setView(item.id); setMobileNavOpen(false) }} aria-label={item.label}><Icon size={18} /><span>{item.label}</span><ChevronRight size={15} className="nav-arrow" /></button>
        })}
        {setup?.icp_number && <a className="icp-link" href="https://beian.miit.gov.cn" target="_blank" rel="noreferrer">{setup.icp_number}</a>}
      </nav>
      <main className="workspace">{content}</main>
      <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} context={chatContext} onActionComplete={load} />
      <nav className="mobile-bottom-nav" aria-label="移动导航">
        {navItems.slice(0, 5).map((item) => { const Icon = item.icon; return <button key={item.id} className={view === item.id ? 'active' : ''} aria-label={item.label} onClick={() => setView(item.id)}><Icon size={19} /><span>{item.label}</span></button> })}
      </nav>
    </div>
  )
}

function SectionHeader({ eyebrow, title, action }: { eyebrow: string; title: string; action?: React.ReactNode }) {
  return <header className="section-header"><div><p>{eyebrow}</p><h1>{title}</h1></div>{action}</header>
}

function TodayView({ task, radar, onTask, onProfile }: { task: LearningTask | null; radar: RadarItem[]; onTask: (task: LearningTask) => void; onProfile: (profile: SkillProfile[]) => void }) {
  const [summary, setSummary] = useState('')
  const [reference, setReference] = useState('')
  const [scores, setScores] = useState<Record<string, number>>({ correctness: 3, testing: 3 })
  const [result, setResult] = useState<{ passed: boolean; feedback: string } | null>(null)
  const [busy, setBusy] = useState(false)

  async function generate() {
    setBusy(true)
    try {
      onTask(await api<LearningTask>('/tasks/generate', { method: 'POST', body: JSON.stringify({ topic: 'curriculum', skill: 'curriculum' }) }))
    } finally { setBusy(false) }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!task) return
    setBusy(true)
    try {
      const response = await api<{ review: { passed: boolean; feedback: string } }>(`/tasks/${task.id}/submissions`, {
        method: 'POST', body: JSON.stringify({ summary, artifact_kind: 'commit', artifact_reference: reference, self_scores: scores }),
      })
      setResult(response.review)
      onProfile(await api<SkillProfile[]>('/profile'))
    } finally { setBusy(false) }
  }

  async function regenerate() {
    if (!task || !window.confirm('重新出题会替换当前未提交任务，是否继续？')) return
    setBusy(true)
    try {
      onTask(await api<LearningTask>(`/tasks/${task.id}/regenerate`, {
        method: 'POST',
        headers: { 'Idempotency-Key': `web-${task.id}-${Date.now()}` },
        body: JSON.stringify({ reason: '题目不够明确，需要重新生成' }),
      }))
    } finally { setBusy(false) }
  }

  async function revealHint(level: number) {
    if (!task) return
    onTask(await api<LearningTask>(`/tasks/${task.id}/hints/${level}/reveal`, { method: 'POST' }))
  }

  async function revealSolution() {
    if (!task) return
    onTask(await api<LearningTask>(`/tasks/${task.id}/solution/reveal`, { method: 'POST' }))
  }

  if (!task) return <section><SectionHeader eyebrow="今天" title="准备第一项成长任务" /><div className="empty-work"><Target size={28} /><p>从课程路线中选择当前最需要补强的技能。</p><button className="primary-button compact" onClick={() => void generate()} disabled={busy}><Sparkles size={17} />生成今日任务</button></div></section>

  return (
    <section>
      <SectionHeader eyebrow="今日成长任务" title={task.title} action={<div className="task-actions"><span className="time-badge">{task.expected_minutes} 分钟</span><button className="secondary-button" onClick={() => void regenerate()} disabled={busy}><RefreshCw size={16} />重新出题</button></div>} />
      <div className="task-layout">
        <div className="task-main">
          <p className="task-objective">{task.objective}</p>
          {task.theory_brief && <div className="content-section"><h2>理论基础</h2><p>{task.theory_brief}</p></div>}
          {task.problem_statement && <div className="content-section problem-statement"><h2>题目</h2><p>{task.problem_statement}</p>{task.starter_context && <small>{task.starter_context}</small>}</div>}
          {task.learning_objectives.length > 0 && <div className="content-section"><h2>学习目标</h2><ul>{task.learning_objectives.map((item) => <li key={item}>{item}</li>)}</ul></div>}
          {task.constraints.length > 0 && <div className="content-section"><h2>约束条件</h2><ul>{task.constraints.map((item) => <li key={item}>{item}</li>)}</ul></div>}
          {task.prerequisites.length > 0 && <div className="content-section"><h2>开始前</h2><ul>{task.prerequisites.map((item) => <li key={item}>{item}</li>)}</ul></div>}
          <div className="content-section"><h2>执行步骤</h2><ol className="task-steps">{task.instructions.map((item, index) => typeof item === 'string' ? <li key={`${index}-${item}`}>{item}</li> : <li key={`${index}-${item.action}`}><div><strong>{item.action}</strong><span>{item.minutes} 分钟</span></div><p>{item.expected_result}</p></li>)}</ol></div>
          {task.deliverables.length > 0 && <div className="content-section"><h2>必须提交</h2><ul>{task.deliverables.map((item) => <li key={item}>{item}</li>)}</ul></div>}
          {task.acceptance_checks.length > 0 && <div className="content-section"><h2>验收检查</h2><div className="check-list">{task.acceptance_checks.map((check) => <div key={`${check.method}-${check.instruction}`}><code>{check.instruction}</code><p>{check.expected_result}</p></div>)}</div></div>}
          <div className="content-section"><h2>验收 Rubric</h2><div className="rubric-list">{task.rubric.map((item) => <div className="rubric-row" key={item.key}><FileCheck2 size={17} /><div><strong>{item.label}</strong>{item.description && <p>{item.description}</p>}{item.score_anchors && <div className="score-anchors">{Object.entries(item.score_anchors).map(([score, label]) => <span key={score}><b>{score}</b>{label}</span>)}</div>}</div>{item.critical && <small>关键项</small>}<select aria-label={`${item.label}评分`} value={scores[item.key] ?? 3} onChange={(event) => setScores({ ...scores, [item.key]: Number(event.target.value) })}>{[0, 1, 2, 3, 4].map((score) => <option value={score} key={score}>{score} / 4</option>)}</select></div>)}</div></div>
          <div className="content-section guidance-section"><h2>分层提示</h2>{task.revealed_hints.length > 0 && <ol>{task.revealed_hints.map((hint, index) => <li key={`${index}-${hint}`}>{hint}</li>)}</ol>}{task.revealed_hint_level < 3 && <button className="secondary-button" onClick={() => void revealHint(task.revealed_hint_level + 1)}>查看{['一级', '二级', '三级'][task.revealed_hint_level]}提示</button>}</div>
          <div className="content-section guidance-section"><h2>解题思路</h2>{task.solution_outline ? <p>{task.solution_outline}</p> : <button className="secondary-button" onClick={() => void revealSolution()}>查看解题思路</button>}</div>
          <form className="submission-form" onSubmit={submit}><h2>提交成果</h2><label htmlFor="summary">成果摘要</label><textarea id="summary" value={summary} onChange={(event) => setSummary(event.target.value)} required minLength={5} /><label htmlFor="reference">Commit / PR / 报告引用</label><input id="reference" value={reference} onChange={(event) => setReference(event.target.value)} required /><button className="primary-button compact" disabled={busy}><CheckCircle2 size={17} />提交审阅</button></form>
          {result && <div className={`review-result ${result.passed ? 'passed' : 'retry'}`}><strong>{result.passed ? '审阅通过' : '需要补做'}</strong><p>{result.feedback}</p></div>}
        </div>
        <aside className="context-rail"><h2>相关技术信号</h2>{radar.slice(0, 3).map((item) => <a href={item.source_url} target="_blank" rel="noreferrer" key={item.id}><span>{item.source_name}</span><strong>{item.title}</strong><small>{item.relevance_reason}</small></a>)}</aside>
      </div>
    </section>
  )
}

function RadarView({ items, selected, onSelect, onReload }: { items: RadarItem[]; selected: string; onSelect: (id: string) => void; onReload: () => Promise<void> }) {
  const [topic, setTopic] = useState('全部')
  const [status, setStatus] = useState<RadarStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { api<RadarStatus>('/radar/status').then(setStatus).catch((reason) => setError(reason instanceof Error ? reason.message : '无法读取雷达状态')) }, [])
  const topics = ['全部', ...new Set(items.map((item) => item.topic))]
  const filtered = topic === '全部' ? items : items.filter((item) => item.topic === topic)
  async function refresh() {
    setBusy(true); setError('')
    try { setStatus(await api<RadarStatus>('/radar/refresh', { method: 'POST' })); await onReload() }
    catch (reason) { setError(reason instanceof Error ? reason.message : '刷新失败') }
    finally { setBusy(false) }
  }
  return <section><SectionHeader eyebrow="技术雷达" title="值得关注的技术变化" action={<button className="secondary-button" onClick={() => void refresh()} disabled={busy}><RefreshCw className={busy ? 'spin' : ''} size={17} />立即刷新</button>} />{status && <div className={`radar-status ${status.status}`}><strong>{status.successful_sources}/{status.total_sources} 个来源成功</strong><span>新增 {status.inserted_items} 条</span>{status.created_at && <time>{new Date(status.created_at).toLocaleString('zh-CN')}</time>}{status.failed_sources.length > 0 && <small>失败：{status.failed_sources.join('、')}</small>}</div>}{error && <p className="form-error" role="alert">{error}</p>}<div className="filter-row">{topics.map((item) => <button className={topic === item ? 'active' : ''} key={item} onClick={() => setTopic(item)}>{item}</button>)}</div><div className="radar-list">{filtered.map((item) => <article className={selected === item.id ? 'selected' : ''} key={item.id} onClick={() => onSelect(item.id)}><div className="radar-meta"><span>{item.source_name}</span><span>可信度 {Math.round(item.credibility * 100)}%</span><span>相关度 {Math.round(item.relevance * 100)}%</span></div><h2>{item.title}</h2><p>{item.summary}</p><footer><small>{item.relevance_reason}</small><a href={item.source_url} target="_blank" rel="noreferrer" title="打开来源"><ExternalLink size={16} /></a></footer></article>)}</div></section>
}

function RepositoryView({ items, onReload }: { items: Repository[]; onReload: () => Promise<void> }) {
  const [pairing, setPairing] = useState<{ code: string; expires_at: string } | null>(null)
  const [githubToken, setGithubToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  async function createPairing() { setPairing(await api('/connectors/pairing-codes', { method: 'POST' })) }
  async function importGithub(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage(''); setError('')
    try {
      await api('/setup/github', { method: 'PUT', body: JSON.stringify({ token: githubToken }) })
      const result = await api<{ imported: number }>('/repositories/github/import', { method: 'POST' })
      setGithubToken(''); setMessage(`已导入 ${result.imported} 个 GitHub 仓库`); await onReload()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'GitHub 仓库导入失败') }
    finally { setBusy(false) }
  }
  return <section><SectionHeader eyebrow="代码证据" title="项目与仓库" action={<button className="secondary-button" onClick={() => void createPairing()}><ShieldCheck size={17} />配对连接器</button>} />{pairing && <div className="pairing-band"><span>配对码</span><strong>{pairing.code}</strong><small>10 分钟内有效</small></div>}<form className="github-import" onSubmit={importGithub}><label>GitHub Fine-grained PAT<input type="password" value={githubToken} onChange={(event) => setGithubToken(event.target.value)} required /></label><button className="secondary-button" disabled={busy}><GitBranch size={17} />验证并导入</button></form>{message && <p className="form-success" role="status">{message}</p>}{error && <p className="form-error" role="alert">{error}</p>}<div className="repository-table"><div className="table-head"><span>仓库</span><span>主要语言</span><span>最近提交</span><span>匹配状态</span></div>{items.map((item) => <div className="table-row" key={item.id}><div className="repository-identity"><strong>{item.name}</strong><small>{item.canonical_remote || '未发现 Git 远程地址'}</small></div><span>{Object.entries(item.languages).slice(0, 2).map(([name, value]) => `${name} ${value}%`).join(' · ') || '未识别'}</span><code>{item.last_commit.slice(0, 8) || '—'}</code><span className={`match-state ${item.match_status}`}>{item.match_status === 'matched' ? '已匹配' : item.match_status === 'ambiguous' ? '待确认' : '未匹配'}</span></div>)}</div>{items.length === 0 && <p className="empty-note centered">还没有已同步仓库。</p>}</section>
}

const levelLabels = { discovering: '入门', practicing: '练习中', applied: '已应用', proficient: '熟练' }
function GrowthView({ skills }: { skills: SkillProfile[] }) {
  return <section><SectionHeader eyebrow="成长证据" title="能力画像" /><div className="skill-list">{skills.map((skill) => <article key={skill.id}><div><strong>{skill.name}</strong><span className={`level ${skill.level}`}>{levelLabels[skill.level]}</span></div><div className="evidence-count"><FileCheck2 size={17} /><span>{skill.evidence_count} 条有效证据</span></div></article>)}</div>{skills.length === 0 && <p className="empty-note centered">通过第一项任务后，这里会出现能力证据。</p>}</section>
}

function WeeklyView({ items, onReload }: { items: WeeklyReview[]; onReload: () => Promise<void> }) {
  async function generate() { await api('/weekly-reviews/generate', { method: 'POST' }); await onReload() }
  return <section><SectionHeader eyebrow="周期复盘" title="周复盘" action={<button className="secondary-button" onClick={() => void generate()}><RefreshCw size={17} />生成复盘</button>} /><div className="weekly-list">{items.map((item) => <article key={item.id}><time>{new Date(item.created_at).toLocaleDateString('zh-CN')}</time><h2>{item.summary}</h2><div><strong>下一阶段</strong>{item.next_focus.map((focus) => <span key={focus}>{focus}</span>)}</div></article>)}</div></section>
}

function SettingsView({ setup, preferences, onSaved }: { setup: SetupStatus | null; preferences: NotificationPreference[]; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState({ chat: { base_url: setup?.provider.chat.base_url || '', model: setup?.provider.chat.model || '', api_key: '' }, embedding: { base_url: setup?.provider.embedding.base_url || '', model: setup?.provider.embedding.model || '', api_key: '' } })
  const [prefs, setPrefs] = useState<NotificationPreference[]>(preferences.length ? preferences : [
    { channel: 'email', event: 'daily_task', enabled: true }, { channel: 'web_push', event: 'daily_task', enabled: true },
    { channel: 'email', event: 'review_complete', enabled: true }, { channel: 'web_push', event: 'review_complete', enabled: true },
    { channel: 'email', event: 'weekly_review', enabled: true }, { channel: 'web_push', event: 'weekly_review', enabled: true },
  ])
  async function saveProvider(event: FormEvent) { event.preventDefault(); await api('/setup/provider', { method: 'PUT', body: JSON.stringify(form) }); await onSaved() }
  async function savePrefs() { await api('/notifications/preferences', { method: 'PUT', body: JSON.stringify({ preferences: prefs }) }); await onSaved() }
  async function enablePush() { if (!('serviceWorker' in navigator) || !('PushManager' in window) || !setup?.vapid_public_key) return; const registration = await navigator.serviceWorker.register('/sw.js'); const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: decodeVapidPublicKey(setup.vapid_public_key) }); await api('/notifications/push-subscriptions', { method: 'POST', body: JSON.stringify(subscription.toJSON()) }) }
  return <section><SectionHeader eyebrow="系统设置" title="连接与通知" /><div className="settings-sections"><form onSubmit={saveProvider}><h2>聊天模型服务</h2><div className="field-grid"><label>聊天 Base URL<input value={form.chat.base_url} onChange={(event) => setForm({ ...form, chat: { ...form.chat, base_url: event.target.value } })} type="url" required /></label><label>聊天模型<input value={form.chat.model} onChange={(event) => setForm({ ...form, chat: { ...form.chat, model: event.target.value } })} required /></label><label>聊天 API Key<input value={form.chat.api_key} onChange={(event) => setForm({ ...form, chat: { ...form.chat, api_key: event.target.value } })} type="password" required={!setup?.provider.chat.api_key_configured} placeholder={setup?.provider.chat.api_key_configured ? '已配置，留空则保持不变' : ''} /></label></div><h2>Embedding 模型服务</h2><div className="field-grid"><label>Embedding Base URL<input value={form.embedding.base_url} onChange={(event) => setForm({ ...form, embedding: { ...form.embedding, base_url: event.target.value } })} type="url" required /></label><label>Embedding 模型<input value={form.embedding.model} onChange={(event) => setForm({ ...form, embedding: { ...form.embedding, model: event.target.value } })} required /></label><label>Embedding API Key<input value={form.embedding.api_key} onChange={(event) => setForm({ ...form, embedding: { ...form.embedding, api_key: event.target.value } })} type="password" required={!setup?.provider.embedding.api_key_configured} placeholder={setup?.provider.embedding.api_key_configured ? '已配置，留空则保持不变' : ''} /></label></div><button className="primary-button compact"><Save size={17} />保存模型设置</button></form><div><h2>通知偏好</h2><div className="preference-list">{prefs.map((pref, index) => <label key={`${pref.channel}-${pref.event}`}><span><Bell size={16} />{pref.event === 'daily_task' ? '每日任务' : pref.event === 'review_complete' ? '审阅完成' : '周复盘'} · {pref.channel === 'email' ? '邮件' : 'Web Push'}</span><input type="checkbox" checked={pref.enabled} onChange={(event) => setPrefs(prefs.map((item, itemIndex) => itemIndex === index ? { ...item, enabled: event.target.checked } : item))} /></label>)}</div><div className="button-row"><button className="secondary-button" onClick={() => void savePrefs()}><Save size={17} />保存通知</button><button className="secondary-button" onClick={() => void enablePush()}><Bell size={17} />启用浏览器推送</button></div></div></div></section>
}
