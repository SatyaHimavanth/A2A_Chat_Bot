import { useNavigate } from 'react-router-dom'

export default function AppHeader({
  title,
  subtitle,
  rightActionLabel,
  onRightAction,
  onLogout,
  showAgentsNav = true,
}) {
  const navigate = useNavigate()

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
        <button className="ghost" onClick={onLogout}>
          Logout
        </button>
      </div>
    </header>
  )
}
