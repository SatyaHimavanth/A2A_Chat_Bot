import { useMemo, useState, useEffect } from 'react'

import AppHeader from '../components/AppHeader'
import { apiRequest } from '../lib/api'

export default function PlaygroundPage({ token, username, onLogout, theme, toggleTheme }) {
  const [agents, setAgents] = useState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [activeAgentId, setActiveAgentId] = useState(null)
  const [broadcastMode, setBroadcastMode] = useState(true)
  const [prompt, setPrompt] = useState('')
  const [results, setResults] = useState([])
  const [contexts, setContexts] = useState({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadAgents()
  }, [])

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

  function toggleSelect(agentId) {
    setSelectedIds((prev) => {
      if (prev.includes(agentId)) {
        const next = prev.filter((id) => id !== agentId)
        if (activeAgentId === agentId) {
          setActiveAgentId(next[0] || null)
        }
        return next
      }
      const next = [...prev, agentId]
      if (!activeAgentId) setActiveAgentId(agentId)
      return next
    })
  }

  const selectedAgents = useMemo(
    () => agents.filter((a) => selectedIds.includes(a.id)),
    [agents, selectedIds],
  )

  const comparable = useMemo(() => {
    return [...results].sort((a, b) => a.latency_ms - b.latency_ms)
  }, [results])

  async function runCompare(e) {
    e.preventDefault()
    setError('')
    const message = prompt.trim()
    if (!message) {
      setError('Enter a prompt.')
      return
    }

    const targetIds = broadcastMode
      ? selectedIds
      : activeAgentId
        ? [activeAgentId]
        : []

    if (!targetIds.length) {
      setError('Select at least 1 agent to start chatting.')
      return
    }

    setLoading(true)
    try {
      const context_ids = {}
      targetIds.forEach((id) => {
        if (contexts[id]) context_ids[id] = contexts[id]
      })

      const data = await apiRequest('/api/playground/compare', {
        method: 'POST',
        token,
        body: {
          agent_ids: targetIds,
          message,
          context_ids,
        },
        onUnauthorized: onLogout,
      })

      const nextResults = data.results || []
      setResults(nextResults)
      const nextContexts = { ...contexts }
      nextResults.forEach((r) => {
        if (r.context_id) {
          nextContexts[r.agent_id] = r.context_id
        }
      })
      setContexts(nextContexts)
      setPrompt('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fastestId = comparable[0]?.agent_id

  return (
    <main className="ambient-bg p-4 md:p-6 lg:p-8 animate-fade-in text-foreground">
      <div className="max-w-6xl mx-auto">
        <AppHeader
          title="Agents Playground"
          subtitle="Compare responses across agents with latency and quality hints"
          onLogout={onLogout}
          username={username}
          theme={theme}
          toggleTheme={toggleTheme}
        />

        {error && <div className="bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-xl mb-6">{error}</div>}

        <section className="glass-panel p-5 mb-6">
          <div className="flex items-center justify-between gap-4 mb-4">
            <h2 className="m-0 text-lg font-semibold text-slate-800 dark:text-slate-100">Select Agents</h2>
            <label className="inline-flex items-center gap-3 cursor-pointer select-none">
              <span className="text-sm font-medium text-slate-600 dark:text-slate-300">Broadcast to all selected</span>
              <span className="relative inline-flex items-center">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={broadcastMode}
                  onChange={(e) => setBroadcastMode(e.target.checked)}
                />
                <span className={`w-12 h-7 rounded-full transition-colors ${broadcastMode ? 'bg-primary' : 'bg-slate-300 dark:bg-slate-700'}`}>
                  <span className={`block w-5 h-5 rounded-full bg-white mt-1 transition-transform ${broadcastMode ? 'translate-x-6' : 'translate-x-1'}`}></span>
                </span>
              </span>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {agents.map((agent) => {
              const checked = selectedIds.includes(agent.id)
              const isActive = activeAgentId === agent.id
              return (
                <label key={agent.id} className={`border rounded-xl p-3 cursor-pointer transition-all ${checked ? 'border-primary bg-primary/5' : 'border-cardBorder'}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <input type="checkbox" checked={checked} onChange={() => toggleSelect(agent.id)} />
                      <strong className="text-sm text-slate-800 dark:text-slate-100">{agent.card_name}</strong>
                    </div>
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full ${agent.mode === 'public' ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300' : 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300'}`}>{agent.mode}</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-2 mb-0 truncate">{agent.base_url}</p>
                  {!broadcastMode && checked && (
                    <button
                      type="button"
                      className={`mt-2 text-xs px-2 py-1 rounded-lg border ${isActive ? 'border-primary text-primary' : 'border-cardBorder text-slate-500'}`}
                      onClick={(e) => {
                        e.preventDefault()
                        setActiveAgentId(agent.id)
                      }}
                    >
                      {isActive ? 'Active Agent' : 'Set Active'}
                    </button>
                  )}
                </label>
              )
            })}
          </div>
        </section>

        <section className="glass-panel p-5 mb-6">
          <form onSubmit={runCompare} className="flex flex-col gap-3">
            <textarea
              className="input-base min-h-[96px]"
              placeholder="Ask the same question to selected agents..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <div className="flex items-center justify-between">
              <small className="text-slate-500">Selected: {selectedIds.length}</small>
              <button className="btn-primary" type="submit" disabled={loading || !selectedIds.length}>
                {loading ? 'Running...' : broadcastMode ? 'Compare All' : 'Send to Active'}
              </button>
            </div>
          </form>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {comparable.map((result, idx) => (
            <article key={`${result.agent_id}-${idx}`} className="glass-panel p-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <strong className="text-slate-800 dark:text-slate-100">{result.card_name}</strong>
                  <p className="m-0 text-xs text-slate-500">{result.mode} • {result.latency_ms} ms</p>
                </div>
                <div className="flex items-center gap-2">
                  {fastestId === result.agent_id && (
                    <span className="text-[10px] font-bold uppercase px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">Fastest</span>
                  )}
                  <span className={`text-[10px] font-bold uppercase px-2 py-1 rounded-full ${result.status === 'ok' ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300' : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'}`}>
                    {result.status}
                  </span>
                </div>
              </div>
              {result.error ? (
                <p className="text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap">{result.error}</p>
              ) : (
                <p className="text-sm text-slate-700 dark:text-slate-200 whitespace-pre-wrap">{result.response || '(No text response)'}</p>
              )}
            </article>
          ))}
          {!comparable.length && (
            <div className="col-span-full py-12 text-center border-2 border-dashed border-cardBorder rounded-2xl bg-card/30 text-slate-500">
              Run a prompt to compare selected agents.
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
