import { StrictMode, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import './index.css'
import App from './App.jsx'

function Root() {
  const [auth, setAuth] = useState({
    token: localStorage.getItem('auth_token') || '',
    username: localStorage.getItem('username') || '',
    expiresAt: localStorage.getItem('expires_at') || '',
  })

  const expiresAtTs = useMemo(
    () => (auth.expiresAt ? Date.parse(auth.expiresAt) : 0),
    [auth.expiresAt],
  )

  useEffect(() => {
    if (!auth.token || !expiresAtTs) return
    if (Date.now() >= expiresAtTs) {
      setAuth({ token: '', username: '', expiresAt: '' })
      localStorage.removeItem('auth_token')
      localStorage.removeItem('username')
      localStorage.removeItem('expires_at')
      return
    }
    const timeout = setTimeout(() => {
      setAuth({ token: '', username: '', expiresAt: '' })
      localStorage.removeItem('auth_token')
      localStorage.removeItem('username')
      localStorage.removeItem('expires_at')
    }, expiresAtTs - Date.now())
    return () => clearTimeout(timeout)
  }, [auth.token, expiresAtTs])

  return (
    <BrowserRouter>
      <App auth={auth} setAuth={setAuth} />
    </BrowserRouter>
  )
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
