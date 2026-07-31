import { useEffect, useMemo, useState } from 'react'
import { BarChart3, LoaderCircle } from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'

import { api } from '../api'
import type { AnalyticsView } from '../types'

const views = [
  ['overview', '统一总览'],
  ['learning', '学习进度'],
  ['radar', '雷达趋势'],
  ['repositories', '仓库质量'],
  ['ai-runs', 'AI 运行'],
] as const
const chartColors = ['#18794e', '#2563a7', '#9a6700', '#b42318', '#39756b', '#6b7280']

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

  const languageData = useMemo(() => {
    const languages: Record<string, number> = {}
    data?.repositories?.forEach((repository) => Object.entries(repository.languages).forEach(([name, value]) => {
      languages[name] = (languages[name] ?? 0) + value
    }))
    return Object.entries(languages).map(([name, value]) => ({ name, value }))
  }, [data])

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
        <div className="chart-grid">
          {data.track_progress && data.track_progress.length > 0 && <figure className="chart-panel" role="img" aria-label="路线完成度图表">
            <figcaption><strong>路线完成度</strong><span>通过审阅的节点占比</span></figcaption>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.track_progress.map((track) => ({ name: track.label, percent: Math.round(track.completed_nodes * 100 / Math.max(track.total_nodes, 1)) }))} margin={{ top: 10, right: 12, left: -18, bottom: 36 }}>
                <CartesianGrid stroke="#e4e9e6" vertical={false} /><XAxis dataKey="name" angle={-18} textAnchor="end" interval={0} height={62} fontSize={11} /><YAxis domain={[0, 100]} unit="%" fontSize={11} /><Tooltip formatter={(value) => [`${value}%`, '完成度']} /><Bar dataKey="percent" fill="#18794e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </figure>}
          {data.topics && Object.keys(data.topics).length > 0 && <figure className="chart-panel" role="img" aria-label="技术主题分布图表">
            <figcaption><strong>技术主题分布</strong><span>雷达信号数量</span></figcaption>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={Object.entries(data.topics).map(([name, value]) => ({ name, value }))} layout="vertical" margin={{ left: 18, right: 16 }}><CartesianGrid stroke="#e4e9e6" horizontal={false} /><XAxis type="number" allowDecimals={false} fontSize={11} /><YAxis type="category" dataKey="name" width={90} fontSize={11} /><Tooltip /><Bar dataKey="value" name="信号" fill="#2563a7" radius={[0, 4, 4, 0]} /></BarChart>
            </ResponsiveContainer>
          </figure>}
          {languageData.length > 0 && <figure className="chart-panel" role="img" aria-label="仓库语言分布图表">
            <figcaption><strong>仓库语言分布</strong><span>已连接仓库的代码构成</span></figcaption>
            <ResponsiveContainer width="100%" height={260}>
              <PieChart><Pie data={languageData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={88} paddingAngle={2} label>{languageData.map((item, index) => <Cell key={item.name} fill={chartColors[index % chartColors.length]} />)}</Pie><Tooltip /></PieChart>
            </ResponsiveContainer>
          </figure>}
          {!data.track_progress && !data.topics && languageData.length === 0 && data.metrics.length > 0 && <figure className="chart-panel wide" role="img" aria-label="核心指标对比图表">
            <figcaption><strong>核心指标对比</strong><span>当前统计范围</span></figcaption>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.metrics.map((metric) => ({ name: metric.label, value: metric.value, unit: metric.unit }))} margin={{ top: 10, right: 12, left: -18, bottom: 24 }}><CartesianGrid stroke="#e4e9e6" vertical={false} /><XAxis dataKey="name" fontSize={11} /><YAxis fontSize={11} /><Tooltip formatter={(value, _name, item) => [`${value}${item.payload.unit}`, item.payload.name]} /><Bar dataKey="value" fill="#39756b" radius={[4, 4, 0, 0]} /></BarChart>
            </ResponsiveContainer>
          </figure>}
        </div>
        {data.track_progress && data.track_progress.length > 0 && <div className="progress-section"><h2>路线明细</h2>{data.track_progress.map((track) => {
          const percent = Math.round(track.completed_nodes * 100 / Math.max(track.total_nodes, 1))
          return <div className="track-progress" key={track.track_key}><div><strong>{track.label}</strong><span>{track.completed_nodes}/{track.total_nodes} · {track.current_stage}</span></div><div className="progress-track" aria-label={`${track.label} ${percent}%`}><span style={{ width: `${percent}%` }} /></div></div>
        })}</div>}
        {data.metrics.length === 0 && <div className="empty-note centered"><BarChart3 /><span>当前范围还没有数据</span></div>}
      </>}
    </section>
  )
}
