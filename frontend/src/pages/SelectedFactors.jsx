import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { getJsonData, getExcelData } from '../api/client'

function getNested(obj, paths) {
  for (const p of paths) {
    if (obj == null) return ''
    if (typeof p === 'string' && p.includes('.')) {
      let v = obj
      for (const k of p.split('.')) v = v?.[k]
      obj = v
    } else {
      obj = obj?.[p]
    }
  }
  return obj != null && obj !== '' ? String(obj) : ''
}

function getDocId(data) {
  if (!data) return ''
  if (data.document_id) return data.document_id
  const ids = data.document_ids
  if (ids && typeof ids === 'object') {
    return ids.invoice_id || ids.invoice_number || ids.contract_id || ids.agreement_id || ''
  }
  return ''
}

function formatPartyNames(data) {
  if (!data?.party_names) return ''
  const p = data.party_names
  if (typeof p === 'string') return p
  if (typeof p === 'object') {
    const arr = [p.party_1, p.party_2].filter(Boolean)
    if (p.additional_parties) arr.push(...p.additional_parties.map((x) => (typeof x === 'string' ? x : x?.name)))
    return arr.join(', ')
  }
  return ''
}

function formatRisk(score) {
  if (score == null) return ''
  const n = typeof score === 'object' ? score.score ?? score.value ?? 0 : Number(score)
  if (n >= 80) return { label: 'Critical', class: 'bg-red-100 text-red-800' }
  if (n >= 60) return { label: 'High', class: 'bg-orange-100 text-orange-800' }
  if (n >= 30) return { label: 'Medium', class: 'bg-amber-100 text-amber-800' }
  return { label: 'Low', class: 'bg-emerald-100 text-emerald-800' }
}

export default function SelectedFactors() {
  const [loading, setLoading] = useState(true)
  const [documents, setDocuments] = useState([])
  const [selectedIndex, setSelectedIndex] = useState('')
  const [dataSource, setDataSource] = useState('')
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [jsonRes, excelRes] = await Promise.all([getJsonData(), getExcelData()])
      const jsonList = jsonRes.extractions || []
      const excelRows = excelRes.success && excelRes.data ? excelRes.data : []
      const excelMap = {}
      excelRows.forEach((row) => {
        const name = (row['Document Name'] || '').trim().toLowerCase().replace(/[^a-z0-9]/g, '')
        if (name) excelMap[name] = row
      })
      const merged = jsonList.map((doc) => ({
        ...doc,
        excel_data: excelMap[(doc.file_name || '').toLowerCase().replace(/[^a-z0-9]/g, '')]
      }))
      excelRows.forEach((row) => {
        const name = (row['Document Name'] || '').trim()
        const norm = name.toLowerCase().replace(/[^a-z0-9]/g, '')
        if (norm && !merged.some((d) => (d.file_name || '').toLowerCase().replace(/[^a-z0-9]/g, '') === norm)) {
          merged.push({
            file_name: name,
            extracted_at: row['Extracted At'],
            data: {},
            excel_data: row,
            from_excel: true
          })
        }
      })
      merged.sort((a, b) => (b.extracted_at || b.uploaded_at || '').localeCompare(a.extracted_at || a.uploaded_at || ''))
      setDocuments(merged)
      if (merged.length > 0 && selectedIndex === '') setSelectedIndex('0')
    } catch (e) {
      setError(e.message)
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }, [selectedIndex])

  useEffect(() => { load() }, [load])

  const selected = documents[parseInt(selectedIndex, 10)]
  const factors = selected
    ? selected.excel_data
      ? [
          { label: 'Document Name', value: selected.excel_data['Document Name'] || selected.file_name },
          { label: 'Document Type', value: selected.excel_data['Document Type'] },
          { label: 'Document ID', value: selected.excel_data['ID'] || selected.excel_data['Document ID'] },
          { label: 'Party Names', value: selected.excel_data['Party Names'] },
          { label: 'Start Date', value: selected.excel_data['Start Date'] },
          { label: 'Due Date', value: selected.excel_data['Due Date'] },
          { label: 'Amount', value: selected.excel_data['Amount'] },
          { label: 'Currency', value: selected.excel_data['Currency'] },
          { label: 'Account Type', value: selected.excel_data['Account Type (Head)'] },
          { label: 'Risk Score', value: selected.excel_data['Risk Score'] }
        ]
      : [
          { label: 'Document Name', value: selected.file_name },
          { label: 'Document Type', value: getNested(selected.data, ['document_type', 'contract_type']) },
          { label: 'Document ID', value: getDocId(selected.data) },
          { label: 'Party Names', value: formatPartyNames(selected.data) || getNested(selected.data, ['party_names', 'parties_to_agreement']) },
          { label: 'Start Date', value: getNested(selected.data, ['start_date', 'effective_date', 'execution_date']) },
          { label: 'Due Date', value: getNested(selected.data, ['due_date', 'end_date']) },
          { label: 'Amount', value: getNested(selected.data, ['amount', 'payment_terms.amount', 'contract_value']) },
          { label: 'Currency', value: getNested(selected.data, ['currency', 'payment_terms.currency']) },
          { label: 'Account Type', value: getNested(selected.data, ['account_type']) },
          {
            label: 'Risk Score',
            value: (() => {
              const r = selected.data?.risk_score
              const f = formatRisk(r)
              return f ? f.label : (r != null ? String(r) : '')
            })()
          }
        ]
    : []

  useEffect(() => {
    if (selected) {
      setDataSource(selected.from_excel || selected.excel_data ? 'Excel' : 'JSON')
    }
  }, [selected])

  return (
    <Layout>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-white">Selected Factors</h1>
        <Link to="/" className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          ← Back to Main
        </Link>
      </div>

      <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="mb-2 block text-sm font-semibold text-slate-700">Select document</label>
        <select
          value={selectedIndex}
          onChange={(e) => setSelectedIndex(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-800 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
        >
          <option value="">— Select —</option>
          {documents.map((doc, i) => (
            <option key={i} value={String(i)}>
              {doc.file_name || `Document ${i + 1}`} {doc.from_excel ? '(Excel)' : ''}
            </option>
          ))}
        </select>
        {dataSource && (
          <p className="mt-2 text-xs text-slate-500">Data source: {dataSource}</p>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
        </div>
      ) : !selected ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-500">
          Select a document to view factors.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {factors.map((f) => (
            <div
              key={f.label}
              className="rounded-xl border-l-4 border-indigo-500 bg-white p-4 shadow-sm border border-slate-200"
            >
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-indigo-600">{f.label}</p>
              <p className={f.value ? 'text-slate-800' : 'text-slate-400 italic'}>
                {f.label === 'Risk Score' && typeof f.value === 'string' && ['Low', 'Medium', 'High', 'Critical'].includes(f.value)
                  ? (
                    <span className={`inline-block rounded-full px-2 py-0.5 text-sm font-medium ${
                      f.value === 'Critical' ? 'bg-red-100 text-red-800'
                      : f.value === 'High' ? 'bg-orange-100 text-orange-800'
                      : f.value === 'Medium' ? 'bg-amber-100 text-amber-800'
                      : 'bg-emerald-100 text-emerald-800'
                    }`}>
                      {f.value}
                    </span>
                  )
                  : (f.value || '(Not available)')}
              </p>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
