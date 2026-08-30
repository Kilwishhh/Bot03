import { useState, useEffect } from 'react'
import { Routes, Route, NavLink, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { getToken, setToken, clearToken, getBase, setBase, api } from './api'
import Dashboard from './pages/Dashboard'
import Users from './pages/Users'
import Strategies from './pages/Strategies'
import Signals from './pages/Signals'
import Trades from './pages/Trades'
import Positions from './pages/Positions'
import PaperConfig from './pages/PaperConfig'
import Risk from './pages/Risk'

const BASE_KEY = 'mk_api_base'
function saveBase(b: string) { localStorage.setItem(BASE_KEY, b) }
function loadBase(): string { return localStorage.getItem(BASE_KEY) || (import.meta.env.DEV ? '' : 'http://localhost:8000') }

function Login() {
  const [tok, setTokInput] = useState('')
  const [base, setBaseInput] = useState(loadBase())
  const [err, setErr] = useState('')
  const navigate = useNavigate()
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    saveBase(base)
    setToken(tok)
    try {
      await api('/admin/users', { query: { limit: 1 } })
      navigate('/dashboard')
    } catch (e: any) {
      setErr(e.detail || 'invalid token')
      clearToken()
    }
  }
  return (
    <div className="login">
      <form onSubmit={submit}>
        <h2>MK Trader Admin</h2>
        <label>API base</label>
        <input value={base} onChange={e => setBaseInput(e.target.value)} placeholder="(empty in dev = same origin)" />
        <label>Admin token</label>
        <input type="password" value={tok} onChange={e => setTokInput(e.target.value)} placeholder="X-Admin-Token" />
        {err && <div className="error">{err}</div>}
        <button type="submit">Sign in</button>
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
          <NavLink to="/users" className={({isActive}) => isActive ? 'active' : ''}>Users</NavLink>
          <NavLink to="/strategies" className={({isActive}) => isActive ? 'active' : ''}>Strategies</NavLink>
          <NavLink to="/signals" className={({isActive}) => isActive ? 'active' : ''}>Signals</NavLink>
          <NavLink to="/trades" className={({isActive}) => isActive ? 'active' : ''}>Trades</NavLink>
          <NavLink to="/positions" className={({isActive}) => isActive ? 'active' : ''}>Positions</NavLink>
          <NavLink to="/paper-config" className={({isActive}) => isActive ? 'active' : ''}>Paper Config</NavLink>
          <NavLink to="/risk" className={({isActive}) => isActive ? 'active' : ''}>Risk</NavLink>
          <a onClick={out} style={{cursor:'pointer', marginTop:24}}>Sign out</a>
        </nav>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/users" element={<Users />} />
          <Route path="/strategies" element={<Strategies />} />
          <Route path="/signals" element={<Signals />} />
          <Route path="/trades" element={<Trades />} />
          <Route path="/positions" element={<Positions />} />
          <Route path="/paper-config" element={<PaperConfig />} />
          <Route path="/risk" element={<Risk />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  const [authed, setAuthed] = useState(!!getToken())
  const loc = useLocation()
  useEffect(() => { setAuthed(!!getToken()) }, [loc.pathname])
  if (!authed && loc.pathname !== '/login') return <Navigate to="/login" />
  if (authed && loc.pathname === '/login') return <Navigate to="/dashboard" />
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<Shell />} />
    </Routes>
  )
}
