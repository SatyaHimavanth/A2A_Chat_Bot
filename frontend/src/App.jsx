import { Navigate, Route, Routes } from 'react-router-dom'
import { useState, useEffect } from 'react'

import AgentDetailPage from './pages/AgentDetailPage'
import AgentsPage from './pages/AgentsPage'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import './App.css'

function PrivateRoute({ token, children }) {
  if (!token) {
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
          <PrivateRoute token={auth.accessToken}>
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
          <PrivateRoute token={auth.accessToken}>
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
          <PrivateRoute token={auth.accessToken}>
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
        path="*"
        element={
          <Navigate to={auth.accessToken ? '/agents' : '/login'} replace />
        }
      />
    </Routes>
  )
}
