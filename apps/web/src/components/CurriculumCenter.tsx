import { useEffect, useState } from 'react'
import { CheckCircle2, LoaderCircle, Route } from 'lucide-react'

import { api } from '../api'
import type { CurriculumState } from '../types'

const stageLabels: Record<string, string> = {
  foundation: '初级', practice: '中级', production: '高级', architecture: '架构师',
}
const stages = ['foundation', 'practice', 'production', 'architecture'] as const

export function CurriculumCenter({ onTrackChange }: { onTrackChange?: () => Promise<void> }) {
  const [state, setState] = useState<CurriculumState | null>(null)
  const [busy, setBusy] = useState('')

  useEffect(() => { api<CurriculumState>('/curriculum').then(setState) }, [])

  async function switchTrack(trackKey: string) {
    setBusy(trackKey)
    try {
      setState(await api<CurriculumState>('/curriculum/active-track', {
        method: 'PUT', body: JSON.stringify({ track_key: trackKey }),
      }))
      await onTrackChange?.()
    } finally { setBusy('') }
  }

  async function setFrequency(days: number) {
    setBusy('algorithms')
    try {
      setState(await api<CurriculumState>('/curriculum/algorithm-frequency', {
        method: 'PUT', body: JSON.stringify({ days_per_week: days }),
      }))
    } finally { setBusy('') }
  }

  async function setTargetStage(stageKey: (typeof stages)[number]) {
    setBusy(stageKey)
    try {
      setState(await api<CurriculumState>('/curriculum/target-stage', {
        method: 'PUT', body: JSON.stringify({ stage_key: stageKey }),
      }))
      await onTrackChange?.()
    } finally { setBusy('') }
  }

  if (!state) return <div className="loading-state"><LoaderCircle className="spin" /><span>正在载入课程</span></div>
  return <section>
    <header className="section-header"><div><p>课程中心</p><h1>选择成长路线</h1></div><span className="time-badge">课程 {state.catalog_version}</span></header>
    <div className="difficulty-selector"><div><strong>每日任务难度</strong><p>选择后，下一题严格使用该阶段的课程节点。</p></div><div role="group" aria-label="每日任务难度">{stages.map((stage) => <button type="button" key={stage} className={state.target_stage === stage ? 'active' : ''} aria-pressed={state.target_stage === stage} disabled={Boolean(busy)} onClick={() => void setTargetStage(stage)}>{stageLabels[stage]}</button>)}</div></div>
    <div className="curriculum-list">
      {state.tracks.filter((track) => track.kind === 'primary').map((track) => {
        const active = track.key === state.active_track_key
        const percent = Math.round(track.completed_nodes * 100 / Math.max(track.total_nodes, 1))
        return <article key={track.key}><div className="curriculum-head"><div><strong>{track.label}</strong><span>{stageLabels[track.current_stage] ?? track.current_stage} · {track.completed_nodes}/{track.total_nodes}</span></div>{active ? <span className="active-track"><CheckCircle2 size={15} />主路线</span> : <button type="button" className="secondary-button compact" aria-label={`将 ${track.label} 设为主路线`} disabled={Boolean(busy)} onClick={() => void switchTrack(track.key)}>{busy === track.key ? <LoaderCircle className="spin" size={15} /> : <Route size={15} />}设为主路线</button>}</div><div className="progress-track"><span style={{ width: `${percent}%` }} /></div></article>
      })}
    </div>
    {state.tracks.find((track) => track.key === state.active_track_key) && <div className="curriculum-path"><div className="path-heading"><strong>{state.tracks.find((track) => track.key === state.active_track_key)?.label} · 完整成长路径</strong><span>初级到架构师，共 12 个课程节点</span></div><div className="stage-grid">{state.tracks.find((track) => track.key === state.active_track_key)?.stages.map((stage) => <section key={stage.key} className={state.target_stage === stage.key ? 'selected' : ''}><header><span>{stage.label}</span><strong>{stage.nodes.filter((node) => node.completed).length}/{stage.nodes.length}</strong></header><ol>{stage.nodes.map((node) => <li key={node.key} className={node.completed ? 'completed' : ''}><span>{node.order}</span>{node.title}</li>)}</ol></section>)}</div></div>}
    <div className="algorithm-settings"><div><strong>数据结构与算法</strong><p>作为公共副线，在设置的天数替代主路线任务。</p></div><label>每周任务天数<select aria-label="每周算法任务天数" value={state.algorithm_days_per_week} disabled={busy === 'algorithms'} onChange={(event) => void setFrequency(Number(event.target.value))}>{[0, 1, 2, 3, 4, 5, 6, 7].map((days) => <option value={days} key={days}>{days} 天</option>)}</select></label></div>
  </section>
}
