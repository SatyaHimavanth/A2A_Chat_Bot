import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import AppHeader from '../components/AppHeader'
import ConnectAgentModal from '../components/ConnectAgentModal'
import { apiRequest } from '../lib/api'

export default function AgentsPage({ token, username, onLogout }) {
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
    <main className="app-shell">
      <AppHeader
        title="A2A Agent Cards"
        subtitle={`Signed in as ${username}`}
        rightActionLabel="Create"
        onRightAction={() => setShowConnect(true)}
        onLogout={onLogout}
        showAgentsNav={false}
      />
      {error && <div className="error">{error}</div>}
      <section className="agents-only-layout">
        <div className="card-grid">
          {agents.map((agent) => (
            <article key={agent.id} className="agent-card">
              <header>
                <h3>{agent.card_name}</h3>
                <span className={`mode ${agent.mode}`}>{agent.mode}</span>
              </header>
              <p>{agent.card_description}</p>
              <small>{agent.base_url}</small>
              <footer>
                <span>{agent.skills?.length || 0} skills</span>
                <button onClick={() => navigate(`/agents/${agent.id}`)}>
                  View
                </button>
              </footer>
            </article>
          ))}
          {!agents.length && <p>No connected agents yet.</p>}
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
    </main>
  )
}
