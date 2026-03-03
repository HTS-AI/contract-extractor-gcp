import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { getJsonData } from '../api/client'

function getTypeBadge(type) {
  const t = (type || '').toUpperCase()
  if (t === 'NDA') return <span className="badge badge-nda">NDA</span>
  if (t === 'LEASE') return <span className="badge badge-lease">LEASE</span>
  return <span className="badge badge-contract">CONTRACT</span>
}

// Syntax-highlighted JSON tree (matches old dashboard.js formatJson)
function JsonTree({ obj, indent = 0 }) {
  const ind = '\u00A0\u00A0'.repeat(indent)

  if (obj === null || obj === undefined) {
    return <span className="json-null">null</span>
  }
  if (Array.isArray(obj)) {
    if (obj.length === 0) return <span className="json-null">[]</span>
    return (
      <>
        [<br />
        {obj.map((item, i) => (
          <React.Fragment key={i}>
            {ind}\u00A0\u00A0<JsonTree obj={item} indent={indent + 1} />
            {i < obj.length - 1 ? ',' : ''}
            <br />
          </React.Fragment>
        ))}
        {ind}]
      </>
    )
  }
  if (typeof obj === 'object') {
    const keys = Object.keys(obj)
    if (keys.length === 0) return <span className="json-null">{'{}'}</span>
    return (
      <>
        {'{'}<br />
        {keys.map((key, i) => (
          <React.Fragment key={key}>
            {ind}\u00A0\u00A0<span className="json-key">"{key}"</span>: <JsonTree obj={obj[key]} indent={indent + 1} />
            {i < keys.length - 1 ? ',' : ''}
            <br />
          </React.Fragment>
        ))}
        {ind}{'}'}
      </>
    )
  }
  if (typeof obj === 'string') {
    const s = obj.length > 500 ? obj.slice(0, 500) + '... (truncated)' : obj
    return <span className="json-string">"{s}"</span>
  }
  if (typeof obj === 'number') return <span className="json-number">{obj}</span>
  if (typeof obj === 'boolean') return <span className="json-boolean">{String(obj)}</span>
  return <span>{String(obj)}</span>
}

export default function Dashboard() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState([])
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [expanded, setExpanded] = useState(new Set())
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getJsonData()
      setData(res.extractions || [])
    } catch (e) {
      setError(e.message)
      setData([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = data.filter((item) => {
    const type = (item.data?.document_type || item.data?.contract_type || '').toUpperCase()
    if (typeFilter === 'NDA' && type !== 'NDA') return false
    if (typeFilter === 'LEASE' && type !== 'LEASE') return false
    if (typeFilter === 'CONTRACT' && (type === 'NDA' || type === 'LEASE')) return false
    if (!search) return true
    const s = search.toLowerCase()
    return JSON.stringify(item.data || {}).toLowerCase().includes(s) || (item.file_name || '').toLowerCase().includes(s)
  })

  const stats = {
    total: data.length,
    nda: data.filter((i) => (i.data?.document_type || i.data?.contract_type || '').toUpperCase() === 'NDA').length,
    lease: data.filter((i) => (i.data?.document_type || i.data?.contract_type || '').toUpperCase() === 'LEASE').length,
    contract: data.filter((i) => {
      const t = (i.data?.document_type || i.data?.contract_type || '').toUpperCase()
      return t === 'CONTRACT' || (t !== 'NDA' && t !== 'LEASE')
    }).length
  }

  const toggle = (i) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  }

  const expandAll = () => setExpanded(new Set(filtered.map((_, i) => i)))
  const collapseAll = () => setExpanded(new Set())

  return (
    <Layout>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-white">📊 JSON Data Dashboard</h1>
        <Link to="/" className="rounded-lg border-2 border-white bg-white/20 px-4 py-2 text-sm font-semibold text-indigo-700 hover:bg-white hover:text-indigo-700">
          ← Back to Main
        </Link>
      </div>

      <div className="stats-bar mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="stat-box rounded-xl border border-slate-200 bg-white p-5 text-center shadow-sm">
          <p className="stat-value text-2xl font-bold text-indigo-600">{stats.total}</p>
          <p className="stat-label text-sm text-slate-500">Total Extractions</p>
        </div>
        <div className="stat-box rounded-xl border border-slate-200 bg-white p-5 text-center shadow-sm">
          <p className="stat-value text-2xl font-bold text-indigo-600">{stats.nda}</p>
          <p className="stat-label text-sm text-slate-500">NDA Documents</p>
        </div>
        <div className="stat-box rounded-xl border border-slate-200 bg-white p-5 text-center shadow-sm">
          <p className="stat-value text-2xl font-bold text-indigo-600">{stats.lease}</p>
          <p className="stat-label text-sm text-slate-500">Lease Documents</p>
        </div>
        <div className="stat-box rounded-xl border border-slate-200 bg-white p-5 text-center shadow-sm">
          <p className="stat-value text-2xl font-bold text-indigo-600">{stats.contract}</p>
          <p className="stat-label text-sm text-slate-500">Contract Documents</p>
        </div>
      </div>

      <div className="controls-bar mb-4 flex flex-wrap gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <input
          type="text"
          placeholder="🔍 Search in JSON data..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="min-w-[200px] flex-1 rounded-lg border-2 border-slate-200 px-3 py-2.5 text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded-lg border-2 border-slate-200 px-3 py-2.5 text-slate-800 focus:border-indigo-500"
        >
          <option value="all">All Types</option>
          <option value="NDA">NDA</option>
          <option value="LEASE">Lease</option>
          <option value="CONTRACT">Contract</option>
        </select>
        <button
          type="button"
          onClick={expandAll}
          className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700"
        >
          Expand All
        </button>
        <button
          type="button"
          onClick={collapseAll}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Collapse All
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>
      )}

      {loading ? (
        <div className="loading flex flex-col items-center justify-center py-12 text-indigo-600">
          <div className="loading-spinner h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-indigo-600" />
          <p className="mt-4">Loading JSON data...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-500">
          <div className="empty-state-icon mb-4 text-5xl opacity-50">📄</div>
          <h3 className="text-lg font-semibold text-slate-700">No JSON Data Available</h3>
          <p className="mt-2">Extract some contracts to see JSON data here.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((item, index) => {
            const type = (item.data?.document_type || item.data?.contract_type || '').toUpperCase()
            const isOpen = expanded.has(index)
            const dateStr = item.extracted_at || item.uploaded_at
              ? new Date(item.extracted_at || item.uploaded_at).toLocaleString()
              : 'Unknown date'
            const extractionIdShort = item.extraction_id ? `${item.extraction_id.substring(0, 8)}...` : ''
            return (
              <div key={item.extraction_id || index} className="json-viewer rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <button
                  type="button"
                  onClick={() => toggle(index)}
                  className={`json-item-header flex w-full cursor-pointer items-center justify-between rounded-lg px-4 py-3 text-left transition ${
                    isOpen ? 'bg-indigo-600 text-white' : 'bg-indigo-50 hover:bg-indigo-100'
                  }`}
                >
                  <div className="flex flex-1 flex-wrap items-center gap-3">
                    <div className="json-item-title font-semibold">{item.file_name || 'Unknown Document'}</div>
                    <div className="json-item-meta flex flex-wrap gap-3 text-sm opacity-90">
                      {getTypeBadge(type)}
                      <span>📅 {dateStr}</span>
                      {extractionIdShort && <span>ID: {extractionIdShort}</span>}
                    </div>
                  </div>
                  <span className="ml-3 text-xl">{isOpen ? '▲' : '▼'}</span>
                </button>
                {isOpen && (
                  <div className="json-content active max-h-[600px] overflow-y-auto rounded-lg border border-slate-100 bg-slate-50 p-4 pt-3">
                    <div className="json-tree rounded-lg border border-slate-200 bg-white p-4 font-mono text-sm leading-relaxed text-slate-700">
                      <JsonTree obj={item.data || {}} />
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <style>{`
        .json-key { color: #4f46e5; font-weight: 600; }
        .json-string { color: #15803d; word-break: break-word; }
        .json-number { color: #dc2626; font-weight: 600; }
        .json-boolean { color: #2563eb; font-weight: 600; }
        .json-null { color: #64748b; font-style: italic; }
        .badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.75em; font-weight: 600; text-transform: uppercase; }
        .badge-nda { background: #d1fae5; color: #065f46; }
        .badge-lease { background: #dbeafe; color: #1e40af; }
        .badge-contract { background: #fef3c7; color: #92400e; }
      `}</style>
    </Layout>
  )
}
