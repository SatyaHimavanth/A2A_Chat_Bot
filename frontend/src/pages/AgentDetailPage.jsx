import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import AppHeader from '../components/AppHeader'
import { apiRequest } from '../lib/api'

export default function AgentDetailPage({ token, username, onLogout, theme, toggleTheme }) {
  const { agentId } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [selectedModeId, setSelectedModeId] = useState(null)
  const [error, setError] = useState('')

  async function loadDetail() {
    setError('')
    try {
      const data = await apiRequest(`/api/agents/${agentId}`, {
        token,
        onUnauthorized: onLogout,
      })
      setDetail(data)
      if (!selectedModeId) {
        const defaultMode = data.modes.find((m) => m.id === Number(agentId)) || data.modes[0]
        setSelectedModeId(defaultMode?.id ?? null)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  async function refreshStatus(modeId) {
    setError('')
    try {
      await apiRequest(`/api/agents/${modeId}/refresh-status`, {
        method: 'POST',
        token,
        onUnauthorized: onLogout,
      })
      await loadDetail()
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    loadDetail()
  }, [agentId])

  useEffect(() => {
    const intervalSecs = 60
    const timer = setInterval(() => {
      loadDetail()
    }, intervalSecs * 1000)
    return () => clearInterval(timer)
  }, [agentId, token])

  const selectedMode = useMemo(
    () => detail?.modes?.find((m) => m.id === selectedModeId) || null,
    [detail, selectedModeId],
  )

  return (
    <main className="ambient-bg p-4 md:p-6 lg:p-8 animate-fade-in text-foreground">
      <div className="max-w-6xl mx-auto">
        <AppHeader
          title="Agent Details"
          subtitle="Auto-refresh status every 60 seconds"
          rightActionLabel="Chat with Agent"
          onRightAction={() => selectedModeId && navigate(`/agents/${selectedModeId}/chat`)}
          onLogout={onLogout}
          username={username}
          theme={theme}
          toggleTheme={toggleTheme}
        />
        {error && <div className="bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-xl mb-6">{error}</div>}

        {detail && (
          <section className="grid grid-cols-1 lg:grid-cols-5 gap-6 mt-8 animate-slide-up">
            <article className="glass-panel p-6 lg:col-span-2 flex flex-col gap-5">
              <div>
                <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">{detail.card_name}</h2>
                <small className="inline-block mt-2 font-mono text-xs text-slate-500 bg-slate-100 dark:bg-slate-800/50 p-1.5 rounded-md truncate max-w-full">{detail.base_url}</small>
              </div>
              <p className="text-slate-600 dark:text-slate-400 flex-grow">{detail.card_description}</p>

              <div className="mt-4 pt-4 border-t border-cardBorder">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">Available Modes</h3>
                <div className="flex flex-col gap-2">
                  {detail.modes.map((mode) => (
                    <button
                      key={mode.id}
                      className={`text-left p-3 rounded-xl border transition-all ${selectedModeId === mode.id ? 'border-primary bg-primary/5 shadow-md shadow-primary/10' : 'border-cardBorder bg-card/50 hover:bg-slate-50 dark:hover:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-600'}`}
                      onClick={() => setSelectedModeId(mode.id)}
                    >
                      <div className="flex justify-between items-center mb-1">
                        <strong className="text-sm text-slate-800 dark:text-slate-200">{mode.mode}</strong>
                        <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${mode.status === 'connected' ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300' : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'}`}>
                          {mode.status || 'connected'}
                        </span>
                      </div>
                      <small className="text-xs text-slate-500 block">Connection ID: {mode.id}</small>
                    </button>
                  ))}
                </div>
              </div>
            </article>

            <article className="glass-panel p-6 lg:col-span-3 flex flex-col">
              <div className="flex items-center justify-between mb-4 pb-4 border-b border-cardBorder">
                <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">Card Payload</h2>
                {selectedMode && (
                  <button
                    type="button"
                    className="btn-ghost py-1.5 text-sm flex items-center gap-2"
                    onClick={() => refreshStatus(selectedMode.id)}
                  >
                    <span>Refresh Data</span>
                  </button>
                )}
              </div>

              {selectedMode ? (
                <div className="flex-grow bg-slate-50 dark:bg-slate-900/50 block rounded-xl border border-cardBorder p-4 overflow-auto max-h-[60vh] max-w-full">
                  <pre className="text-xs font-mono text-slate-700 dark:text-slate-300">
                    {JSON.stringify(selectedMode.card_payload, null, 2)}
                  </pre>
                </div>
              ) : (
                <div className="flex-grow flex items-center justify-center border-2 border-dashed border-cardBorder rounded-xl bg-card/30 min-h-[300px]">
                  <p className="text-slate-500 dark:text-slate-400 font-medium">Select a mode to inspect its card payload.</p>
                </div>
              )}
            </article>
          </section>
        )}
      </div>
    </main>
  )
}
