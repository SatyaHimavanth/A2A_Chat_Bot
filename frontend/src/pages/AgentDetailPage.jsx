import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import AppHeader from '../components/AppHeader'
import { apiRequest } from '../lib/api'

export default function AgentDetailPage({ token, username, onLogout }) {
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
    const timer = setInterval(() => {
      loadDetail()
    }, 15000)
    return () => clearInterval(timer)
  }, [agentId, token])

  const selectedMode = useMemo(
    () => detail?.modes?.find((m) => m.id === selectedModeId) || null,
    [detail, selectedModeId],
  )

  return (
    <main className="app-shell">
      <AppHeader
        title="Agent Details"
        subtitle={`Signed in as ${username} | Auto-refresh status every 15s`}
        rightActionLabel="Chat"
        onRightAction={() => selectedModeId && navigate(`/agents/${selectedModeId}/chat`)}
        onLogout={onLogout}
      />
      {error && <div className="error">{error}</div>}
      {detail && (
        <section className="detail-layout">
          <article className="column">
            <h2>{detail.card_name}</h2>
            <p>{detail.card_description}</p>
            <small>{detail.base_url}</small>
            <h3>Available Modes</h3>
            <div className="mode-cards">
              {detail.modes.map((mode) => (
                <button
                  key={mode.id}
                  className={selectedModeId === mode.id ? 'session active' : 'session'}
                  onClick={() => setSelectedModeId(mode.id)}
                >
                  <strong>{mode.mode}</strong>
                  <small>ID: {mode.id}</small>
                  <small>Status: {mode.status || 'connected'}</small>
                </button>
              ))}
            </div>
          </article>
          <article className="column">
            <h2>Card Payload</h2>
            {selectedMode && (
              <div className="status-row">
                <span className={`status-pill ${selectedMode.status || 'connected'}`}>
                  {selectedMode.status || 'connected'}
                </span>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => refreshStatus(selectedMode.id)}
                >
                  Refresh
                </button>
              </div>
            )}
            {selectedMode ? (
              <pre className="payload-view">
                {JSON.stringify(selectedMode.card_payload, null, 2)}
              </pre>
            ) : (
              <p>Select a mode to inspect its card.</p>
            )}
          </article>
        </section>
      )}
    </main>
  )
}
