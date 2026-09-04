import { useState, useEffect } from 'react'
import { Routes, Route, NavLink, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { getToken, setToken, setSessionToken, clearToken, api } from './api'
import Dashboard from './pages/Dashboard'
import Logs from './pages/Logs'
import Users from './pages/Users'
import Strategies from './pages/Strategies'
import Signals from './pages/Signals'
import Trades from './pages/Trades'
import Positions from './pages/Positions'
import PaperConfig from './pages/PaperConfig'
import Risk from './pages/Risk'
import Settings from './pages/Settings'

function Login({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [tok, setTokInput] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [tokenMode, setTokenMode] = useState(false)
  const [err, setErr] = useState('')
  const navigate = useNavigate()
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    try {
      if (tokenMode) {
        setToken(tok)
        await api('/admin/users', { query: { limit: 1 } })
      } else {
        const result = await api<{ token: string; user: { role: string } }>('/auth/login', {
          method: 'POST',
          body: { email, password },
        })
        if (result.user.role !== 'admin') throw new Error('admin role required')
        setSessionToken(result.token)
        await api('/admin/users', { query: { limit: 1 } })
      }
      onAuthenticated()
      navigate('/dashboard')
    } catch (e: any) {
      setErr(e.detail || e.message || (tokenMode ? 'invalid token' : 'invalid email or password'))
      clearToken()
    }
  }
  return (
    <div className="login">
      <form onSubmit={submit}>
        <h2>MK Trader Admin</h2>
        {tokenMode ? <>
          <label>Admin token</label>
          <input type="password" value={tok} onChange={e => setTokInput(e.target.value)} placeholder="X-Admin-Token" autoFocus />
        </> : <>
          <label>Email</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" autoFocus />
          <label>Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" />
        </>}
        {err && <div className="error">{err}</div>}
        <button type="submit">Sign in</button>
        <button type="button" onClick={() => { setTokenMode(!tokenMode); setErr('') }}>
          {tokenMode ? 'Sign in with account' : 'Use admin token'}
        </button>
      </form>
    </div>
  )
}

function Shell() {
  const nav = useNavigate()
  const out = () => { clearToken(); nav('/login') }
  return (
    <div className="app">
      <aside className="sidebar">
        <h1>MK Trader</h1>
        <nav>
          <NavLink to="/dashboard" className={({isActive}) => isActive ? 'active' : ''}>Dashboard</NavLink>
          <NavLink to="/logs" className={({isActive}) => isActive ? 'active' : ''}>Logs</NavLink>
          <NavLink to="/users" className={({isActive}) => isActive ? 'active' : ''}>Users</NavLink>
          <NavLink to="/strategies" className={({isActive}) => isActive ? 'active' : ''}>Strategies</NavLink>
          <NavLink to="/signals" className={({isActive}) => isActive ? 'active' : ''}>Signals</NavLink>
          <NavLink to="/trades" className={({isActive}) => isActive ? 'active' : ''}>Trades</NavLink>
          <NavLink to="/positions" className={({isActive}) => isActive ? 'active' : ''}>Positions</NavLink>
          <NavLink to="/paper-config" className={({isActive}) => isActive ? 'active' : ''}>Paper Config</NavLink>
          <NavLink to="/risk" className={({isActive}) => isActive ? 'active' : ''}>Risk</NavLink>
          <NavLink to="/settings" className={({isActive}) => isActive ? 'active' : ''}>Settings</NavLink>
          <a onClick={out} style={{cursor:'pointer', marginTop:24}}>Sign out</a>
        </nav>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/users" element={<Users />} />
          <Route path="/strategies" element={<Strategies />} />
          <Route path="/signals" element={<Signals />} />
          <Route path="/trades" element={<Trades />} />
          <Route path="/positions" element={<Positions />} />
          <Route path="/paper-config" element={<PaperConfig />} />
          <Route path="/risk" element={<Risk />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  const [authed, setAuthed] = useState(false)
  const [checking, setChecking] = useState(true)
  const loc = useLocation()

  // Validate ONCE on mount. Do NOT re-validate on route changes — that causes
  // the "refresh kicks me to /login" bug. Each page handles its own API errors.
  useEffect(() => {
    let cancelled = false
    const validate = async () => {
      const tok = getToken()
      if (!tok) {
        if (!cancelled) { setAuthed(false); setChecking(false) }
        return
      }
      try {
        await api('/admin/users', { query: { limit: 1 } })
        if (!cancelled) { setAuthed(true); setChecking(false) }
      } catch {
        if (!cancelled) {
          clearToken()
          setAuthed(false)
          setChecking(false)
        }
      }
    }
    validate()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])  // <-- empty deps = only on mount (initial page load / hard refresh)

  if (checking) return <div className="loading">Loading…</div>
  if (!authed && loc.pathname !== '/login') return <Navigate to="/login" />
  if (authed && loc.pathname === '/login') return <Navigate to="/dashboard" />
  return (
    <Routes>
      <Route path="/login" element={<Login onAuthenticated={() => setAuthed(true)} />} />
      <Route path="/*" element={<Shell />} />
    </Routes>
  )
}
