import React, { useState, useEffect, useCallback } from 'react'
import { getFilesList, deleteFile, deleteExtractionRecord } from '../api/client'

function formatFileSize(bytes) {
  if (bytes == null || bytes === '-') return '-'
  if (typeof bytes !== 'number') return String(bytes)
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

function formatDate(dateStr) {
  if (!dateStr || dateStr === '-') return '-'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return dateStr
  }
}

const TABS = [
  { key: 'extractions', label: 'Extractions', countKey: 'extractions' },
  { key: 'purchase_orders', label: 'Purchase Orders', countKey: 'purchase_orders' },
  { key: 'grns', label: 'GRN', countKey: 'grns' },
  { key: 'extraction_cache', label: 'Extraction Cache', countKey: 'extraction_cache' },
  { key: 'chatbot_cache', label: 'Chatbot Cache', countKey: 'chatbot_cache' },
  { key: 'exports', label: 'Exports', countKey: 'exports' }
]

function buildFileList(tab, data, gcsEnabled) {
  const d = data?.data || {}
  if (tab === 'extractions') {
    const records = (d.extraction_records || []).map((ext) => ({
      id: ext.extraction_id,
      name: `${ext.extraction_id}.json`,
      original: ext.file_name || 'Unknown',
      location: ext.location || 'local',
      size: ext.size ?? '-',
      modified: formatDate(ext.extracted_at || ext.uploaded_at || ext.modified),
      type: 'extraction',
      file_hash: ext.file_hash || ''
    }))
    const legacy = (d.extractions_data || []).map((f) => ({
      id: f.path,
      name: f.name || f.path,
      original: `${f.record_count ?? 0} records (legacy)`,
      location: f.location || 'local',
      size: formatFileSize(f.size),
      modified: formatDate(f.modified),
      type: 'legacy_extractions_data',
      file_hash: ''
    }))
    return [...records, ...legacy]
  }
  if (tab === 'purchase_orders') {
    return (d.purchase_orders || []).map((po) => ({
      id: po.file_hash,
      name: po.filename || 'Unknown',
      original: po.po_number ? `PO: ${po.po_number}` : (po.vendor || '-'),
      location: 'local',
      size: '-',
      modified: formatDate(po.indexed_at),
      type: 'purchase_order',
      file_hash: po.file_hash
    }))
  }
  if (tab === 'grns') {
    return (d.grns || []).map((grn) => ({
      id: grn.file_hash,
      name: grn.filename || 'Unknown',
      original: grn.po_number ? `PO: ${grn.po_number}` : (grn.vendor || '-'),
      location: gcsEnabled ? 'gcs' : 'local',
      size: '-',
      modified: formatDate(grn.indexed_at),
      type: 'grn',
      file_hash: grn.file_hash
    }))
  }
  if (tab === 'extraction_cache') {
    return (d.extraction_cache || []).map((f) => ({
      id: f.path,
      name: f.name,
      original: f.original_filename || '-',
      location: f.location || 'local',
      size: formatFileSize(f.size),
      modified: formatDate(f.modified),
      type: 'extraction_cache',
      file_hash: f.file_hash || ''
    }))
  }
  if (tab === 'chatbot_cache') {
    return (d.chatbot_cache || []).map((f) => ({
      id: f.path,
      name: f.name,
      original: f.original_filename || '-',
      location: f.location || 'local',
      size: formatFileSize(f.size),
      modified: formatDate(f.modified),
      type: 'chatbot_cache',
      file_hash: f.file_hash || ''
    }))
  }
  if (tab === 'exports') {
    return (d.exports || []).map((f) => ({
      id: f.path,
      name: f.name,
      original: '-',
      location: f.location || 'local',
      size: formatFileSize(f.size),
      modified: formatDate(f.modified),
      type: 'export',
      file_hash: ''
    }))
  }
  return []
}

function getTabCount(tab, data) {
  const d = data?.data || {}
  if (tab === 'extractions') return (d.extraction_records || []).length + (d.extractions_data || []).length
  if (tab === 'purchase_orders') return (d.purchase_orders || []).length
  if (tab === 'grns') return (d.grns || []).length
  if (tab === 'extraction_cache') return (d.extraction_cache || []).length
  if (tab === 'chatbot_cache') return (d.chatbot_cache || []).length
  if (tab === 'exports') return (d.exports || []).length
  return 0
}

export default function FileManagerModal({ onClose, onRefresh }) {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [tab, setTab] = useState('extractions')
  const [selected, setSelected] = useState(new Set())
  const [deleteProgress, setDeleteProgress] = useState(null)
  const [error, setError] = useState(null)

  const gcsEnabled = data?.data?.gcs_enabled === true

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getFilesList()
      setData(res)
    } catch (e) {
      setError(e.message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const fileList = data ? buildFileList(tab, data, gcsEnabled) : []
  const selectAll = () => setSelected(new Set(fileList.map((f) => f.id + '|' + f.type)))
  const deselectAll = () => setSelected(new Set())
  const toggleSelect = (id, type) => {
    const key = id + '|' + type
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }
  const isSelected = (id, type) => selected.has(id + '|' + type)

  const deleteOne = async (file) => {
    if (!window.confirm('Are you sure you want to delete this file?')) return
    setDeleteProgress({ current: 0, total: 1, message: file.name })
    try {
      if (file.type === 'extraction') {
        await deleteExtractionRecord(file.id)
      } else if (file.type === 'purchase_order' && file.file_hash) {
        await deleteFile({ file_hashes: [file.file_hash] })
      } else if (file.type === 'grn' && file.file_hash) {
        await deleteFile({ grn_file_hashes: [file.file_hash] })
      } else {
        await deleteFile({
          files: [{ path: file.id, location: file.location }],
          ...(file.file_hash ? { file_hashes: [file.file_hash] } : {})
        })
      }
      await load()
      onRefresh?.()
    } catch (e) {
      console.error(e)
    } finally {
      setDeleteProgress(null)
    }
  }

  const deleteSelected = async () => {
    if (selected.size === 0) return
    if (!window.confirm(`Delete ${selected.size} selected file(s)?`)) return
    const toDelete = fileList.filter((f) => isSelected(f.id, f.type))
    setDeleteProgress({ current: 0, total: toDelete.length, message: '' })
    let done = 0
    for (const file of toDelete) {
      setDeleteProgress((p) => ({ ...p, current: done, message: file.name }))
      try {
        if (file.type === 'extraction') {
          await deleteExtractionRecord(file.id)
        } else if (file.type === 'purchase_order' && file.file_hash) {
          await deleteFile({ file_hashes: [file.file_hash] })
        } else if (file.type === 'grn' && file.file_hash) {
          await deleteFile({ grn_file_hashes: [file.file_hash] })
        } else {
          await deleteFile({
            files: [{ path: file.id, location: file.location }],
            ...(file.file_hash ? { file_hashes: [file.file_hash] } : {})
          })
        }
      } catch (e) {
        console.error(e)
      }
      done++
    }
    setDeleteProgress(null)
    setSelected(new Set())
    await load()
    onRefresh?.()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 bg-gradient-to-r from-red-600 to-red-700 px-4 py-3 text-white">
          <h3 className="flex items-center gap-2 text-lg font-semibold">🗂️ File & Cache Manager</h3>
          <button type="button" onClick={onClose} className="rounded p-1.5 hover:bg-white/20">×</button>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-red-50/80 px-4 py-2">
          <span
            className={`inline-block rounded-full px-3 py-1 text-sm font-semibold ${
              gcsEnabled ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800'
            }`}
          >
            {loading ? '…' : gcsEnabled ? '☁️ GCS Connected' : '💾 Local Storage Only'}
          </span>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              🔄 Refresh
            </button>
            <button
              type="button"
              onClick={selectAll}
              className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700"
            >
              ☑️ Select All
            </button>
            <button
              type="button"
              onClick={deselectAll}
              className="rounded-lg bg-slate-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
            >
              ☐ Deselect All
            </button>
            <button
              type="button"
              onClick={deleteSelected}
              disabled={selected.size === 0}
              className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              🗑️ Delete Selected
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-1 border-b border-slate-200 p-2">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                tab === t.key ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {t.label} <span className="ml-1 rounded bg-black/10 px-1.5 py-0.5">{getTabCount(t.key, data)}</span>
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 py-12 text-slate-600">
            <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
            <p className="font-medium">🔌 Please wait, connecting to GCS...</p>
            <p className="text-sm text-slate-500">Loading your files from cloud storage</p>
          </div>
        ) : error ? (
          <div className="p-4 text-center text-red-600">{error}</div>
        ) : deleteProgress ? (
          <div className="flex flex-1 flex-col justify-center gap-2 bg-amber-50 p-6">
            <div className="flex items-center gap-2">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-amber-300 border-t-amber-600" />
              <span className="font-medium text-amber-900">
                Deleting… {deleteProgress.current} of {deleteProgress.total}
              </span>
            </div>
            {deleteProgress.message && (
              <p className="truncate text-sm text-amber-800">{deleteProgress.message}</p>
            )}
            <div className="h-2 w-full overflow-hidden rounded-full bg-amber-200">
              <div
                className="h-full bg-amber-600 transition-all duration-300"
                style={{
                  width: deleteProgress.total ? `${(deleteProgress.current / deleteProgress.total) * 100}%` : '0%'
                }}
              />
            </div>
          </div>
        ) : fileList.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center py-12 text-slate-500">
            <p className="text-4xl">📭</p>
            <p className="mt-2">No files in this category</p>
          </div>
        ) : (
          <div className="flex-1 overflow-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-slate-100">
                  <th className="w-10 border-b border-slate-200 p-2 text-center">☐</th>
                  <th className="border-b border-slate-200 p-2 text-left">File Name</th>
                  <th className="border-b border-slate-200 p-2 text-left">Original Document</th>
                  <th className="border-b border-slate-200 p-2 text-center">Location</th>
                  <th className="border-b border-slate-200 p-2 text-right">Size</th>
                  <th className="border-b border-slate-200 p-2 text-center">Modified</th>
                  <th className="border-b border-slate-200 p-2 text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {fileList.map((f) => (
                  <tr key={f.id + f.type} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="p-2 text-center">
                      <input
                        type="checkbox"
                        checked={isSelected(f.id, f.type)}
                        onChange={() => toggleSelect(f.id, f.type)}
                        className="h-4 w-4 rounded border-slate-300"
                      />
                    </td>
                    <td className="max-w-[200px] truncate font-mono text-xs" title={f.name}>
                      {f.name}
                    </td>
                    <td className="max-w-[200px] truncate" title={f.original}>
                      {f.original}
                    </td>
                    <td className="p-2 text-center">
                      <span
                        className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${
                          f.location === 'gcs' ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'
                        }`}
                      >
                        {f.location === 'gcs' ? '☁️ GCS' : '💾 Local'}
                      </span>
                    </td>
                    <td className="p-2 text-right font-mono text-xs">{f.size}</td>
                    <td className="p-2 text-center text-xs">{f.modified}</td>
                    <td className="p-2 text-center">
                      <button
                        type="button"
                        onClick={() => deleteOne(f)}
                        className="rounded bg-red-100 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-200"
                      >
                        🗑️ Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-600">
          <span>{selected.size} file(s) selected</span>
          <button
            type="button"
            onClick={() => {
              load()
              onRefresh?.()
              onClose?.()
            }}
            className="rounded-lg bg-slate-200 px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-300"
          >
            Refresh list & close
          </button>
        </div>
      </div>
    </div>
  )
}
