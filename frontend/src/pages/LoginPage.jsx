import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { apiRequest } from '../lib/api'

export default function LoginPage({ onAuthSuccess }) {
  const navigate = useNavigate()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ username: 'admin', password: 'admin' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const isRegister = mode === 'register'

  async function submit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const path = isRegister ? '/api/register' : '/api/login'
      const data = await apiRequest(path, {
        method: 'POST',
        body: form,
      })
      onAuthSuccess({
        token: data.token,
        username: data.username,
        expiresAt: data.expires_at,
      })
      navigate('/agents', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="ambient-bg flex items-center justify-center p-4">
      <section className="glass-panel w-full max-w-[400px] p-8 animate-slide-up">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-purple-500 bg-clip-text text-transparent mb-2">A2A Console</h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            {isRegister
              ? 'Create an account to save connected agents.'
              : 'Sign in to your intelligent workspace.'}
          </p>
        </div>

        <div className="flex bg-slate-100 dark:bg-slate-800/50 p-1 rounded-xl mb-6">
          <button
            type="button"
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${!isRegister ? 'bg-white dark:bg-slate-700 shadow-sm text-primary' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}
            onClick={() => setMode('login')}
          >
            Login
          </button>
          <button
            type="button"
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${isRegister ? 'bg-white dark:bg-slate-700 shadow-sm text-primary' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}
            onClick={() => setMode('register')}
          >
            Register
          </button>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-5">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-300">
            Username
            <input
              className="input-base"
              value={form.username}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, username: e.target.value }))
              }
              placeholder="Enter your username"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-300">
            Password
            <input
              type="password"
              className="input-base"
              value={form.password}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, password: e.target.value }))
              }
              placeholder="••••••••"
            />
          </label>

          <button type="submit" className="btn-primary mt-2 py-3" disabled={loading}>
            {loading
              ? 'Please wait...'
              : isRegister
                ? 'Register and Login'
                : 'Login securely'}
          </button>
        </form>
        {error && <div className="mt-6 bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-xl text-sm text-center">{error}</div>}
      </section>
    </main>
  )
}
