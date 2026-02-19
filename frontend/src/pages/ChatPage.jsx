import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import AppHeader from '../components/AppHeader'
import { apiRequest, createSseUrl } from '../lib/api'

export default function ChatPage({ token, username, onLogout }) {
  const { agentId } = useParams()
  const [agentDetail, setAgentDetail] = useState(null)
  const [agentStatus, setAgentStatus] = useState('connected')
  const [sessions, setSessions] = useState([])
  const [selectedSession, setSelectedSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  async function loadSessions() {
    setError('')
    try {
      const data = await apiRequest(`/api/agents/${agentId}/sessions`, {
        token,
        onUnauthorized: onLogout,
      })
      setSessions(data)
      if (data.length > 0 && !selectedSession) {
        await selectSession(data[0])
      }
    } catch (err) {
      setError(err.message)
    }
  }

  async function loadAgentDetail() {
    setError('')
    try {
      const data = await apiRequest(`/api/agents/${agentId}`, {
        token,
        onUnauthorized: onLogout,
      })
      setAgentDetail(data)
      const selectedMode = data.modes?.find((m) => m.id === Number(agentId))
      setAgentStatus(selectedMode?.status || 'connected')
    } catch (err) {
      setError(err.message)
    }
  }

  async function refreshStatus() {
    setError('')
    try {
      const data = await apiRequest(`/api/agents/${agentId}/refresh-status`, {
        method: 'POST',
        token,
        onUnauthorized: onLogout,
      })
      const nextStatus = data.status || 'connected'
      setAgentStatus(nextStatus)
      await loadAgentDetail()
      return nextStatus
    } catch (err) {
      setError(err.message)
      return 'disconnected'
    }
  }

  useEffect(() => {
    setSelectedSession(null)
    setMessages([])
    loadAgentDetail()
    loadSessions()
  }, [agentId])

  useEffect(() => {
    const timer = setInterval(() => {
      refreshStatus()
    }, 15000)
    return () => clearInterval(timer)
  }, [agentId, token])

  async function createSession() {
    const statusNow = await refreshStatus()
    if (statusNow !== 'connected') {
      throw new Error('Agent cannot be connected right now.')
    }
    const data = await apiRequest(`/api/agents/${agentId}/sessions`, {
      method: 'POST',
      token,
      body: { title: 'New chat' },
      onUnauthorized: onLogout,
    })
    setSessions((prev) => [data, ...prev])
    setSelectedSession(data)
    setMessages([])
    return data
  }

  async function selectSession(session) {
    setSelectedSession(session)
    try {
      const data = await apiRequest(`/api/sessions/${session.id}/messages`, {
        token,
        onUnauthorized: onLogout,
      })
      setMessages(data)
    } catch (err) {
      setError(err.message)
    }
  }

  async function sendMessage(e) {
    e.preventDefault()
    if (!chatInput.trim() || isLoading) {
      return
    }

    setIsLoading(true)
    setError('')
    const statusNow = await refreshStatus()
    if (statusNow !== 'connected') {
      setError('Agent cannot be connected right now.')
      setIsLoading(false)
      return
    }
    const messageText = chatInput.trim()
    setChatInput('')

    let session = selectedSession
    try {
      if (!session) {
        session = await createSession()
      }
    } catch (err) {
      setError(err.message)
      setIsLoading(false)
      return
    }

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: messageText,
      created_at: new Date().toISOString(),
    }
    const assistantPlaceholder = {
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      streaming: true,
    }
    setMessages((prev) => [...prev, userMessage, assistantPlaceholder])

    try {
      const res = await fetch(createSseUrl(`/api/sessions/${session.id}/stream`), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: messageText }),
      })
      if (res.status === 401) {
        onLogout()
        throw new Error('Session expired. Please login again.')
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Agent cannot be connected right now.')
      }

      const reader = res.body?.getReader()
      if (!reader) {
        throw new Error('Agent cannot be connected right now.')
      }
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split('\n\n')
        buffer = chunks.pop() || ''

        for (const chunk of chunks) {
          const line = chunk
            .split('\n')
            .find((row) => row.startsWith('data: '))
          if (!line) continue
          const payload = JSON.parse(line.slice(6))
          if (payload.type === 'assistant_snapshot') {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.streaming ? { ...msg, content: payload.text } : msg,
              ),
            )
          }
          if (payload.type === 'error') {
            setError(payload.message)
          }
        }
      }

      setMessages((prev) =>
        prev.map((msg) => (msg.streaming ? { ...msg, streaming: false } : msg)),
      )
      await loadSessions()
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="app-shell">
      <AppHeader
        title="Agent Chat"
        subtitle={`${agentDetail?.card_name || 'Agent'} | Signed in as ${username}`}
        onLogout={onLogout}
      />
      {error && <div className="error">{error}</div>}
      <section className="chat-page-layout">
        <aside className="column sessions">
          <div className="sessions-header">
            <h2>Sessions</h2>
            <button onClick={createSession} disabled={agentStatus !== 'connected'}>
              New
            </button>
          </div>
          <div className="session-list">
            {sessions.map((session) => (
              <button
                key={session.id}
                className={selectedSession?.id === session.id ? 'session active' : 'session'}
                onClick={() => selectSession(session)}
              >
                <strong>{session.title || 'Untitled'}</strong>
                <small>{session.context_id}</small>
              </button>
            ))}
            {!sessions.length && <p>No sessions yet.</p>}
          </div>
        </aside>
        <section className="column chat">
          <div className="chat-title-row">
            <h2>Conversation</h2>
            <div className="status-row">
              <span className={`status-pill ${agentStatus || 'connected'}`}>
                {agentStatus || 'connected'}
              </span>
              <button type="button" className="ghost" onClick={refreshStatus}>
                Refresh
              </button>
            </div>
          </div>
          {selectedSession && (
            <p className="session-id">Session ID: {selectedSession.context_id}</p>
          )}
          {agentStatus !== 'connected' && (
            <p className="status-warning">
              Agent cannot be connected right now. Refresh status to retry.
            </p>
          )}
          <div className="messages">
            {messages.map((msg) => (
              <div key={msg.id} className={`msg ${msg.role}`}>
                <strong>{msg.role === 'user' ? 'You' : 'Agent'}</strong>
                <p>{msg.content || (msg.streaming ? 'Typing...' : '')}</p>
              </div>
            ))}
            {!messages.length && <p className="empty">Start a conversation.</p>}
          </div>
          <form className="composer" onSubmit={sendMessage}>
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Send a message..."
              disabled={isLoading || agentStatus !== 'connected'}
            />
            <button type="submit" disabled={isLoading || agentStatus !== 'connected'}>
              {isLoading ? 'Sending...' : 'Send'}
            </button>
          </form>
        </section>
      </section>
    </main>
  )
}
