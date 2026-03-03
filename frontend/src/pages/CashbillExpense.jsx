import React, { useState, useCallback, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getExpenseList, deleteExpense, updateExpense, getExpenseFileUrl } from '../api/client'
import ExpenseChatbot from '../components/ExpenseChatbot'

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

function formatOmanTimestamp(s) {
  if (!s || s === '-') return '-'
  try {
    const d = new Date(s)
    if (isNaN(d.getTime())) return s
    return d.toLocaleString('en-GB', {
      timeZone: 'Asia/Muscat',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return s
  }
}

function formatAmount(amount, currency) {
  if (amount == null || amount === '' || amount === undefined) return '-'
  const n = parseFloat(String(amount).replace(/,/g, ''))
  if (isNaN(n)) return amount
  return n.toLocaleString('en-IN') + (currency ? ` ${currency}` : '')
}

function ConfidenceBadge({ score }) {
  if (score == null) return <span className="text-slate-400">-</span>
  const pct = typeof score === 'number' ? (score <= 1 ? score * 100 : score) : parseFloat(score) || 0
  const color = pct >= 80 ? 'bg-emerald-100 text-emerald-800' : pct >= 50 ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>{pct.toFixed(0)}%</span>
}

const IMAGE_EXTS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
const TEXT_EXTS = ['txt', 'csv', 'log', 'json', 'xml', 'md']
const IFRAME_EXTS = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']

function getFileExt(name) {
  if (!name) return ''
  const parts = name.split('.')
  return parts.length > 1 ? parts.pop().toLowerCase() : ''
}

function FilePreview({ expenseId, fileName, documentName }) {
  const displayName = fileName || documentName || ''
  const ext = getFileExt(displayName)
  const url = getExpenseFileUrl(expenseId)

  const isImage = IMAGE_EXTS.includes(ext)
  const isPdf = ext === 'pdf'
  const isText = TEXT_EXTS.includes(ext)
  const isIframe = !isPdf && IFRAME_EXTS.includes(ext)

  const [failed, setFailed] = useState(false)
  const [textContent, setTextContent] = useState(null)
  const [textLoading, setTextLoading] = useState(false)

  useEffect(() => {
    setFailed(false)
    setTextContent(null)
    if (isText && expenseId) {
      setTextLoading(true)
      fetch(url)
        .then((r) => { if (!r.ok) throw new Error(); return r.text() })
        .then((t) => setTextContent(t))
        .catch(() => setFailed(true))
        .finally(() => setTextLoading(false))
    }
  }, [expenseId, url, isText])

  if (!expenseId) return null

  const renderPreview = () => {
    if (failed) {
      return (
        <div className="flex h-full flex-col items-center justify-center text-slate-400">
          <div className="mb-2 text-4xl">📎</div>
          <p className="mb-1 text-sm font-medium text-slate-500">Source file not available</p>
          <p className="text-xs text-slate-400">Re-upload the document to enable preview</p>
        </div>
      )
    }

    if (isImage) {
      return <img src={url} alt={displayName} className="h-auto w-full rounded-lg object-contain" onError={() => setFailed(true)} />
    }
    if (isPdf || isIframe) {
      return <iframe src={url} title={displayName} className="h-full w-full rounded-lg border-0" style={{ minHeight: '600px' }} onError={() => setFailed(true)} />
    }
    if (isText) {
      if (textLoading) return <div className="flex h-full items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-emerald-600" /></div>
      if (textContent != null) {
        return <pre className="h-full overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700 whitespace-pre-wrap break-words">{textContent}</pre>
      }
    }

    return (
      <div className="flex h-full flex-col items-center justify-center text-slate-400">
        <div className="mb-2 text-4xl">📎</div>
        <p className="mb-1 text-sm font-medium text-slate-500">{ext ? `.${ext} preview` : 'Preview'} not supported inline</p>
        <p className="text-xs text-slate-400">Use the Download button above to view the file</p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2.5">
        <span className="text-base">📄</span>
        <h3 className="text-sm font-semibold text-slate-700">Source Document</h3>
        <span className="ml-auto max-w-[200px] truncate text-xs text-slate-500" title={displayName}>{displayName || 'N/A'}</span>
        <a href={url} download={displayName || 'file'} className="ml-2 flex-shrink-0 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100" title="Download file">
          ⬇ Download
        </a>
      </div>
      <div className="flex-1 overflow-auto p-2">
        {renderPreview()}
      </div>
    </div>
  )
}

function EditableField({ label, value, field, onChange, mono = false, multiline = false }) {
  const baseClass = `w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-800 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/30 ${mono ? 'font-mono' : ''}`
  return (
    <div>
      <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">{label}</label>
      {multiline ? (
        <textarea
          value={value ?? ''}
          onChange={(e) => onChange(field, e.target.value)}
          rows={2}
          className={baseClass + ' resize-y'}
        />
      ) : (
        <input
          type="text"
          value={value ?? ''}
          onChange={(e) => onChange(field, e.target.value)}
          className={baseClass}
        />
      )}
    </div>
  )
}

function EditableLineItems({ items, onChange }) {
  const update = (idx, field, val) => {
    const updated = items.map((it, i) => i === idx ? { ...it, [field]: val } : it)
    onChange('line_items', updated)
  }
  const addRow = () => {
    onChange('line_items', [...items, { sl_no: String(items.length + 1), description: '', qty: '', unit: '', unit_price: '', amount: '' }])
  }
  const removeRow = (idx) => {
    onChange('line_items', items.filter((_, i) => i !== idx))
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Line Items</label>
        <button type="button" onClick={addRow} className="rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100">
          + Add row
        </button>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
              <th className="px-2 py-1.5 w-8">#</th>
              <th className="px-2 py-1.5">Description</th>
              <th className="px-2 py-1.5 w-16">Qty</th>
              <th className="px-2 py-1.5 w-16">Unit</th>
              <th className="px-2 py-1.5 w-24">Unit Price</th>
              <th className="px-2 py-1.5 w-24">Amount</th>
              <th className="px-2 py-1.5 w-8"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((it, i) => (
              <tr key={i}>
                <td className="px-2 py-1 text-slate-500">{i + 1}</td>
                <td className="px-1 py-1">
                  <input type="text" value={it.description ?? ''} onChange={(e) => update(i, 'description', e.target.value)}
                    className="w-full rounded border border-slate-200 px-2 py-1 text-sm focus:border-emerald-500 focus:outline-none" />
                </td>
                <td className="px-1 py-1">
                  <input type="text" value={it.qty ?? ''} onChange={(e) => update(i, 'qty', e.target.value)}
                    className="w-full rounded border border-slate-200 px-2 py-1 text-sm text-right focus:border-emerald-500 focus:outline-none" />
                </td>
                <td className="px-1 py-1">
                  <input type="text" value={it.unit ?? ''} onChange={(e) => update(i, 'unit', e.target.value)}
                    className="w-full rounded border border-slate-200 px-2 py-1 text-sm focus:border-emerald-500 focus:outline-none" />
                </td>
                <td className="px-1 py-1">
                  <input type="text" value={it.unit_price ?? ''} onChange={(e) => update(i, 'unit_price', e.target.value)}
                    className="w-full rounded border border-slate-200 px-2 py-1 text-sm text-right focus:border-emerald-500 focus:outline-none" />
                </td>
                <td className="px-1 py-1">
                  <input type="text" value={it.amount ?? ''} onChange={(e) => update(i, 'amount', e.target.value)}
                    className="w-full rounded border border-slate-200 px-2 py-1 text-sm text-right focus:border-emerald-500 focus:outline-none" />
                </td>
                <td className="px-1 py-1">
                  <button type="button" onClick={() => removeRow(i)} className="text-red-400 hover:text-red-600" title="Remove">✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function VerificationPanel({ expense, onClose, onSaved }) {
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    if (expense) setForm({ ...expense })
  }, [expense])

  if (!expense) return null

  const onChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    setSaved(false)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const { expense_id, extracted_at, source_file_path, source_file_name, raw_text, description, ...payload } = form
      await updateExpense(expense.expense_id, payload)
      setSaved(true)
      if (onSaved) onSaved()
    } catch (e) {
      alert('Save failed: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  const lineItems = Array.isArray(form.line_items) ? form.line_items : []

  return (
    <div className="fixed inset-0 z-50 flex bg-black/50" onClick={onClose}>
      <div className="flex h-full w-full" onClick={(e) => e.stopPropagation()}>

        {/* Left: Source file */}
        <div className="hidden w-1/2 flex-shrink-0 p-3 lg:block">
          <FilePreview expenseId={expense.expense_id} fileName={expense.source_file_name} documentName={expense.document_name} />
        </div>

        {/* Right: Editable details */}
        <div className="flex w-full flex-col bg-slate-50 lg:w-1/2">
          {/* Header */}
          <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 py-3 shadow-sm">
            <div>
              <h3 className="text-lg font-semibold text-slate-800">Human Verification</h3>
              <p className="text-xs text-slate-500">Edit fields to correct extraction results, then save.</p>
            </div>
            <div className="flex items-center gap-2">
              {saved && <span className="text-xs font-medium text-emerald-600">Saved!</span>}
              <button type="button" onClick={handleSave} disabled={saving}
                className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50">
                {saving ? 'Saving...' : 'Save'}
              </button>
              <button type="button" onClick={onClose}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100">
                Close
              </button>
            </div>
          </div>

          {/* Mobile file preview toggle */}
          <div className="border-b border-slate-200 bg-white px-4 py-2 lg:hidden">
            {(expense.source_file_name || expense.document_name) ? (
              <a href={getExpenseFileUrl(expense.expense_id)} target="_blank" rel="noopener noreferrer"
                className="text-sm font-medium text-emerald-600 hover:underline">
                📄 Open source file: {expense.source_file_name || expense.document_name}
              </a>
            ) : (
              <span className="text-sm text-slate-400">No source file attached</span>
            )}
          </div>

          {/* Scrollable form */}
          <div className="flex-1 overflow-auto p-4 space-y-5">

            {/* Receipt / Bill Info */}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
                <span>🧾</span> Receipt / Bill Information
              </h4>
              <div className="grid gap-3 sm:grid-cols-2">
                <EditableField label="Document Type" value={form.document_type} field="document_type" onChange={onChange} />
                <EditableField label="Expense Type" value={form.expense_type} field="expense_type" onChange={onChange} />
                <EditableField label="Receipt No" value={form.receipt_no} field="receipt_no" onChange={onChange} />
                <EditableField label="Invoice No" value={form.invoice_no} field="invoice_no" onChange={onChange} />
                <EditableField label="Receipt Date" value={form.receipt_date} field="receipt_date" onChange={onChange} />
                <EditableField label="Receipt Time" value={form.receipt_time} field="receipt_time" onChange={onChange} />
                <EditableField label="Currency" value={form.currency} field="currency" onChange={onChange} />
              </div>
            </div>

            {/* Vendor Details */}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
                <span>🏢</span> Vendor Details
              </h4>
              <div className="grid gap-3 sm:grid-cols-2">
                <EditableField label="Vendor / Merchant" value={form.vendor} field="vendor" onChange={onChange} />
                <div className="sm:col-span-2">
                  <EditableField label="Address" value={form.vendor_address} field="vendor_address" onChange={onChange} multiline />
                </div>
                <EditableField label="VAT Number" value={form.site_vat_no} field="site_vat_no" onChange={onChange} mono />
                <EditableField label="C.R. No" value={form.cr_no} field="cr_no" onChange={onChange} mono />
                <EditableField label="Customer" value={form.customer_name} field="customer_name" onChange={onChange} />
                <EditableField label="Site Name" value={form.site_name} field="site_name" onChange={onChange} />
                <EditableField label="Site Code" value={form.site_code} field="site_code" onChange={onChange} />
              </div>
            </div>

            {/* Line Items */}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
                <span>📋</span> Line Items
              </h4>
              <EditableLineItems items={lineItems} onChange={onChange} />
            </div>

            {/* Amount Breakdown */}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
                <span>💹</span> Amount Breakdown
              </h4>
              <div className="grid gap-3 sm:grid-cols-2">
                <EditableField label="Subtotal" value={form.subtotal} field="subtotal" onChange={onChange} />
                <EditableField label="VAT Rate %" value={form.vat_rate} field="vat_rate" onChange={onChange} />
                <EditableField label="VAT Amount" value={form.vat_amount} field="vat_amount" onChange={onChange} />
                <EditableField label="Total Amount" value={form.total_amount} field="total_amount" onChange={onChange} />
              </div>
            </div>

            {/* Payment Details */}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
                <span>💳</span> Payment Details
              </h4>
              <div className="grid gap-3 sm:grid-cols-2">
                <EditableField label="Payment Method" value={form.payment_method} field="payment_method" onChange={onChange} />
                <EditableField label="Plate / Vehicle" value={form.plate_number} field="plate_number" onChange={onChange} />
                <EditableField label="Pump No" value={form.pump_no} field="pump_no" onChange={onChange} />
              </div>
            </div>

            {/* Confidence & Extraction */}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
                <span>🎯</span> Confidence & Extraction
              </h4>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">Overall Confidence</label>
                  <ConfidenceBadge score={form.confidence_score} />
                </div>
              </div>
              {form.validation_notes && (
                <div className="mt-3">
                  <EditableField label="Validation Notes" value={form.validation_notes} field="validation_notes" onChange={onChange} multiline />
                </div>
              )}
            </div>

            {/* Raw OCR text toggle */}
            {expense.raw_text && (
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <button type="button" onClick={() => setShowRaw((v) => !v)}
                  className="text-sm font-medium text-emerald-700 hover:text-emerald-800">
                  {showRaw ? 'Hide' : 'Show'} full OCR text
                </button>
                {showRaw && (
                  <pre className="mt-2 max-h-64 overflow-auto rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 whitespace-pre-wrap break-words">
                    {expense.raw_text}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function CashbillExpense() {
  const [expenses, setExpenses] = useState([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState({ text: '', type: 'info' })
  const [error, setError] = useState(null)
  const [verifyExpense, setVerifyExpense] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getExpenseList()
      if (res.success && Array.isArray(res.expenses)) {
        setExpenses(res.expenses)
      } else {
        setExpenses([])
      }
    } catch (e) {
      setError(e.message)
      setExpenses([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const showMsg = (text, type = 'success') => {
    setMessage({ text, type })
    setTimeout(() => setMessage({ text: '', type: '' }), 4000)
  }

  const onDelete = async (expenseId) => {
    if (!confirm('Delete this expense record?')) return
    try {
      await deleteExpense(expenseId)
      showMsg('Expense deleted')
      load()
      setVerifyExpense(null)
    } catch (e) {
      showMsg(e.message, 'error')
    }
  }

  const cols = [
    'Extracted At', 'Document Name', 'Document Type', 'Vendor Name', 'Receipt No', 'Date', 'Time',
    'Total', 'VAT', 'Currency', 'Expense Type', 'Confidence', 'Verify', 'Delete',
  ]

  return (
    <div className="flex min-h-screen flex-col bg-[#1e3a5f]">
      {verifyExpense && (
        <VerificationPanel
          expense={verifyExpense}
          onClose={() => setVerifyExpense(null)}
          onSaved={() => load()}
        />
      )}
      <header className="flex-shrink-0 border-b border-slate-600 bg-slate-800/90 px-4 py-3 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link to="/cashbill-expense" className="rounded-lg border border-slate-500 bg-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:bg-slate-600">
              ← Back
            </Link>
            <div>
              <h1 className="text-xl font-bold text-white">Expense Table</h1>
              <p className="text-sm text-slate-400">AI powered cash bill to expense</p>
            </div>
          </div>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-auto px-4 py-6 sm:px-6 lg:px-8">
        {message.text && (
          <div className={`mb-4 rounded-lg border p-3 text-sm ${message.type === 'success' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-800'}`}>
            {message.text}
          </div>
        )}
        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

        <div className="rounded-xl border border-slate-600 bg-white shadow-sm">
          <h2 className="border-b border-slate-200 bg-slate-50 px-4 py-3 text-lg font-semibold text-slate-800">
            Expense table
          </h2>
          {loading ? (
            <div className="flex justify-center py-16">
              <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-300 border-t-emerald-600" />
            </div>
          ) : expenses.length === 0 ? (
            <div className="py-16 text-center text-slate-500">No expenses yet. Upload a cash bill or receipt above.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-gradient-to-r from-emerald-600 to-emerald-700 text-left text-xs font-semibold uppercase tracking-wider text-white">
                    {cols.map((c) => <th key={c} className="whitespace-nowrap px-3 py-2">{c}</th>)}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {expenses.map((row) => (
                    <tr key={row.expense_id || row.document_name} className="hover:bg-slate-50/50">
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700">{formatOmanTimestamp(row.extracted_at)}</td>
                      <td className="px-3 py-2 text-slate-700 break-words" title={row.document_name}>{row.document_name || '-'}</td>
                      <td className="px-3 py-2 text-slate-600 break-words" title={row.document_type}>{row.document_type || '-'}</td>
                      <td className="px-3 py-2 text-slate-700 break-words" title={row.vendor}>{row.vendor || '-'}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700">{row.receipt_no || row.invoice_no || '-'}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700">{formatDate(row.receipt_date) !== '-' ? formatDate(row.receipt_date) : '-'}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700">{row.receipt_time || '-'}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700">{formatAmount(row.total_amount ?? row.amount, row.currency)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700">{formatAmount(row.vat_amount ?? row.tax_amount, '')}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700">{row.currency || '-'}</td>
                      <td className="px-3 py-2 text-slate-600 break-words" title={row.expense_type}>{row.expense_type || '-'}</td>
                      <td className="whitespace-nowrap px-3 py-2"><ConfidenceBadge score={row.confidence_score} /></td>
                      <td className="whitespace-nowrap px-3 py-2">
                        <button type="button" onClick={() => setVerifyExpense(row)}
                          className="rounded border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100">
                          View all
                        </button>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2">
                        <button type="button" onClick={() => onDelete(row.expense_id)}
                          className="rounded border border-red-200 bg-red-50 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100">
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
      <ExpenseChatbot />
    </div>
  )
}
