import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { ResizableTh } from '../components/ResizableTable'
import { getExcelData, getDownloadExcelUrl } from '../api/client'

function formatDate(s) {
  if (!s || s === '-') return '-'
  try {
    const d = new Date(s)
    if (isNaN(d.getTime())) return s
    return d.toISOString().slice(0, 10)
  } catch {
    return s
  }
}

function formatAmount(amount, currency) {
  if (amount == null || amount === '-') return '-'
  const n = parseFloat(String(amount).replace(/,/g, ''))
  if (isNaN(n)) return amount
  return n.toLocaleString('en-IN') + (currency ? ` ${currency}` : '')
}

function riskClass(score) {
  if (!score) return 'text-slate-500'
  const s = String(score).toLowerCase()
  if (s.includes('critical')) return 'text-red-600 font-semibold'
  if (s.includes('high')) return 'text-orange-600 font-semibold'
  if (s.includes('medium')) return 'text-amber-600 font-semibold'
  return 'text-emerald-600 font-semibold'
}

export default function ExcelTable() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState([])
  const [message, setMessage] = useState({ text: '', type: 'info' })
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getExcelData()
      if (res.success && res.data && res.data.length > 0) {
        setData(res.data)
        setMessage({ text: `Loaded ${res.data.length} extractions`, type: 'success' })
        setTimeout(() => setMessage({ text: '', type: '' }), 3000)
      } else {
        setData([])
        setMessage({ text: 'No data yet. Upload and extract documents.', type: 'info' })
      }
    } catch (e) {
      setError(e.message)
      setData([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const downloadExcel = () => {
    const link = document.createElement('a')
    link.href = getDownloadExcelUrl()
    link.download = 'contract_extractions.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    setMessage({ text: 'Download started', type: 'success' })
    setTimeout(() => setMessage({ text: '', type: '' }), 3000)
  }

  const cols = [
    'Extracted At', 'Document Name', 'Unique ID', 'IDs', 'Type',
    'Account Type', 'Party Names', 'Start Date', 'Due Date',
    'Amount', 'Currency', 'Risk Score', 'Matched PO',
  ]

  return (
    <Layout>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Data Table</h1>
          <p className="text-slate-200">View all contract extractions in table format</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            Refresh
          </button>
          <button
            type="button"
            onClick={downloadExcel}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
          >
            Download Excel
          </button>
          <Link to="/" className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Back to Home
          </Link>
        </div>
      </div>

      {message.text && (
        <div className={`mb-4 rounded-lg border p-3 text-sm ${
          message.type === 'success' ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
            : message.type === 'error' ? 'border-red-200 bg-red-50 text-red-800'
            : 'border-blue-200 bg-blue-50 text-blue-800'
        }`}>
          {message.text}
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
          </div>
        ) : data.length === 0 ? (
          <div className="py-16 text-center text-slate-500">No data. Extract some documents to see them here.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-gradient-to-r from-indigo-600 to-indigo-700 text-left text-xs font-semibold uppercase tracking-wider text-white">
                {cols.map((c) => (
                  <ResizableTh key={c} className="px-4 py-3 whitespace-nowrap">{c}</ResizableTh>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50/50">
                  <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatDate(row['Extracted At'])}</td>
                  <td className="px-4 py-3 text-slate-700">{row['Document Name'] || '-'}</td>
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-indigo-600">{row['Unique ID'] || '-'}</td>
                  <td className="px-4 py-3 text-slate-700">{row['ID'] || '-'}</td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className="rounded bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-800">
                      {row['Document Type'] || '-'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{row['Account Type (Head)'] || '-'}</td>
                  <td className="px-4 py-3 text-slate-700">{row['Party Names'] || '-'}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatDate(row['Start Date'])}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatDate(row['Due Date'])}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatAmount(row['Amount'], row['Currency'])}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-700">{row['Currency'] || '-'}</td>
                  <td className={`whitespace-nowrap px-4 py-3 ${riskClass(row['Risk Score'])}`}>{row['Risk Score'] || '-'}</td>
                  <td className="px-4 py-3 font-medium text-emerald-600">{row['Matched PO'] || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Layout>
  )
}
