import { useState } from 'react'

import { apiRequest } from '../lib/api'

export default function ConnectAgentModal({
  token,
  onUnauthorized,
  onClose,
  onCreated,
}) {
  const [form, setForm] = useState({
    base_url: 'http://localhost:10000',
    mode: 'public',
    auth_token: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const payload = {
        ...form,
        auth_token: form.mode === 'authorized' ? form.auth_token : null,
      }
      const data = await apiRequest('/api/agents', {
        method: 'POST',
        token,
        body: payload,
        onUnauthorized,
      })
      onCreated(data)
      onClose()
    } catch (err) {
      if (err.message.toLowerCase().includes('request failed')) {
        setError('Agent cannot be connected right now.')
      } else {
        setError(err.message)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Connect New Agent</h3>
        <form onSubmit={submit}>
          <label>
            Hosted URL
            <input
              value={form.base_url}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, base_url: e.target.value }))
              }
              placeholder="https://your-agent-host"
            />
          </label>
          <label>
            Mode
            <select
              value={form.mode}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, mode: e.target.value }))
              }
            >
              <option value="public">Public</option>
              <option value="authorized">Authorized</option>
            </select>
          </label>
          {form.mode === 'authorized' && (
            <label>
              Bearer Token
              <input
                value={form.auth_token}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, auth_token: e.target.value }))
                }
                placeholder="token"
              />
            </label>
          )}
          <div className="modal-actions">
            <button type="button" className="ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" disabled={loading}>
              {loading ? 'Connecting...' : 'Connect'}
            </button>
          </div>
        </form>
        {error && <div className="error">{error}</div>}
      </div>
    </div>
  )
}
