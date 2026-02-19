const API_BASE = import.meta.env.VITE_API_BASE || ''

async function parseBody(res) {
  const text = await res.text()
  if (!text) return {}
  try {
    return JSON.parse(text)
  } catch {
    return { detail: text }
  }
}

export async function apiRequest(
  path,
  { method = 'GET', token, body, headers = {}, onUnauthorized } = {},
) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  })

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
