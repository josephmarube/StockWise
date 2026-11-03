// Thin fetch wrapper: attaches the JWT, normalises errors, handles 401 globally.
const BASE = import.meta.env.VITE_API_URL || ''
const TOKEN_KEY = 'stockwise.token'

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export const tokenStore = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } },
  set: (t) => { try { localStorage.setItem(TOKEN_KEY, t) } catch { /* ignore */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ } },
}

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.detail || `Request failed (${status})`)
    this.status = status
    this.body = body || {}
    this.fields = body?.fields || {}
  }
}

function qs(params) {
  if (!params) return ''
  const p = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '' && v !== false) p.set(k, v)
  })
  const s = p.toString()
  return s ? `?${s}` : ''
}

async function request(method, path, { body, params, raw } = {}) {
  const headers = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res
  try {
    res = await fetch(BASE + path + qs(params), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, { detail: 'Cannot reach the server. Check your internet connection and try again.' })
  }

  if (res.status === 401 && !path.startsWith('/api/auth/login')) {
    onUnauthorized()
  }
  if (raw && res.ok) return res
  if (res.status === 204) return null

  const data = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 403) throw new ApiError(403, { detail: 'You do not have permission to do that.' })
    if (res.status >= 500) throw new ApiError(res.status, { detail: data?.detail || 'Something went wrong on the server. No changes were saved.' })
    throw new ApiError(res.status, data)
  }
  return data
}

export const api = {
  get: (path, params) => request('GET', path, { params }),
  post: (path, body) => request('POST', path, { body }),
  patch: (path, body) => request('PATCH', path, { body }),
  put: (path, body) => request('PUT', path, { body }),
  del: (path) => request('DELETE', path),
  async download(path, params, fallbackName) {
    const res = await request('GET', path, { params, raw: true })
    const blob = await res.blob()
    const cd = res.headers.get('Content-Disposition') || ''
    const name = /filename="([^"]+)"/.exec(cd)?.[1] || fallbackName
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  },
}
