import { useEffect, useState } from 'react'

import { ApiError, api } from './api'
import { LoginScreen } from './components/LoginScreen'
import { Workbench } from './components/Workbench'
import type { User } from './types'
import './styles.css'

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    api<User>('/auth/me')
      .then(setUser)
      .catch((error) => {
        if (!(error instanceof ApiError) || error.status !== 401) console.error(error)
      })
      .finally(() => setChecking(false))
  }, [])

  if (checking) return <main className="boot-screen"><span className="boot-mark">TG</span></main>
  if (!user) return <LoginScreen onAuthenticated={setUser} />
  return <Workbench user={user} onLogout={() => setUser(null)} />
}

