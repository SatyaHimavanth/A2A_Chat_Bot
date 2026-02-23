import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import './index.css'
import App from './App.jsx'

function Root() {
  const [auth, setAuth] = useState({
    accessToken: localStorage.getItem('access_token') || '',
    refreshToken: localStorage.getItem('refresh_token') || '',
    username: localStorage.getItem('username') || '',
    accessExpiresAt: localStorage.getItem('access_expires_at') || '',
    refreshExpiresAt: localStorage.getItem('refresh_expires_at') || '',
  })

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
