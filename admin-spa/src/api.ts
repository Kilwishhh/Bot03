// Token + API client. Always uses the same origin (FastAPI serves the SPA),
// so no API base field is needed and CORS is impossible.

const TOKEN_KEY = 'mk_admin_token'
const AUTH_TYPE_KEY = 'mk_admin_auth_type'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t)
  localStorage.setItem(AUTH_TYPE_KEY, 'admin-token')
}
export function setSessionToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t)
  localStorage.setItem(AUTH_TYPE_KEY, 'session')
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(AUTH_TYPE_KEY)
}

export class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) { super(detail); this.status = status; this.detail = detail }
}

export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: any; query?: Record<string, any> } = {}
): Promise<T> {
  // Always same-origin. The SPA is served by FastAPI from /admin, so all API
  // routes are reachable as same-origin. This prevents cross-origin token
  // issues, mixed-content warnings, and stale localhost entries.
  const url = new URL(path, window.location.origin)
  if (opts.query) {
    Object.entries(opts.query).forEach(([k, v]) => {
      if (v != null) url.searchParams.set(k, String(v))
    })
  }
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const tok = getToken()
  if (tok) {
    if (localStorage.getItem(AUTH_TYPE_KEY) === 'session') headers['Authorization'] = `Bearer ${tok}`
    else headers['X-Admin-Token'] = tok
  }
  const res = await fetch(url.toString(), {
    method: opts.method || 'GET',
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  })
  if (res.status === 401) {
    clearToken()
  }
  const text = await res.text()
  if (!res.ok) {
    let detail = text
    try { detail = JSON.parse(text).detail || text } catch {}
    throw new ApiError(res.status, detail)
  }
  return text ? JSON.parse(text) : ({} as T)
}
