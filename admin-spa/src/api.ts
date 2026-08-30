const TOKEN_KEY = 'mk_admin_token'
const BASE_KEY = 'mk_api_base'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function setToken(t: string) { localStorage.setItem(TOKEN_KEY, t) }
export function clearToken() { localStorage.removeItem(TOKEN_KEY) }
export function getBase(): string {
  const stored = localStorage.getItem(BASE_KEY)
  if (stored) return stored
  // In dev, Vite proxy serves same-origin; in prod, use current origin
  return (import.meta as any).env.DEV ? window.location.origin : window.location.origin
}
export function setBase(b: string) { localStorage.setItem(BASE_KEY, b) }

export class ApiError extends Error {
  constructor(public status: number, public detail: string) { super(detail) }
}

export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: any; query?: Record<string, any> } = {}
): Promise<T> {
  const base = getBase()
  const url = new URL(path, base)
  if (opts.query) {
    Object.entries(opts.query).forEach(([k, v]) => {
      if (v != null) url.searchParams.set(k, String(v))
    })
  }
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const tok = getToken()
  if (tok) headers['X-Admin-Token'] = tok
  const res = await fetch(url.toString(), {
    method: opts.method || 'GET',
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  })
  const text = await res.text()
  if (!res.ok) {
    let detail = text
    try { detail = JSON.parse(text).detail || text } catch {}
    throw new ApiError(res.status, detail)
  }
  return text ? JSON.parse(text) : ({} as T)
}
