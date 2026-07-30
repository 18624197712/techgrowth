import { useEffect, useState } from 'react'
import { BarChart3, LoaderCircle } from 'lucide-react'

import { api } from '../api'
import type { AnalyticsView } from '../types'

const views = [
  ['overview', '统一总览'],
  ['learning', '学习进度'],
  ['radar', '雷达趋势'],
  ['repositories', '仓库质量'],
  ['ai-runs', 'AI 运行'],
] as const

export function DataPlatform() {
  const [view, setView] = useState<(typeof views)[number][0]>('overview')
  const [range, setRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d')
  const [data, setData] = useState<AnalyticsView | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setData(null)
    setError('')
    api<AnalyticsView>(`/analytics/${view}?range=${range}`)
      .then(setData)
      .catch((reason) => setError(reason instanceof Error ? reason.message : '无法读取成长数据'))
  }, [range, view])

  return (
    <section>
      <header className="section-header">
        <div><p>数据中台</p><h1>成长数据总览</h1></div>
        <label className="range-select">统计范围
          <select value={range} onChange={(event) => setRange(event.target.value as typeof range)}>
            <option value="7d">最近 7 天</option><option value="30d">最近 30 天</option>
            <option value="90d">最近 90 天</option><option value="all">全部</option>
          </select>
        </label>
      </header>
      <div className="data-tabs" role="tablist" aria-label="数据中台视图">
        {views.map(([key, label]) => <button type="button" role="tab" aria-selected={view === key} className={view === key ? 'active' : ''} key={key} onClick={() => setView(key)}>{label}</button>)}
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {!data && !error && <div className="loading-state compact-state"><LoaderCircle className="spin" /><span>正在计算</span></div>}
      {data && <>
        <div className="metric-grid">
          {data.metrics.map((metric) => <article key={metric.key} className="metric-card"><span>{metric.label}</span><strong>{metric.value}<small>{metric.unit}</small></strong><p>{metric.definition}</p></article>)}
        </div>
        {data.track_progress && data.track_progress.length > 0 && <div className="progress-section"><h2>路线进度</h2>{data.track_progress.map((track) => {
          const percent = Math.round(track.completed_nodes * 100 / Math.max(track.total_nodes, 1))
          return <div className="track-progress" key={track.track_key}><div><strong>{track.label}</strong><span>{track.completed_nodes}/{track.total_nodes} · {track.current_stage}</span></div><div className="progress-track" aria-label={`${track.label} ${percent}%`}><span style={{ width: `${percent}%` }} /></div></div>
        })}</div>}
        {data.metrics.length === 0 && <div className="empty-note centered"><BarChart3 /><span>当前范围还没有数据</span></div>}
      </>}
    </section>
  )
}
