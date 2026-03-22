const API_BASE = import.meta.env.VITE_API_BASE || ''

function emitAuthUpdated() {
  window.dispatchEvent(new Event('auth-updated'))
}

async function parseBody(res) {
  const text = await res.text()
  if (!text) return {}
  try {
    return JSON.parse(text)
  } catch {
    return { detail: text }
  }
}

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null

  const res = await fetch(`${API_BASE}/api/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!res.ok) return null
  const payload = await parseBody(res)
  const nextAccess = payload.access_token
  if (!nextAccess) return null

  localStorage.setItem('access_token', nextAccess)
  localStorage.setItem('access_expires_at', payload.access_expires_at || '')
  if (payload.refresh_token) {
    localStorage.setItem('refresh_token', payload.refresh_token)
  }
  if (payload.refresh_expires_at) {
    localStorage.setItem('refresh_expires_at', payload.refresh_expires_at)
  }
  emitAuthUpdated()
  return nextAccess
}

export async function apiRequest(
  path,
  { method = 'GET', token, body, headers = {}, onUnauthorized, _retried = false } = {},
) {
  const bearerToken = token || localStorage.getItem('access_token') || ''
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      ...(bearerToken ? { Authorization: `Bearer ${bearerToken}` } : {}),
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (
    res.status === 401 &&
    !_retried &&
    !['/api/login', '/api/register', '/api/refresh'].includes(path)
  ) {
    const nextAccessToken = await refreshAccessToken()
    if (nextAccessToken) {
      return apiRequest(path, {
        method,
        token: nextAccessToken,
        body,
        headers,
        onUnauthorized,
        _retried: true,
      })
    }
  }
  if (res.status === 401 && onUnauthorized) {
    onUnauthorized()
    throw new Error('Session expired. Please login again.')
  }
  if (!res.ok) {
    const payload = await parseBody(res)
    throw new Error(payload.detail || `Request failed (${res.status})`)
  }
  return parseBody(res)
}

export function createSseUrl(path) {
  return `${API_BASE}${path}`
}

export function createWebSocketUrl(path, query = {}) {
  const base = API_BASE || window.location.origin
  const url = new URL(`${base}${path}`)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== '') {
      url.searchParams.set(key, String(value))
    }
  })
  return url.toString()
}
