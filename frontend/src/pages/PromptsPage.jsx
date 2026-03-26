import { useEffect, useState } from 'react'

import AppHeader from '../components/AppHeader'
import { apiRequest } from '../lib/api'

export default function PromptsPage({ token, username, onLogout, theme, toggleTheme }) {
  const [prompts, setPrompts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState({ title: '', content: '' })
  const [saving, setSaving] = useState(false)
  const [editingId, setEditingId] = useState(null)

  async function loadPrompts() {
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest('/api/prompts', {
        token,
        onUnauthorized: onLogout,
      })
      setPrompts(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPrompts()
  }, [])

  function startEdit(prompt) {
    setEditingId(prompt.id)
    setDraft({
      title: prompt.title || '',
      content: prompt.content || '',
    })
  }

  function resetDraft() {
    setEditingId(null)
    setDraft({ title: '', content: '' })
  }

  async function submitPrompt(e) {
    e.preventDefault()
    const title = draft.title.trim()
    const content = draft.content.trim()
    if (!title || !content) {
      setError('Prompt title and content are required.')
      return
    }
    setSaving(true)
    setError('')
    try {
      if (editingId) {
        const updated = await apiRequest(`/api/prompts/${editingId}`, {
          method: 'PATCH',
          token,
          body: { title, content },
          onUnauthorized: onLogout,
        })
        setPrompts((prev) => prev.map((item) => (item.id === editingId ? updated : item)))
      } else {
        const created = await apiRequest('/api/prompts', {
          method: 'POST',
          token,
          body: { title, content, agent_id: null },
          onUnauthorized: onLogout,
        })
        setPrompts((prev) => [created, ...prev])
      }
      resetDraft()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function deletePrompt(id) {
    try {
      await apiRequest(`/api/prompts/${id}`, {
        method: 'DELETE',
        token,
        onUnauthorized: onLogout,
      })
      setPrompts((prev) => prev.filter((item) => item.id !== id))
      if (editingId === id) {
        resetDraft()
      }
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <main className="ambient-bg min-h-screen p-4 md:p-6 lg:p-8 text-foreground">
      <div className="max-w-6xl mx-auto">
        <AppHeader
          title="Prompt Library"
          subtitle="Manage reusable prompts across your workspace"
          onLogout={onLogout}
          username={username}
          showPromptsNav={false}
          theme={theme}
          toggleTheme={toggleTheme}
        />
        {error && (
          <div className="bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-xl mb-6">
            {error}
          </div>
        )}
        <section className="grid lg:grid-cols-[0.95fr,1.05fr] gap-6">
          <div className="glass-panel p-6">
            <h2 className="m-0 text-lg font-semibold text-slate-800 dark:text-slate-100">
              {editingId ? 'Edit Prompt' : 'New Prompt'}
            </h2>
            <p className="mt-1 mb-5 text-sm text-slate-500 dark:text-slate-400">
              Save reusable prompts that can be applied from the chat composer.
            </p>
            <form className="space-y-4" onSubmit={submitPrompt}>
              <input
                className="input-base"
                placeholder="Prompt title"
                value={draft.title}
                onChange={(e) => setDraft((prev) => ({ ...prev, title: e.target.value }))}
              />
              <textarea
                className="input-base min-h-[260px] resize-y"
                placeholder="Prompt content"
                value={draft.content}
                onChange={(e) => setDraft((prev) => ({ ...prev, content: e.target.value }))}
              />
              <div className="flex justify-end gap-3">
                {editingId && (
                  <button type="button" className="btn-ghost" onClick={resetDraft}>
                    Cancel
                  </button>
                )}
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? 'Saving...' : editingId ? 'Update Prompt' : 'Create Prompt'}
                </button>
              </div>
            </form>
          </div>

          <div className="glass-panel p-6 min-h-[420px]">
            <h2 className="m-0 text-lg font-semibold text-slate-800 dark:text-slate-100">
              Saved Prompts
            </h2>
            <p className="mt-1 mb-5 text-sm text-slate-500 dark:text-slate-400">
              Workspace-wide prompts are available from the chat page for any agent.
            </p>
            <div className="space-y-4 max-h-[620px] overflow-y-auto custom-scroll pr-1">
              {loading ? (
                <div className="text-sm text-slate-500 dark:text-slate-400">Loading prompts...</div>
              ) : prompts.length ? (
                prompts.map((prompt) => (
                  <article key={prompt.id} className="rounded-2xl border border-cardBorder bg-card/50 p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className="m-0 text-sm font-semibold text-slate-800 dark:text-slate-200">
                          {prompt.title}
                        </h3>
                        <p className="mt-2 mb-0 text-sm text-slate-600 dark:text-slate-400 whitespace-pre-wrap line-clamp-5">
                          {prompt.content}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button type="button" className="btn-ghost py-1.5 px-3 text-xs" onClick={() => startEdit(prompt)}>
                          Edit
                        </button>
                        <button type="button" className="btn-danger py-1.5 px-3 text-xs" onClick={() => deletePrompt(prompt.id)}>
                          Delete
                        </button>
                      </div>
                    </div>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-cardBorder p-6 text-sm text-slate-500 dark:text-slate-400">
                  No prompts saved yet.
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}
