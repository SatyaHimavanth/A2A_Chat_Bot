import { Navigate, Route, Routes } from 'react-router-dom'
import { useState, useEffect } from 'react'

import AgentDetailPage from './pages/AgentDetailPage'
import AgentsPage from './pages/AgentsPage'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import PlaygroundPage from './pages/PlaygroundPage'
import PromptsPage from './pages/PromptsPage'
import './App.css'

function isFutureIso(value) {
  if (!value) return false
  const timestamp = Date.parse(value)
  if (Number.isNaN(timestamp)) return false
  return timestamp > Date.now()
}

function hasUsableAuth(auth) {
  if (auth.accessToken && isFutureIso(auth.accessExpiresAt)) {
    return true
  }
  if (auth.refreshToken && isFutureIso(auth.refreshExpiresAt)) {
    return true
  }
  return false
}

function PrivateRoute({ auth, children }) {
  if (!hasUsableAuth(auth)) {
    return <Navigate to="/login" replace />
  }
  return children
}

export default function App({ auth, setAuth }) {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme')
    if (saved) return saved
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })

  useEffect(() => {
    localStorage.setItem('theme', theme)
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [theme])

  useEffect(() => {
    function syncAuthFromStorage() {
      setAuth({
        accessToken: localStorage.getItem('access_token') || '',
        refreshToken: localStorage.getItem('refresh_token') || '',
        username: localStorage.getItem('username') || '',
        accessExpiresAt: localStorage.getItem('access_expires_at') || '',
        refreshExpiresAt: localStorage.getItem('refresh_expires_at') || '',
      })
    }

    window.addEventListener('storage', syncAuthFromStorage)
    window.addEventListener('auth-updated', syncAuthFromStorage)
    return () => {
      window.removeEventListener('storage', syncAuthFromStorage)
      window.removeEventListener('auth-updated', syncAuthFromStorage)
    }
  }, [setAuth])

  useEffect(() => {
    if (!auth.accessToken && !auth.refreshToken) {
      return
    }
    if (hasUsableAuth(auth)) {
      return
    }
    handleLogout()
  }, [auth.accessToken, auth.refreshToken, auth.accessExpiresAt, auth.refreshExpiresAt])

  const toggleTheme = () => setTheme((t) => (t === 'light' ? 'dark' : 'light'))

  function handleLogout() {
    setAuth({
      accessToken: '',
      refreshToken: '',
      username: '',
      accessExpiresAt: '',
      refreshExpiresAt: '',
    })
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('username')
    localStorage.removeItem('access_expires_at')
    localStorage.removeItem('refresh_expires_at')
  }

  function handleAuthSuccess({
    accessToken,
    refreshToken,
    username,
    accessExpiresAt,
    refreshExpiresAt,
  }) {
    setAuth({ accessToken, refreshToken, username, accessExpiresAt, refreshExpiresAt })
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('refresh_token', refreshToken || '')
    localStorage.setItem('username', username)
    localStorage.setItem('access_expires_at', accessExpiresAt || '')
    localStorage.setItem('refresh_expires_at', refreshExpiresAt || '')
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={<LoginPage onAuthSuccess={handleAuthSuccess} />}
      />
      <Route
        path="/agents"
        element={
          <PrivateRoute auth={auth}>
            <AgentsPage
              token={auth.accessToken}
              username={auth.username}
              onLogout={handleLogout}
              theme={theme}
              toggleTheme={toggleTheme}
            />
          </PrivateRoute>
        }
      />
      <Route
        path="/agents/:agentId"
        element={
          <PrivateRoute auth={auth}>
            <AgentDetailPage
              token={auth.accessToken}
              username={auth.username}
              onLogout={handleLogout}
              theme={theme}
              toggleTheme={toggleTheme}
            />
          </PrivateRoute>
        }
      />
      <Route
        path="/agents/:agentId/chat"
        element={
          <PrivateRoute auth={auth}>
            <ChatPage
              token={auth.accessToken}
              username={auth.username}
              onLogout={handleLogout}
              theme={theme}
              toggleTheme={toggleTheme}
            />
          </PrivateRoute>
        }
      />
      <Route
        path="/playground"
        element={
          <PrivateRoute auth={auth}>
            <PlaygroundPage
              token={auth.accessToken}
              username={auth.username}
              onLogout={handleLogout}
              theme={theme}
              toggleTheme={toggleTheme}
            />
          </PrivateRoute>
        }
      />
      <Route
        path="/prompts"
        element={
          <PrivateRoute auth={auth}>
            <PromptsPage
              token={auth.accessToken}
              username={auth.username}
              onLogout={handleLogout}
              theme={theme}
              toggleTheme={toggleTheme}
            />
          </PrivateRoute>
        }
      />
      <Route
        path="*"
        element={
          <Navigate to={hasUsableAuth(auth) ? '/agents' : '/login'} replace />
        }
      />
    </Routes>
  )
}
