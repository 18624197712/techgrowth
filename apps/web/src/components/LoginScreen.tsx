import { FormEvent, useState } from 'react'
import { KeyRound, LoaderCircle, ShieldCheck } from 'lucide-react'

import { api } from '../api'
import type { User } from '../types'

type Stage = 'login' | 'totp_setup' | 'totp'

export function LoginScreen({ onAuthenticated }: { onAuthenticated: (user: User) => void }) {
  const [stage, setStage] = useState<Stage>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [totpSecret, setTotpSecret] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submitLogin(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await api<{ next: Stage }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      setStage(result.next)
      if (result.next === 'totp_setup') {
        const setup = await api<{ secret: string }>('/auth/totp/setup')
        setTotpSecret(setup.secret)
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '登录失败')
    } finally {
      setBusy(false)
    }
  }

  async function submitTotp(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const endpoint = stage === 'totp_setup' ? '/auth/totp/confirm' : '/auth/totp/verify'
      const result = await api<{ csrf_token: string; recovery_codes?: string[] }>(endpoint, {
        method: 'POST',
        body: JSON.stringify({ code }),
      })
      sessionStorage.setItem('tg_csrf', result.csrf_token)
      if (result.recovery_codes?.length) {
        setRecoveryCodes(result.recovery_codes)
        return
      }
      const user = await api<User>('/auth/me')
      onAuthenticated(user)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '验证码错误')
    } finally {
      setBusy(false)
    }
  }

  if (recoveryCodes.length) {
    return (
      <main className="auth-page">
        <section className="auth-panel">
          <ShieldCheck size={30} aria-hidden="true" />
          <h1>保存恢复码</h1>
          <div className="recovery-grid">
            {recoveryCodes.map((item) => <code key={item}>{item}</code>)}
          </div>
          <button className="primary-button" onClick={() => window.location.reload()}>完成</button>
        </section>
      </main>
    )
  }

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="brand-mark"><KeyRound size={22} aria-hidden="true" /></div>
        <p className="brand-name">TechGrowth</p>
        <h1>{stage === 'login' ? '登录 TechGrowth' : '双重验证'}</h1>
        {stage === 'login' ? (
          <form onSubmit={submitLogin}>
            <label htmlFor="email">邮箱</label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <label htmlFor="password">密码</label>
            <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={12} required />
            <button className="primary-button" disabled={busy}>
              {busy && <LoaderCircle className="spin" size={17} aria-hidden="true" />}登录
            </button>
          </form>
        ) : (
          <form onSubmit={submitTotp}>
            {stage === 'totp_setup' && (
              <div className="totp-secret"><span>认证器密钥</span><code>{totpSecret}</code></div>
            )}
            <label htmlFor="totp">动态验证码</label>
            <input id="totp" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} required />
            <button className="primary-button" disabled={busy}>验证</button>
          </form>
        )}
        {error && <p className="form-error" role="alert">{error}</p>}
      </section>
    </main>
  )
}
