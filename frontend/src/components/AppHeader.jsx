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
  showPromptsNav = false,
  theme,
  toggleTheme,
}) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const initial = (username || '?').charAt(0).toUpperCase()

  return (
    <header className="flex justify-between items-center gap-4 mb-6 sticky top-0 z-20 bg-background/80 backdrop-blur-md pb-4 pt-2 -mx-2 px-2 border-b border-transparent">
      <div>
        <h1 className="m-0 text-2xl font-bold bg-gradient-to-r from-primary to-purple-500 bg-clip-text text-transparent">{title}</h1>
        {subtitle && <p className="m-0 mt-1 text-sm text-slate-500 dark:text-slate-400 font-medium">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        {rightActionLabel && (
          <button className="btn-primary" onClick={onRightAction}>{rightActionLabel}</button>
        )}
        {showAgentsNav && (
          <button className="btn-ghost" onClick={() => navigate('/agents')}>
            Agents
          </button>
        )}
        {showPromptsNav && (
          <button className="btn-ghost" onClick={() => navigate('/prompts')}>
            Prompts
          </button>
        )}

        {toggleTheme && (
          <button
            onClick={toggleTheme}
            className="w-9 h-9 flex items-center justify-center rounded-full bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-700 transition-colors"
            title="Toggle Theme"
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        )}

        <div className="relative">
          <button
            className="w-10 h-10 rounded-full flex items-center justify-center bg-gradient-to-br from-primary to-blue-600 text-white font-bold shadow-lg shadow-primary/30 hover:shadow-primary/50 transition-shadow transition-transform active:scale-95"
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label="Profile menu"
          >
            {initial}
          </button>
          {open && (
            <div className="absolute right-0 top-12 min-w-[180px] border border-cardBorder rounded-xl bg-card backdrop-blur-md shadow-2xl p-2 z-50 animate-fade-in origin-top-right">
              <p className="m-0 mb-3 px-2 text-sm text-slate-800 dark:text-slate-200 font-semibold border-b border-cardBorder pb-2">{username}</p>
              <button className="btn-ghost w-full text-left justify-start" type="button" onClick={onLogout}>
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
