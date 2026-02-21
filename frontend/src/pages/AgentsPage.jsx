import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import AppHeader from '../components/AppHeader'
import ConnectAgentModal from '../components/ConnectAgentModal'
import { apiRequest } from '../lib/api'

export default function AgentsPage({ token, username, onLogout, theme, toggleTheme }) {
  const [agents, setAgents] = useState([])
  const [showConnect, setShowConnect] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function loadAgents() {
    setError('')
    try {
      const data = await apiRequest('/api/agents', {
        token,
        onUnauthorized: onLogout,
      })
      setAgents(data)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    loadAgents()
  }, [])

  return (
    <main className="ambient-bg p-4 md:p-6 lg:p-8 animate-fade-in text-foreground">
      <div className="max-w-6xl mx-auto">
        <AppHeader
          title="A2A Agent Space"
          subtitle="Manage your connected A2A agents"
          rightActionLabel="Create"
          onRightAction={() => setShowConnect(true)}
          onLogout={onLogout}
          username={username}
          showAgentsNav={false}
          theme={theme}
          toggleTheme={toggleTheme}
        />
        {error && <div className="bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-xl mb-6">{error}</div>}
        <section className="mt-8 animate-slide-up">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {agents.map((agent) => (
              <article key={agent.id} className="glass-panel p-5 flex flex-col transition-transform duration-300 hover:-translate-y-1 hover:shadow-2xl hover:border-primary/50 group">
                <header className="flex items-start justify-between mb-3">
                  <h3 className="m-0 text-lg font-bold text-slate-800 dark:text-slate-100 group-hover:text-primary transition-colors">{agent.card_name}</h3>
                  <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full ${agent.mode === 'public' ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300' : 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300'}`}>{agent.mode}</span>
                </header>
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-4 line-clamp-2 flex-grow">{agent.card_description}</p>
                <small className="block text-xs text-slate-500 dark:text-slate-500 mb-4 truncate font-mono bg-slate-100 dark:bg-slate-800/50 p-1.5 rounded-md">{agent.base_url}</small>
                <footer className="flex items-center justify-between pt-4 border-t border-cardBorder mt-auto">
                  <span className="text-sm font-medium text-slate-500 dark:text-slate-400">{agent.skills?.length || 0} skills</span>
                  <button className="btn-primary py-1.5 px-4 text-sm" onClick={() => navigate(`/agents/${agent.id}`)}>
                    Interact
                  </button>
                </footer>
              </article>
            ))}
            {!agents.length && (
              <div className="col-span-full py-16 text-center border-2 border-dashed border-cardBorder rounded-2xl bg-card/30">
                <p className="text-lg text-slate-500 dark:text-slate-400 font-medium">No agents connected yet. Start by creating one.</p>
              </div>
            )}
          </div>
        </section>
        {showConnect && (
          <ConnectAgentModal
            token={token}
            onUnauthorized={onLogout}
            onClose={() => setShowConnect(false)}
            onCreated={loadAgents}
          />
        )}
      </div>
    </main>
  )
}
