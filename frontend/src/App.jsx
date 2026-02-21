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
    setAuth({ token: '', username: '', expiresAt: '' })
    localStorage.removeItem('auth_token')
    localStorage.removeItem('username')
    localStorage.removeItem('expires_at')
  }

  function handleAuthSuccess({ token, username, expiresAt }) {
    setAuth({ token, username, expiresAt })
    localStorage.setItem('auth_token', token)
    localStorage.setItem('username', username)
    localStorage.setItem('expires_at', expiresAt || '')
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
          <PrivateRoute token={auth.token}>
            <AgentsPage
              token={auth.token}
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
          <PrivateRoute token={auth.token}>
            <AgentDetailPage
              token={auth.token}
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
          <PrivateRoute token={auth.token}>
            <ChatPage
              token={auth.token}
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
          <Navigate to={auth.token ? '/agents' : '/login'} replace />
        }
      />
    </Routes>
  )
}
