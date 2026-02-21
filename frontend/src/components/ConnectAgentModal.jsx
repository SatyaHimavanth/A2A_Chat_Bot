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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in" onClick={onClose}>
      <div className="glass-panel w-full max-w-md p-6 relative" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
          aria-label="Close"
        >
          ✕
        </button>
        <h3 className="mt-0 pt-1 mb-6 text-xl font-bold bg-gradient-to-r from-primary to-purple-500 bg-clip-text text-transparent">Connect New Agent</h3>

        <form onSubmit={submit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-300">
            Hosted URL
            <input
              className="input-base"
              value={form.base_url}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, base_url: e.target.value }))
              }
              placeholder="https://your-agent-host"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-300">
            Mode
            <select
              className="input-base cursor-pointer"
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
            <label className="flex flex-col gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-300 animate-slide-up">
              Bearer Token
              <input
                className="input-base"
                value={form.auth_token}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, auth_token: e.target.value }))
                }
                placeholder="Secure token"
              />
            </label>
          )}

          {error && <div className="bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-xl text-sm mt-2">{error}</div>}

          <div className="flex justify-end gap-3 mt-4">
            <button type="button" className="btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Connecting...' : 'Connect'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
