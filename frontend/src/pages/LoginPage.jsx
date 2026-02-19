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
    <main className="login-shell">
      <section className="login-panel">
        <h1>A2A Console</h1>
        <p>
          {isRegister
            ? 'Create an account to save connected agents.'
            : 'Sign in to continue.'}
        </p>
        <div className="auth-toggle">
          <button
            type="button"
            className={!isRegister ? 'active' : 'ghost'}
            onClick={() => setMode('login')}
          >
            Login
          </button>
          <button
            type="button"
            className={isRegister ? 'active' : 'ghost'}
            onClick={() => setMode('register')}
          >
            Register
          </button>
        </div>
        <form onSubmit={submit}>
          <label>
            Username
            <input
              value={form.username}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, username: e.target.value }))
              }
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={form.password}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, password: e.target.value }))
              }
            />
          </label>
          <button type="submit" disabled={loading}>
            {loading
              ? 'Please wait...'
              : isRegister
                ? 'Register and Login'
                : 'Login'}
          </button>
        </form>
        {error && <div className="error">{error}</div>}
      </section>
    </main>
  )
}
