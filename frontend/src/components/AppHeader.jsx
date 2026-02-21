import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function AppHeader({
  title,
  subtitle,
  rightActionLabel,
  onRightAction,
  onLogout,
  username,
  showAgentsNav = true,
}) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const initial = (username || '?').charAt(0).toUpperCase()

  return (
    <header className="topbar">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <div className="topbar-actions">
        {rightActionLabel && (
          <button onClick={onRightAction}>{rightActionLabel}</button>
        )}
        {showAgentsNav && (
          <button className="ghost" onClick={() => navigate('/agents')}>
            Agents
          </button>
        )}
        <div className="profile-wrap">
          <button
            className="profile-avatar"
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label="Profile menu"
          >
            {initial}
          </button>
          {open && (
            <div className="profile-menu">
              <p className="profile-name">{username}</p>
              <button className="ghost" type="button" onClick={onLogout}>
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
