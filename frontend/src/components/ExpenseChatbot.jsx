import React, { useState, useRef, useEffect } from 'react'
import { expenseChatStart, expenseChatAsk, expenseChatRefresh } from '../api/client'

function escapeHtml(text) {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function getTime() {
  return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

const QUICK_QUESTIONS = [
  'What is the total expense amount?',
  'List all vendors',
  'Show expenses with missing VAT',
  'Which is the highest expense?',
]

export default function ExpenseChatbot() {
  const [open, setOpen] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [asking, setAsking] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [recordCount, setRecordCount] = useState(0)
  const chatEndRef = useRef(null)
  const initRef = useRef(false)

  const scrollToBottom = () => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  useEffect(() => { scrollToBottom() }, [messages])

  const addUserMsg = (text) => setMessages((m) => [...m, { role: 'user', text, time: getTime() }])
  const addBotMsg = (text) => setMessages((m) => [...m, { role: 'bot', text, time: getTime() }])

  const startSession = async () => {
    setLoading(true)
    try {
      const res = await expenseChatStart()
      if (res.success) {
        setSessionId(res.session_id)
        setRecordCount(res.record_count || 0)
        setMessages([{
          role: 'bot',
          text: `Loaded ${res.record_count || 0} expense record(s). Ask me anything about your cash bills and expenses.`,
          time: getTime(),
        }])
      } else {
        setMessages([{ role: 'bot', text: res.error || 'No expense data found. Upload some cash bills first.', time: getTime() }])
      }
    } catch (e) {
      setMessages([{ role: 'bot', text: 'Failed to connect. Make sure the server is running.', time: getTime() }])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open && !initRef.current) {
      initRef.current = true
      startSession()
    }
  }, [open])

  const sendMessage = async (text) => {
    const question = (text || input).trim()
    if (!question || asking || !sessionId) return
    addUserMsg(question)
    setInput('')
    setAsking(true)
    try {
      const res = await expenseChatAsk(sessionId, question)
      if (res.success) {
        addBotMsg(res.answer)
      } else {
        addBotMsg('Sorry, I could not answer that: ' + (res.error || 'Unknown error'))
      }
    } catch {
      addBotMsg('Network error. Please try again.')
    } finally {
      setAsking(false)
    }
  }

  const handleRefresh = async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      const res = await expenseChatRefresh(sessionId)
      if (res.success) {
        setRecordCount(res.record_count || 0)
        addBotMsg(`Data refreshed. Now using ${res.record_count || 0} expense record(s) with latest edits.`)
      }
    } catch {
      addBotMsg('Failed to refresh data.')
    } finally {
      setLoading(false)
    }
  }

  const handleNewChat = async () => {
    setMessages([])
    setSessionId(null)
    setRecordCount(0)
    setInput('')
    initRef.current = false
    await startSession()
  }

  return (
    <>
      {/* Floating button */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="Expense Q&A Assistant"
        className="fixed bottom-8 right-8 z-[1000] flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-teal-700 text-white shadow-lg shadow-emerald-500/40 transition hover:scale-110 hover:shadow-emerald-500/50"
      >
        {sessionId && (
          <span className="absolute -right-0.5 -top-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-emerald-400 text-xs font-bold">{recordCount}</span>
        )}
        <svg className="h-7 w-7" fill="currentColor" viewBox="0 0 24 24">
          <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z" />
        </svg>
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-24 right-8 z-[1001] flex h-[600px] w-[400px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
          {/* Header */}
          <div className="flex-shrink-0 bg-gradient-to-br from-emerald-500 to-teal-700 px-5 py-4 text-white">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Expense Q&A</h3>
              <div className="flex items-center gap-1">
                {sessionId && (
                  <button type="button" onClick={handleNewChat} disabled={loading}
                    className="rounded-full p-1.5 hover:bg-white/20" title="Start new chat">
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  </button>
                )}
                {sessionId && (
                  <button type="button" onClick={handleRefresh} disabled={loading}
                    className="rounded-full p-1.5 hover:bg-white/20" title="Refresh data (pick up HITL edits)">
                    <svg className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  </button>
                )}
                <button type="button" onClick={() => setOpen(false)} className="rounded-full p-1.5 hover:bg-white/20" aria-label="Close">
                  <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            {sessionId && (
              <p className="mt-1 text-xs text-emerald-100">{recordCount} expense record(s) loaded</p>
            )}
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto bg-slate-50 p-4">
            {loading && !sessionId ? (
              <div className="flex flex-col items-center justify-center py-16">
                <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-200 border-t-emerald-600" />
                <p className="mt-4 text-sm text-slate-600">Loading expense data...</p>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                    {msg.role === 'bot' && (
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-emerald-100 text-base">💬</div>
                    )}
                    <div className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${
                      msg.role === 'user'
                        ? 'bg-emerald-600 text-white'
                        : 'border border-slate-200 bg-white text-slate-800'
                    }`}>
                      <div className="whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: escapeHtml(msg.text) }} />
                      <div className={`mt-1 text-xs ${msg.role === 'user' ? 'text-emerald-200' : 'text-slate-400'}`}>{msg.time}</div>
                    </div>
                    {msg.role === 'user' && (
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white text-sm">👤</div>
                    )}
                  </div>
                ))}

                {asking && (
                  <div className="flex gap-2">
                    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-emerald-100">💬</div>
                    <div className="flex gap-1 rounded-xl border border-slate-200 bg-white px-4 py-3">
                      <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: '0ms' }} />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: '150ms' }} />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                )}

                {/* Quick questions — shown only when session ready and few messages */}
                {sessionId && messages.length <= 2 && !asking && (
                  <div className="mt-2">
                    <p className="mb-2 text-xs font-medium text-slate-500">Try asking:</p>
                    <div className="flex flex-wrap gap-1.5">
                      {QUICK_QUESTIONS.map((q) => (
                        <button key={q} type="button" onClick={() => sendMessage(q)}
                          className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs text-emerald-700 hover:bg-emerald-100">
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>
            )}
          </div>

          {/* Input */}
          <div className="flex-shrink-0 border-t border-slate-200 bg-white p-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder={sessionId ? 'Ask about your expenses...' : 'Loading...'}
                disabled={!sessionId || asking}
                className="flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-sm outline-none focus:border-emerald-500 disabled:bg-slate-50"
              />
              <button
                type="button"
                onClick={() => sendMessage()}
                disabled={!sessionId || asking || !input.trim()}
                className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-teal-700 text-white disabled:opacity-50"
              >
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
