import { useState, useEffect } from 'react'
import { api } from '../api'
import { absoluteTime, relativeTime, useCurrentTime } from '../utils/time'

const STATUS_COLORS: Record<string, string> = {
  active: 'green', inactive: 'gray', pending: 'yellow', banned: 'red'
}
const ROLE_COLORS: Record<string, string> = {
  admin: 'purple', user: 'blue'
}

export default function Users() {
  const now = useCurrentTime()
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [action, setAction] = useState('')
  const [msg, setMsg] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const per = 20

  const load = async () => {
    setLoading(true)
    try {
      const data = await api('/admin/users', { query: { limit: 100 } })
      setUsers(Array.isArray(data) ? data : [])
    } catch { setUsers([]) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const act = async (id: string, type: 'activate' | 'delete') => {
    setAction(id + type)
    setMsg('')
    try {
      if (type === 'delete') {
        if (!confirm('Delete this user and all their data?')) { setAction(''); return }
        await api(`/admin/users/${id}`, { method: 'DELETE' })
        setMsg('User deleted')
      } else {
        await api(`/admin/users/${id}/${type}`, { method: 'POST' })
        setMsg('User activated')
      }
      await load()
    } catch (e: any) { setMsg(e.detail || 'Error') }
    setAction('')
    setTimeout(() => setMsg(''), 3000)
  }

  const filtered = users.filter(u =>
    !search || u.email?.includes(search) || u.display_name?.includes(search)
  )
  const totalPages = Math.max(1, Math.ceil(filtered.length / per))
  const paged = filtered.slice((page - 1) * per, page * per)

  return (
    <div>
      <h2 className="page-title">Users</h2>
      <div className="toolbar">
        <input placeholder="Search email or name..." value={search} onChange={e => { setSearch(e.target.value); setPage(1) }} />
        <button onClick={load}>Refresh</button>
        {msg && <span style={{color: msg.includes('deleted') || msg.includes('activated') ? 'var(--green)' : 'var(--red)'}}>{msg}</span>}
      </div>
      {loading ? <p className="muted">Loading...</p> : (
        <>
          <table>
            <thead>
              <tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Created</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {paged.map(u => (
                <tr key={u.id}>
                  <td>{u.display_name || '—'}</td>
                  <td>{u.email}</td>
                  <td><span className={`badge ${ROLE_COLORS[u.role] || 'gray'}`}>{u.role}</span></td>
                  <td><span className={`badge ${STATUS_COLORS[u.status] || 'gray'}`}>{u.status}</span></td>
                  <td className="muted" title={absoluteTime(u.created_at)}>{relativeTime(u.created_at, now)}</td>
                  <td>
                    {u.status !== 'active' && (
                      <button className="success" style={{marginRight:6}} onClick={() => act(u.id, 'activate')}
                        disabled={!!action}>Activate</button>
                    )}
                    <button className="danger" onClick={() => act(u.id, 'delete')}
                      disabled={!!action}>Delete</button>
                  </td>
                </tr>
              ))}
              {paged.length === 0 && <tr><td colSpan={6} className="empty">No users</td></tr>}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div className="toolbar" style={{marginTop:8}}>
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Prev</button>
              <span>{page} / {totalPages}</span>
              <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Next</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
