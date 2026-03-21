import { useEffect, useState, useRef } from 'react'
import { useParams } from 'react-router-dom'

import AppHeader from '../components/AppHeader'
import FlashMessages from '../components/FlashMessages'
import MarkdownMessage from '../components/MarkdownMessage'
import SpeechToTextControl from '../components/SpeechToTextControl'
import { apiRequest, createSseUrl } from '../lib/api'

const CHAT_STREAM_TIMEOUT_MS = Number(import.meta.env.VITE_CHAT_STREAM_TIMEOUT_MS || 240000)

export default function ChatPage({ token, username, onLogout, theme, toggleTheme }) {
  const { agentId } = useParams()
  const [agentDetail, setAgentDetail] = useState(null)
  const [agentStatus, setAgentStatus] = useState('connected')
  const [sessions, setSessions] = useState([])
  const [sessionSearch, setSessionSearch] = useState('')
  const [selectedSession, setSelectedSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [flashMessages, setFlashMessages] = useState([])

  const [sessionToRename, setSessionToRename] = useState(null)
  const [renameInputValue, setRenameInputValue] = useState('')
  const [sessionToDelete, setSessionToDelete] = useState(null)
  const [showArchived, setShowArchived] = useState(false)

  const messagesEndRef = useRef(null)
  const hasSearchEffectInitialized = useRef(false)

  const activeSessions = sessions.filter((s) => (s.chat_status ?? 1) === 1)
  const archivedSessions = sessions.filter((s) => (s.chat_status ?? 1) === -1)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  function showFlash(text, type = 'error') {
    const id = `${Date.now()}-${Math.random()}`
    setFlashMessages((prev) => [...prev, { id, text, type }])
    setTimeout(() => {
      setFlashMessages((prev) => prev.filter((item) => item.id !== id))
    }, 5000)
  }

  function dismissFlash(id) {
    setFlashMessages((prev) => prev.filter((item) => item.id !== id))
  }

  function reportError(message) {
    setError(message)
    showFlash(message, 'error')
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  async function loadSessions() {
    setError('')
    try {
      const query = sessionSearch.trim()
      const suffix = query ? `?search=${encodeURIComponent(query)}` : ''
      const data = await apiRequest(`/api/agents/${agentId}/sessions${suffix}`, {
        token,
        onUnauthorized: onLogout,
      })
      setSessions(data)
      if (data.length > 0 && !selectedSession) {
        await selectSession(data[0])
      }
    } catch (err) {
      reportError(err.message)
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
      reportError(err.message)
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
      reportError(err.message)
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
    if (!hasSearchEffectInitialized.current) {
      hasSearchEffectInitialized.current = true
      return
    }
    const timer = setTimeout(() => {
      loadSessions()
    }, 250)
    return () => clearTimeout(timer)
  }, [sessionSearch])

  useEffect(() => {
    const intervalSecs = 60
    const timer = setInterval(() => {
      refreshStatus()
    }, intervalSecs * 1000)
    return () => clearInterval(timer)
  }, [agentId, token])

  async function createSession() {
    const topActiveSession = activeSessions[0]
    if (topActiveSession && typeof topActiveSession.id === 'number') {
      try {
        const topMessages = await apiRequest(`/api/sessions/${topActiveSession.id}/messages`, {
          token,
          onUnauthorized: onLogout,
        })
        if (topMessages.length === 0) {
          setSelectedSession(topActiveSession)
          setMessages(topMessages)
          return topActiveSession
        }
      } catch (err) {
        reportError(err.message)
      }
    }

    const statusNow = await refreshStatus()
    if (statusNow !== 'connected') {
      throw new Error('Agent cannot be connected right now.')
    }

    const tempId = `temp-${Date.now()}`
    const tempSession = {
      id: tempId,
      context_id: 'creating...',
      title: 'New chat',
      summary: null,
      tags: [],
      chat_status: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      _temp: true,
    }
    setSessions((prev) => [tempSession, ...prev])
    setSelectedSession(tempSession)
    setMessages([])

    try {
      const data = await apiRequest(`/api/agents/${agentId}/sessions`, {
        method: 'POST',
        token,
        body: { title: 'New chat' },
        onUnauthorized: onLogout,
      })
      setSessions((prev) => prev.map((s) => (s.id === tempId ? data : s)))
      setSelectedSession(data)
      return data
    } catch (err) {
      setSessions((prev) => prev.filter((s) => s.id !== tempId))
      if (selectedSession?.id === tempId) {
        setSelectedSession(null)
      }
      throw err
    }
  }

  async function selectSession(session) {
    if (session?._temp) {
      return
    }
    setSelectedSession(session)
    try {
      const data = await apiRequest(`/api/sessions/${session.id}/messages`, {
        token,
        onUnauthorized: onLogout,
      })
      setMessages(data)
    } catch (err) {
      reportError(err.message)
    }
  }

  function openRenameModal(e, session) {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    setSessionToRename(session)
    setRenameInputValue(session.title || '')
  }

  async function submitRenameSession(e) {
    if (e) e.preventDefault()
    if (!sessionToRename || !renameInputValue.trim()) {
      setSessionToRename(null)
      return
    }
    try {
      await apiRequest(`/api/sessions/${sessionToRename.id}/rename`, {
        method: 'PATCH',
        token,
        body: { title: renameInputValue.trim() },
        onUnauthorized: onLogout,
      })
      await loadSessions()
    } catch (err) {
      reportError(err.message)
    } finally {
      setSessionToRename(null)
      setRenameInputValue('')
    }
  }

  function closeRenameModal() {
    setSessionToRename(null)
    setRenameInputValue('')
  }

  async function archiveSession(e, session) {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    try {
      await apiRequest(`/api/sessions/${session.id}/archive`, {
        method: 'POST',
        token,
        onUnauthorized: onLogout,
      })
      if (selectedSession?.id === session.id) {
        setSelectedSession(null)
        setMessages([])
      }
      await loadSessions()
    } catch (err) {
      reportError(err.message)
    }
  }

  async function unarchiveSession(e, session) {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    try {
      await apiRequest(`/api/sessions/${session.id}/unarchive`, {
        method: 'POST',
        token,
        onUnauthorized: onLogout,
      })
      await loadSessions()
    } catch (err) {
      reportError(err.message)
    }
  }

  function openDeleteModal(e, session) {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    setSessionToDelete(session)
  }

  async function submitDeleteSession() {
    if (!sessionToDelete) return
    try {
      await apiRequest(`/api/sessions/${sessionToDelete.id}/delete`, {
        method: 'POST',
        token,
        onUnauthorized: onLogout,
      })
      if (selectedSession?.id === sessionToDelete.id) {
        setSelectedSession(null)
        setMessages([])
      }
      await loadSessions()
    } catch (err) {
      reportError(err.message)
    } finally {
      setSessionToDelete(null)
    }
  }

  function closeDeleteModal() {
    setSessionToDelete(null)
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
      reportError('Agent cannot be connected right now.')
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
      reportError(err.message)
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

    let timeoutId
    try {
      const controller = new AbortController()
      timeoutId = setTimeout(() => controller.abort('stream-timeout'), CHAT_STREAM_TIMEOUT_MS)
      const res = await fetch(createSseUrl(`/api/sessions/${session.id}/stream`), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: messageText }),
        signal: controller.signal,
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
      let latestAssistantText = ''
      let hadStreamError = false
      const processPayload = (payload) => {
        if (payload.type === 'assistant_snapshot') {
          latestAssistantText = typeof payload.text === 'string' ? payload.text : ''
          setMessages((prev) =>
            prev.map((msg) =>
              msg.streaming ? { ...msg, content: payload.text } : msg,
            ),
          )
        }
        if (payload.type === 'error') {
          hadStreamError = true
          reportError(payload.message || 'Agent stream failed.')
        }
      }

      const processChunk = (chunk) => {
        const dataLines = chunk
          .split(/\r?\n/)
          .filter((row) => row.startsWith('data:'))
          .map((row) => row.slice(5).trimStart())
          .filter(Boolean)
        if (!dataLines.length) return
        for (const rawData of dataLines) {
          let payload
          try {
            payload = JSON.parse(rawData)
          } catch {
            continue
          }
          processPayload(payload)
        }
      }
      while (true) {
        const { value, done } = await reader.read()
        if (done) {
          buffer += decoder.decode()
          break
        }
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split(/\r?\n\r?\n/)
        buffer = chunks.pop() || ''

        for (const chunk of chunks) {
          processChunk(chunk)
        }
      }

      if (buffer.trim()) {
        processChunk(buffer)
      }

      setMessages((prev) =>
        prev.map((msg) => (msg.streaming ? { ...msg, streaming: false } : msg)),
      )
      await loadSessions()
      if (!hadStreamError && !latestAssistantText.trim()) {
        try {
          const persisted = await apiRequest(`/api/sessions/${session.id}/messages`, {
            token,
            onUnauthorized: onLogout,
          })
          if (Array.isArray(persisted) && persisted.length) {
            setMessages(persisted)
            const hasAssistant = persisted.some(
              (m) => m.role === 'assistant' && String(m.content || '').trim(),
            )
            if (hasAssistant) {
              return
            }
          }
        } catch {
          // keep fallback error below
        }
        reportError('No response received from agent. Please try again.')
      }
    } catch (err) {
      if (err?.name === 'AbortError') {
        reportError('Agent response timed out. Please try again.')
      } else {
        reportError(err.message)
      }
    } finally {
      if (timeoutId) clearTimeout(timeoutId)
      setIsLoading(false)
    }
  }

  return (
    <main className="ambient-bg flex flex-col h-screen overflow-hidden text-foreground">
      <FlashMessages messages={flashMessages} onDismiss={dismissFlash} />
      <div className="px-4 md:px-6 lg:px-8 shrink-0">
        <AppHeader
          title="Workspace"
          subtitle={agentDetail?.card_name || 'Agent Console'}
          onLogout={onLogout}
          username={username}
          theme={theme}
          toggleTheme={toggleTheme}
        />
        {error && <div className="bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-2 rounded-xl text-sm mb-4 animate-slide-up shadow-lg max-w-6xl mx-auto">{error}</div>}
      </div>

      <section className="flex-1 flex flex-col lg:flex-row gap-6 px-4 md:px-6 lg:px-8 pb-6 min-h-0 max-w-[1400px] w-full mx-auto">

        {/* Sidebar Sessions */}
        <aside className="glass-panel w-full lg:w-[320px] shrink-0 flex flex-col max-h-[30vh] lg:max-h-full overflow-hidden">
          <div className="p-4 border-b border-cardBorder flex justify-between items-center shrink-0">
            <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100 m-0">
              {showArchived ? 'Archived Chats' : 'Conversations'}
            </h2>
            <div className="flex items-center gap-2">
              <button
                className="text-[10px] uppercase font-bold tracking-wider text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
                onClick={() => setShowArchived(!showArchived)}
              >
                {showArchived ? 'Active' : 'Archived'}
              </button>
              {!showArchived && (
                <button className="btn-primary text-xs py-1.5 px-3" onClick={createSession} disabled={agentStatus !== 'connected'}>
                  + New
                </button>
              )}
            </div>
          </div>
          <div className="p-3 border-b border-cardBorder shrink-0">
            <input
              type="text"
              className="input-base py-2 text-xs"
              placeholder="Search sessions by title, summary, tags..."
              value={sessionSearch}
              onChange={(e) => setSessionSearch(e.target.value)}
            />
          </div>

          <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
            {!showArchived ? (
              <>
                {activeSessions.map((session) => (
                  <div
                    key={session.id}
                    className={`flex flex-col rounded-xl overflow-hidden transition-all border ${selectedSession?.id === session.id ? 'border-primary bg-primary/5 shadow-md shadow-primary/10' : 'border-cardBorder bg-card/50 hover:bg-slate-50 dark:hover:bg-slate-800/80 hover:border-slate-300 dark:hover:border-slate-600'}`}
                  >
                    <button className="text-left w-full p-3 bg-transparent outline-none focus:outline-none" onClick={() => selectSession(session)}>
                      <strong className="text-sm font-semibold text-slate-800 dark:text-slate-200 block truncate">{session.title || 'Untitled'}</strong>
                      {session.summary && <small className="text-xs text-slate-500 block truncate mt-1">{session.summary}</small>}
                      <small className="text-xs text-slate-500 font-mono block truncate mt-1">{session.context_id}</small>
                      {!!session.tags?.length && (
                        <small className="text-[11px] text-slate-500 block truncate mt-1">
                          #{session.tags.join(' #')}
                        </small>
                      )}
                    </button>
                    <div className="flex gap-2 p-2 bg-slate-100/50 dark:bg-slate-900/50 border-t border-cardBorder">
                      <button className="text-[11px] font-medium text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200" onClick={(e) => openRenameModal(e, session)}>Rename</button>
                      <button className="text-[11px] font-medium text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200" onClick={(e) => archiveSession(e, session)}>Archive</button>
                      <button className="text-[11px] font-medium text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 ml-auto" onClick={(e) => openDeleteModal(e, session)}>Delete</button>
                    </div>
                  </div>
                ))}
                {!activeSessions.length && <p className="text-center text-sm text-slate-500 py-6">No active sessions.</p>}
              </>
            ) : (
              <>
                {archivedSessions.map((session) => (
                  <div
                    key={session.id}
                    className={`flex flex-col rounded-xl overflow-hidden transition-all border opacity-75 hover:opacity-100 ${selectedSession?.id === session.id ? 'border-primary bg-primary/5 shadow-md shadow-primary/10' : 'border-cardBorder bg-card/50 hover:bg-slate-50 dark:hover:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-600'}`}
                  >
                    <button className="text-left w-full p-3 bg-transparent outline-none" onClick={() => selectSession(session)}>
                      <strong className="text-sm font-semibold text-slate-800 dark:text-slate-200 block truncate line-through decoration-slate-400/50">{session.title || 'Untitled'}</strong>
                    </button>
                    <div className="flex gap-2 p-2 bg-slate-100/50 dark:bg-slate-900/50 border-t border-cardBorder">
                      <button className="text-[11px] font-medium text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200" onClick={(e) => unarchiveSession(e, session)}>Restore</button>
                      <button className="text-[11px] font-medium text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 ml-auto" onClick={(e) => openDeleteModal(e, session)}>Delete</button>
                    </div>
                  </div>
                ))}
                {!archivedSessions.length && <p className="text-center text-sm text-slate-500 py-6">No archived sessions.</p>}
              </>
            )}
          </div>
        </aside>

        {/* Chat Area */}
        <section className="glass-panel flex-1 flex flex-col min-h-0 min-w-0">
          <div className="flex items-center justify-between p-4 border-b border-cardBorder shrink-0">
            <div>
              <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100 m-0">{selectedSession ? selectedSession.title : 'Conversation'}</h2>
              {selectedSession && <p className="text-xs font-mono text-slate-500 m-0 mt-0.5">{selectedSession.context_id}</p>}
            </div>

            <div className="flex items-center gap-3">
              <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 flex items-center gap-1.5 rounded-full ${agentStatus === 'connected' ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300' : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${agentStatus === 'connected' ? 'bg-teal-500 animate-pulse' : 'bg-red-500'}`}></span>
                {agentStatus || 'connected'}
              </span>
              <button type="button" className="btn-ghost py-1 px-3 text-xs" onClick={refreshStatus}>
                ♻
              </button>
            </div>
          </div>

          {agentStatus !== 'connected' && (
            <div className="bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-900 p-2 text-center shrink-0">
              <p className="text-xs font-medium text-red-600 dark:text-red-400 m-0 animate-pulse">Connection suspended. Refresh status to reconnect.</p>
            </div>
          )}

          {/* Messages Wrapper */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6 flex flex-col gap-5 custom-scroll">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex max-w-[85%] animate-slide-up ${msg.role === 'user' ? 'self-end bg-userMsg border border-userMsgBorder rounded-t-2xl rounded-bl-2xl shadow-sm text-slate-800 dark:text-slate-100' : 'self-start bg-agentMsg border border-agentMsgBorder rounded-t-2xl rounded-br-2xl shadow-md text-slate-800 dark:text-slate-100'}`}>
                <div className="p-3.5 md:p-4">
                  <strong className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-1">
                    {msg.role === 'user' ? 'You' : (agentDetail?.card_name || 'Agent')}
                  </strong>
                  <div>
                    {msg.content ? (
                      <MarkdownMessage content={msg.content} />
                    ) : (
                      msg.streaming && <span className="flex gap-1 items-center py-1 mt-1 opacity-60">
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-500 dark:bg-slate-400 animate-bounce" style={{ animationDelay: "0ms" }}></span>
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-500 dark:bg-slate-400 animate-bounce" style={{ animationDelay: "150ms" }}></span>
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-500 dark:bg-slate-400 animate-bounce" style={{ animationDelay: "300ms" }}></span>
                    </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {!messages.length && (
              <div className="my-auto flex flex-col items-center justify-center space-y-4 opacity-50">
                <div className="w-16 h-16 rounded-3xl bg-primary/20 flex items-center justify-center animate-pulse-slow">
                  <div className="w-8 h-8 rounded-full bg-primary/40"></div>
                </div>
                <p className="font-medium text-slate-500">Initiate interaction timeline</p>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="p-4 bg-slate-50/50 dark:bg-slate-900/50 border-t border-cardBorder shrink-0 rounded-b-2xl">
            <form className="relative flex items-end gap-2 max-w-4xl mx-auto" onSubmit={sendMessage}>
              <div className="relative flex-1 bg-card rounded-2xl shadow-inner border border-cardBorder overflow-hidden group focus-within:border-primary focus-within:ring-1 focus-within:ring-primary transition-all">
                <textarea
                  className={`w-full bg-transparent border-0 resize-none max-h-[160px] min-h-[52px] p-3.5 outline-none text-[0.95rem] text-slate-800 dark:text-slate-200 ${selectedSession?.chat_status === -1 ? 'cursor-not-allowed opacity-60' : ''}`}
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder={selectedSession?.chat_status === -1 ? "Chat archived (Read-only)" : agentStatus === 'connected' ? "Type a message..." : "Agent disconnected"}
                  disabled={isLoading || agentStatus !== 'connected' || selectedSession?.chat_status === -1}
                  rows={1}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      sendMessage(e)
                    }
                  }}
                  onInput={(e) => {
                    e.target.style.height = 'auto';
                    e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';
                  }}
                />
              </div>
              <SpeechToTextControl
                token={token}
                disabled={isLoading || agentStatus !== 'connected' || selectedSession?.chat_status === -1}
                onTranscriptChange={(text) => setChatInput(text)}
                onError={reportError}
              />
              <button
                type="submit"
                className={`shrink-0 w-12 h-12 flex items-center justify-center rounded-2xl transition-all shadow-md active:scale-95 ${!chatInput.trim() || isLoading || agentStatus !== 'connected' || selectedSession?.chat_status === -1 ? 'bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed' : 'bg-primary text-white hover:bg-primary-hover hover:shadow-primary/30'}`}
                disabled={isLoading || agentStatus !== 'connected' || selectedSession?.chat_status === -1}
                aria-label="Send Message"
              >
                {isLoading ? (
                  <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin block"></span>
                ) : (
                  <svg className="w-5 h-5 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 5l7 7-7 7" />
                  </svg>
                )}
              </button>
            </form>
            <p className="text-center text-[10px] text-slate-400 dark:text-slate-500 mt-2 m-0 uppercase tracking-widest">
              Agentic protocol interface • A2A Platform
            </p>
          </div>
        </section>
      </section>

      {/* Rename Modal */}
      {sessionToRename && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in" onClick={closeRenameModal}>
          <div className="glass-panel w-full max-w-sm p-6 relative" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-bold text-slate-800 dark:text-slate-100 mb-4">Rename Chat</h3>
            <form onSubmit={submitRenameSession}>
              <input
                type="text"
                autoFocus
                className="input-base mb-6"
                value={renameInputValue}
                onChange={(e) => setRenameInputValue(e.target.value)}
                placeholder="Chat title"
              />
              <div className="flex justify-end gap-3">
                <button type="button" onClick={closeRenameModal} className="btn-ghost">Cancel</button>
                <button type="submit" className="btn-primary" disabled={!renameInputValue.trim()}>Save</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {sessionToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in" onClick={closeDeleteModal}>
          <div className="glass-panel w-full max-w-sm p-6 relative" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-bold text-slate-800 dark:text-slate-100 mb-2">Delete Chat?</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
              Are you sure you want to delete <strong className="text-slate-800 dark:text-slate-200">{sessionToDelete.title}</strong>? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button type="button" onClick={closeDeleteModal} className="btn-ghost">Cancel</button>
              <button type="button" onClick={submitDeleteSession} className="btn-danger">Delete</button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
