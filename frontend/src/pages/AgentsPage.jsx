import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import AppHeader from '../components/AppHeader'
import ConnectAgentModal from '../components/ConnectAgentModal'
import { apiRequest } from '../lib/api'

const AGENTS_LOAD_TIMEOUT_MS = Number(import.meta.env.VITE_AGENTS_LOAD_TIMEOUT_MS || 30000)

export default function AgentsPage({ token, username, onLogout, theme, toggleTheme }) {
  const [agents, setAgents] = useState([])
  const [showConnect, setShowConnect] = useState(false)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const navigate = useNavigate()

  async function loadAgents() {
    setIsLoading(true)
    setError('')
    try {
      const data = await Promise.race([
        apiRequest('/api/agents', {
          token,
          onUnauthorized: onLogout,
        }),
        new Promise((_, reject) =>
          setTimeout(
            () => reject(new Error('Loading agents timed out. Please try again.')),
            AGENTS_LOAD_TIMEOUT_MS,
          ),
        ),
      ])
      setAgents(data)
    } catch (err) {
      setAgents([])
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadAgents()
  }, [])

  const normalizedQuery = searchQuery.trim().toLowerCase()
  const filteredAgents = agents.filter((agent) => {
    if (!normalizedQuery) return true
    const name = (agent.card_name || '').toLowerCase()
    const description = (agent.card_description || '').toLowerCase()
    return name.includes(normalizedQuery) || description.includes(normalizedQuery)
  })

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
        {error && (
          <div className="bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-xl mb-6 flex items-center justify-between gap-4">
            <span>{error || 'Error loading agents.'}</span>
            <button className="btn-ghost py-1.5 px-3 text-xs" onClick={loadAgents}>
              Retry
            </button>
          </div>
        )}
        <section className="mt-8 animate-slide-up">
          <div className="mb-5">
            <input
              type="text"
              className="input-base"
              placeholder="Search agents by name or description..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {isLoading &&
              Array.from({ length: 6 }).map((_, idx) => (
                <article
                  key={`agent-skeleton-${idx}`}
                  className="glass-panel p-5 animate-pulse"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="h-5 w-2/3 rounded bg-slate-200 dark:bg-slate-700" />
                    <div className="h-5 w-16 rounded-full bg-slate-200 dark:bg-slate-700" />
                  </div>
                  <div className="space-y-2 mb-4">
                    <div className="h-4 w-full rounded bg-slate-200 dark:bg-slate-700" />
                    <div className="h-4 w-5/6 rounded bg-slate-200 dark:bg-slate-700" />
                  </div>
                  <div className="h-7 w-full rounded-md bg-slate-200 dark:bg-slate-700 mb-4" />
                  <div className="pt-4 border-t border-cardBorder flex items-center justify-between">
                    <div className="h-4 w-20 rounded bg-slate-200 dark:bg-slate-700" />
                    <div className="h-8 w-24 rounded-lg bg-slate-200 dark:bg-slate-700" />
                  </div>
                </article>
              ))}

            {!isLoading &&
              filteredAgents.map((agent) => (
              <article key={agent.id} className="glass-panel relative p-5 flex flex-col transition-transform duration-300 hover:-translate-y-1 hover:shadow-2xl hover:border-primary/50 group">
                <header className="flex items-start justify-between mb-3">
                  <h3 className="m-0 text-lg font-bold text-slate-800 dark:text-slate-100 group-hover:text-primary transition-colors">{agent.card_name}</h3>
                  <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full ${agent.mode === 'public' ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300' : 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300'}`}>{agent.mode}</span>
                </header>
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-4 line-clamp-2 flex-grow">{agent.card_description}</p>
                <small className="block text-xs text-slate-500 dark:text-slate-500 mb-4 truncate font-mono bg-slate-100 dark:bg-slate-800/50 p-1.5 rounded-md">{agent.base_url}</small>
                <div className="pointer-events-none absolute z-20 left-4 right-4 top-20 opacity-0 scale-95 translate-y-1 transition-all duration-200 group-hover:opacity-100 group-hover:scale-100 group-hover:translate-y-0">
                  <div className="rounded-xl border border-cardBorder bg-white/95 dark:bg-slate-900/95 p-3 shadow-2xl backdrop-blur-md">
                    <p className="m-0 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Skills</p>
                    <p className="m-0 mt-1 text-xs text-slate-700 dark:text-slate-300">
                      {agent.skills?.length
                        ? agent.skills.map((s) => s.name || s.id || 'Unnamed').join(', ')
                        : 'No skills'}
                    </p>
                    <p className="m-0 mt-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Tags</p>
                    <p className="m-0 mt-1 text-xs text-slate-700 dark:text-slate-300">
                      {agent.skills?.flatMap((s) => s.tags || []).length
                        ? [...new Set(agent.skills.flatMap((s) => s.tags || []))].join(', ')
                        : 'No tags'}
                    </p>
                  </div>
                </div>
                <footer className="flex items-center justify-between pt-4 border-t border-cardBorder mt-auto">
                  <span className="text-sm font-medium text-slate-500 dark:text-slate-400">{agent.skills?.length || 0} skills</span>
                  <button className="btn-primary py-1.5 px-4 text-sm" onClick={() => navigate(`/agents/${agent.id}`)}>
                    Interact
                  </button>
                </footer>
              </article>
            ))}
            {!isLoading && !error && !agents.length && (
              <div className="col-span-full py-16 text-center border-2 border-dashed border-cardBorder rounded-2xl bg-card/30">
                <p className="text-lg text-slate-500 dark:text-slate-400 font-medium">No agents found. Start by creating one.</p>
              </div>
            )}
            {!isLoading && !error && !!agents.length && !filteredAgents.length && (
              <div className="col-span-full py-16 text-center border-2 border-dashed border-cardBorder rounded-2xl bg-card/30">
                <p className="text-lg text-slate-500 dark:text-slate-400 font-medium">No matching agents for your search.</p>
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
