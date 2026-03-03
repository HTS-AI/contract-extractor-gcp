import React, { useState, useRef, useEffect } from 'react'
import {
  chatUpload,
  chatLoadFromExtraction,
  chatLoadAllDocuments,
  chatAsk,
  deleteChatSession
} from '../api/client'
import { useCurrentExtraction } from '../context/CurrentExtractionContext'

const SECTION = { UPLOAD: 'upload', LOADING: 'loading', CHAT: 'chat' }

function escapeHtml(text) {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function getTime() {
  return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

export default function Chatbot() {
  const { currentExtractionId } = useCurrentExtraction()
  const [open, setOpen] = useState(false)
  const [section, setSection] = useState(SECTION.UPLOAD)
  const [sessionId, setSessionId] = useState(null)
  const [filename, setFilename] = useState(null)
  const [lastExtractionId, setLastExtractionId] = useState(null)
  const [hasDocument, setHasDocument] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [asking, setAsking] = useState(false)
  const fileInputRef = useRef(null)
  const chatEndRef = useRef(null)
  const bodyRef = useRef(null)
  const loadedForRef = useRef(null)

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }
  useEffect(() => { scrollToBottom() }, [messages])

  const addUserMessage = (text) => {
    setMessages((m) => [...m, { role: 'user', text, time: getTime() }])
  }
  const addBotMessage = (text) => {
    setMessages((m) => [...m, { role: 'bot', text, time: getTime() }])
  }

  const loadFromExtraction = async (extractionId) => {
    if (!extractionId) return
    setSection(SECTION.LOADING)
    setLoading(true)
    try {
      const result = await chatLoadFromExtraction(extractionId)
      if (result.success) {
        setSessionId(result.session_id)
        setFilename(result.filename || 'Document')
        setLastExtractionId(extractionId)
        setHasDocument(true)
        const msg = result.message || `Document loaded! Ask me anything about "${result.filename}".`
        setMessages([{ role: 'bot', text: msg, time: getTime() }])
        setSection(SECTION.CHAT)
      } else {
        setSection(SECTION.UPLOAD)
        alert(result.error || 'Failed to load document.')
      }
    } catch (e) {
      setSection(SECTION.UPLOAD)
      alert('Error: ' + (e.message || 'Failed to load.'))
    } finally {
      setLoading(false)
    }
  }

  const loadAllDocs = async () => {
    setSection(SECTION.LOADING)
    setLoading(true)
    try {
      const result = await chatLoadAllDocuments()
      if (result.success) {
        setSessionId(result.session_id)
        setFilename(result.filename || 'All Invoices, POs & GRN')
        setLastExtractionId(null)
        setHasDocument(true)
        const count = result.document_count ?? 0
        const msg = result.message || `Loaded ${count} document(s). Ask me anything about your invoices and purchase orders.`
        setMessages([{ role: 'bot', text: msg, time: getTime() }])
        setSection(SECTION.CHAT)
      } else {
        setSection(SECTION.UPLOAD)
        alert(result.error || 'Failed to load documents.')
      }
    } catch (e) {
      setSection(SECTION.UPLOAD)
      alert('Error: ' + (e.message || 'Failed to load.'))
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const valid = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
    if (!valid.includes(file.type) && !/\.(pdf|docx|txt)$/i.test(file.name)) {
      alert('Please upload a PDF, DOCX, or TXT file.')
      return
    }
    setSection(SECTION.LOADING)
    setLoading(true)
    try {
      const result = await chatUpload(file)
      if (result.success) {
        setSessionId(result.session_id)
        setFilename(result.filename)
        setLastExtractionId(null)
        setHasDocument(true)
        let welcome = result.message
        if (result.from_cache === 'chatbot') welcome = `⚡ ${welcome}\n\n💾 Loaded from chatbot cache - instant response!`
        else if (result.from_cache === 'extraction') welcome = `⚡ ${welcome}\n\n💾 Loaded from extraction cache - reused parsed text!`
        setMessages([{ role: 'bot', text: welcome, time: getTime() }])
        setSection(SECTION.CHAT)
      } else {
        setSection(SECTION.UPLOAD)
        alert(result.error || 'Upload failed.')
      }
    } catch (e) {
      setSection(SECTION.UPLOAD)
      alert('Error: ' + (e.message || 'Upload failed.'))
    } finally {
      setLoading(false)
      e.target.value = ''
    }
  }

  useEffect(() => {
    if (!open || !currentExtractionId) return
    if (loadedForRef.current === currentExtractionId && sessionId) return
    if (sessionId && lastExtractionId !== currentExtractionId) {
      loadedForRef.current = null
      resetChat().then(() => {
        loadedForRef.current = currentExtractionId
        loadFromExtraction(currentExtractionId)
      })
      return
    }
    loadedForRef.current = currentExtractionId
    loadFromExtraction(currentExtractionId)
  }, [open, currentExtractionId])

  const resetChat = async () => {
    loadedForRef.current = null
    if (sessionId) {
      try {
        await deleteChatSession(sessionId)
      } catch (_) {}
    }
    setSessionId(null)
    setFilename(null)
    setLastExtractionId(null)
    setHasDocument(false)
    setMessages([])
    setInput('')
    setSection(SECTION.UPLOAD)
  }

  const sendMessage = async () => {
    const question = input.trim()
    if (!question || asking || !sessionId) return
    addUserMessage(question)
    setInput('')
    setAsking(true)
    try {
      const result = await chatAsk(sessionId, question)
      if (result.success) {
        addBotMessage(result.answer)
      } else {
        addBotMessage(`Sorry, I encountered an error: ${result.error || 'Unknown'}`)
      }
    } catch (e) {
      addBotMessage('Network error. Please try again.')
    } finally {
      setAsking(false)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title={hasDocument ? `Chat about ${filename}` : 'Ask questions about your documents'}
        className="fixed bottom-8 right-8 z-[1000] flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-purple-700 text-white shadow-lg shadow-violet-500/40 transition hover:scale-110 hover:shadow-violet-500/50"
      >
        {hasDocument ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-emerald-500 text-xs font-bold">✓</span>
        ) : null}
        <svg className="h-7 w-7" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z" />
        </svg>
      </button>

      {open && (
        <div className="fixed bottom-24 right-8 z-[1001] flex h-[600px] w-[400px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
          <div className="flex-shrink-0 bg-gradient-to-br from-violet-500 to-purple-700 px-5 py-4 text-white flex items-center justify-between">
            <h3 className="text-lg font-semibold">Document Q&A Assistant</h3>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-full p-1.5 hover:bg-white/20"
              aria-label="Close"
            >
              <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>

          <div ref={bodyRef} className="flex-1 overflow-y-auto bg-slate-50 p-4">
            {section === SECTION.UPLOAD && (
              <div className="flex flex-col items-center justify-center py-10 text-center">
                <div className="mb-4 text-4xl">📁</div>
                <h4 className="mb-1 font-medium text-slate-800">Upload a Document</h4>
                <p className="mb-5 text-sm text-slate-600">Ask questions about any PDF, DOCX, or TXT file</p>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-lg bg-gradient-to-br from-violet-500 to-purple-700 px-6 py-2.5 font-medium text-white shadow hover:opacity-90"
                >
                  Choose File
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt"
                  className="hidden"
                  onChange={handleFileUpload}
                />
                <p className="mt-4 mb-2 text-sm text-slate-500">or chat with all uploaded documents</p>
                <button
                  type="button"
                  onClick={loadAllDocs}
                  className="rounded-lg bg-slate-600 px-5 py-2.5 font-medium text-white hover:bg-slate-700"
                >
                  All Invoices, POs & GRN
                </button>
              </div>
            )}

            {section === SECTION.LOADING && (
              <div className="flex flex-col items-center justify-center py-16">
                <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-200 border-t-violet-600" />
                <p className="mt-4 text-sm text-slate-600">Processing your document...</p>
              </div>
            )}

            {section === SECTION.CHAT && (
              <div className="flex flex-col">
                <div className="mb-4 rounded-lg border-l-4 border-violet-500 bg-white p-3">
                  <div className="text-xs font-medium text-slate-500">Current Document</div>
                  <div className="text-sm font-medium text-violet-600 break-words">{filename}</div>
                  <button
                    type="button"
                    onClick={resetChat}
                    className="mt-2 rounded bg-slate-100 px-2 py-1 text-xs text-violet-600 hover:bg-slate-200"
                  >
                    Change Document
                  </button>
                </div>
                <div className="flex flex-col gap-3">
                  {messages.map((msg, i) => (
                    <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                      {msg.role === 'bot' && <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-slate-200 text-base">🤖</div>}
                      <div className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${msg.role === 'user' ? 'bg-violet-600 text-white' : 'bg-white border border-slate-200 text-slate-800'}`}>
                        <div className="whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: escapeHtml(msg.text) }} />
                        <div className="mt-1 text-xs text-slate-400">{msg.time}</div>
                      </div>
                      {msg.role === 'user' && <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-violet-600 text-white text-sm">👤</div>}
                    </div>
                  ))}
                  {asking && (
                    <div className="flex gap-2">
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-slate-200">🤖</div>
                      <div className="flex gap-1 rounded-xl border border-slate-200 bg-white px-4 py-3">
                        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: '0ms' }} />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: '150ms' }} />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  )}
                </div>
                <div ref={chatEndRef} />
              </div>
            )}
          </div>

          <div className="flex-shrink-0 border-t border-slate-200 bg-white p-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder="Ask a question about the document..."
                disabled={!sessionId || asking}
                className="flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-sm outline-none focus:border-violet-500 disabled:bg-slate-50"
              />
              <button
                type="button"
                onClick={sendMessage}
                disabled={!sessionId || asking || !input.trim()}
                className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-purple-700 text-white disabled:opacity-50"
              >
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" /></svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
