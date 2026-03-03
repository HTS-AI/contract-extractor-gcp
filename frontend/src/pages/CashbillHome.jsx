import React, { useState, useCallback, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { expenseUpload, getExpenseList, getExpenseDashboard, deleteExpense } from '../api/client'
import ExpenseChatbot from '../components/ExpenseChatbot'

function formatAmount(amount, currency) {
  if (amount == null || amount === '' || amount === undefined) return '-'
  const n = parseFloat(String(amount).replace(/,/g, ''))
  if (isNaN(n)) return amount
  const formatted = n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 3 })
  return currency ? `${formatted} ${currency}` : formatted
}

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

function InfoCard({ title, icon, children, className = '' }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm ${className}`}>
      <div className="mb-3 flex items-center gap-2 border-b border-slate-100 pb-2">
        <span>{icon}</span>
        <h3 className="text-base font-semibold text-slate-800">{title}</h3>
      </div>
      {children}
    </div>
  )
}

function InfoGrid({ children }) {
  return <div className="grid gap-3 sm:grid-cols-2">{children}</div>
}

function InfoItem({ label, value, mono }) {
  if (value == null || value === '') return null
  return (
    <div>
      <label className="mb-0.5 block text-xs font-medium uppercase text-slate-500">{label}</label>
      <span className={mono ? 'font-mono text-sm text-slate-800' : 'text-sm text-slate-800'}>{value}</span>
    </div>
  )
}

function ConfidenceBadge({ score }) {
  if (score == null) return <span className="text-slate-400">-</span>
  const pct = typeof score === 'number' ? (score <= 1 ? score * 100 : score) : parseFloat(score) || 0
  const color = pct >= 80 ? 'bg-emerald-100 text-emerald-800' : pct >= 50 ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>{pct.toFixed(0)}%</span>
}

function ExpenseDetailView({ expense }) {
  if (!expense) return <p className="text-slate-500">Upload a cash bill and click Extract, or select a document below.</p>
  const r = expense
  const lineItems = Array.isArray(r.line_items) ? r.line_items : []

  return (
    <div className="space-y-4">
      <InfoCard title="Receipt / Bill Information" icon="🧾">
        <InfoGrid>
          <InfoItem label="Document Type" value={r.document_type} />
          <InfoItem label="Expense Type" value={r.expense_type} />
          <InfoItem label="Receipt No" value={r.receipt_no} />
          <InfoItem label="Invoice No" value={r.invoice_no} />
          <InfoItem label="Receipt Date" value={r.receipt_date} />
          <InfoItem label="Receipt Time" value={r.receipt_time} />
          <InfoItem label="Currency" value={r.currency} />
        </InfoGrid>
      </InfoCard>

      <InfoCard title="Vendor Details" icon="🏢">
        <InfoGrid>
          <InfoItem label="Vendor / Merchant" value={r.vendor} />
          <div className="sm:col-span-2">
            <InfoItem label="Address" value={r.vendor_address} />
          </div>
          <InfoItem label="VAT Number" value={r.site_vat_no} mono />
          <InfoItem label="C.R. No" value={r.cr_no} mono />
          <InfoItem label="Customer" value={r.customer_name} />
          <InfoItem label="Site Name" value={r.site_name} />
          <InfoItem label="Site Code" value={r.site_code} />
        </InfoGrid>
      </InfoCard>

      {lineItems.length > 0 && (
        <InfoCard title="Line Items" icon="📋">
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-100 text-left text-xs font-semibold uppercase text-slate-600">
                  <th className="px-3 py-2">#</th>
                  <th className="px-3 py-2">Description</th>
                  <th className="px-3 py-2 text-right">Qty</th>
                  <th className="px-3 py-2">Unit</th>
                  <th className="px-3 py-2 text-right">Unit Price</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                  <th className="px-3 py-2 text-right">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {lineItems.map((item, i) => (
                  <tr key={i}>
                    <td className="px-3 py-2 text-slate-700">{item.sl_no ?? i + 1}</td>
                    <td className="px-3 py-2 text-slate-800">{item.description || '-'}</td>
                    <td className="px-3 py-2 text-right text-slate-700">{item.qty ?? '-'}</td>
                    <td className="px-3 py-2 text-slate-600">{item.unit || ''}</td>
                    <td className="px-3 py-2 text-right text-slate-700">{item.unit_price != null ? formatAmount(item.unit_price, '') : '-'}</td>
                    <td className="px-3 py-2 text-right font-medium text-slate-800">{item.amount != null ? formatAmount(item.amount, '') : '-'}</td>
                    <td className="px-3 py-2 text-right">
                      {item.confidence != null ? <ConfidenceBadge score={item.confidence} /> : <span className="text-slate-400">-</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </InfoCard>
      )}

      <InfoCard title="Amount Breakdown" icon="💹">
        <InfoGrid>
          <InfoItem label="Subtotal" value={r.subtotal != null ? formatAmount(r.subtotal, r.currency) : null} />
          <InfoItem label="VAT Rate" value={r.vat_rate != null ? `${r.vat_rate}%` : null} />
          <InfoItem label="VAT Amount" value={r.vat_amount != null ? formatAmount(r.vat_amount, r.currency) : null} />
          <div>
            <label className="mb-0.5 block text-xs font-medium uppercase text-slate-500">Total Amount</label>
            <span className="text-lg font-bold text-slate-900">
              {formatAmount(r.total_amount ?? r.amount, r.currency)}
            </span>
          </div>
        </InfoGrid>
      </InfoCard>

      <InfoCard title="Payment Details" icon="💳">
        <InfoGrid>
          <InfoItem label="Payment Method" value={r.payment_method} />
          <InfoItem label="Plate / Vehicle" value={r.plate_number} />
          <InfoItem label="Pump No" value={r.pump_no} />
        </InfoGrid>
      </InfoCard>

      {(r.confidence_score != null || r.validation_notes) && (
        <InfoCard title="Confidence & Validation" icon="🎯">
          <InfoGrid>
            {r.confidence_score != null && (
              <div>
                <label className="mb-0.5 block text-xs font-medium uppercase text-slate-500">Overall Confidence</label>
                <ConfidenceBadge score={r.confidence_score} />
              </div>
            )}
            {r.validation_notes && (
              <div className="sm:col-span-2">
                <label className="mb-0.5 block text-xs font-medium uppercase text-slate-500">Validation Notes</label>
                <p className="whitespace-pre-wrap text-sm text-slate-700">{r.validation_notes}</p>
              </div>
            )}
          </InfoGrid>
        </InfoCard>
      )}

      {r.raw_text && (
        <RawTextSection text={r.raw_text} />
      )}
    </div>
  )
}

function RawTextSection({ text }) {
  const [show, setShow] = useState(false)
  return (
    <InfoCard title="Full OCR Text" icon="📝">
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        className="text-sm font-medium text-emerald-700 hover:text-emerald-800"
      >
        {show ? 'Hide' : 'Show'} full extracted text
      </button>
      {show && (
        <pre className="mt-2 max-h-64 overflow-auto rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 whitespace-pre-wrap break-words">
          {text}
        </pre>
      )}
    </InfoCard>
  )
}

export default function CashbillHome() {
  const [file, setFile] = useState(null)
  const [statusMsg, setStatusMsg] = useState('')
  const [statusType, setStatusType] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [expenses, setExpenses] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [selectedExpense, setSelectedExpense] = useState(null)
  const [dashboard, setDashboard] = useState({ total_bills: 0, total_amount: 0, total_vat: 0, unique_vendors: 0, currencies: [] })
  const fileInputRef = useRef(null)

  const showStatus = useCallback((msg, type = 'info') => {
    setStatusMsg(msg)
    setStatusType(type)
    if (msg) setTimeout(() => { setStatusMsg(''); setStatusType('') }, 5000)
  }, [])

  const loadDashboard = useCallback(async () => {
    try {
      const data = await getExpenseDashboard()
      setDashboard({
        total_bills: data.total_bills ?? 0,
        total_amount: data.total_amount ?? 0,
        total_vat: data.total_vat ?? 0,
        unique_vendors: data.unique_vendors ?? 0,
        currencies: data.currencies ?? [],
      })
    } catch (e) {
      console.error(e)
    }
  }, [])

  const loadList = useCallback(async () => {
    try {
      const res = await getExpenseList()
      if (res.success && Array.isArray(res.expenses)) {
        setExpenses(res.expenses)
        if (!selectedId && res.expenses.length > 0) setSelectedId(res.expenses[0].expense_id)
      }
    } catch (e) {
      console.error(e)
    }
  }, [selectedId])

  useEffect(() => {
    loadDashboard()
    loadList()
  }, [loadDashboard, loadList])

  useEffect(() => {
    if (selectedId) {
      const record = expenses.find((r) => r.expense_id === selectedId)
      setSelectedExpense(record || null)
    } else {
      setSelectedExpense(null)
    }
  }, [selectedId, expenses])

  const handleExtract = async () => {
    if (!file) {
      showStatus('Please select a file first', 'error')
      return
    }
    setExtracting(true)
    setStatusMsg('Uploading & extracting via GCP Vision + multimodal LLM ...')
    try {
      const res = await expenseUpload(file)
      if (res.success && res.expense) {
        showStatus(`Extracted: ${res.expense.vendor || res.expense.document_name || 'receipt'}`, 'success')
        loadDashboard()
        await loadList()
        setSelectedId(res.expense.expense_id || '')
      } else {
        showStatus('Extraction failed', 'error')
      }
    } catch (e) {
      showStatus(e.message || 'Extraction failed', 'error')
    } finally {
      setExtracting(false)
    }
  }

  const handleDelete = async (expenseId) => {
    if (!confirm('Delete this expense record?')) return
    try {
      await deleteExpense(expenseId)
      showStatus('Expense deleted')
      if (selectedId === expenseId) setSelectedId('')
      loadDashboard()
      loadList()
    } catch (e) {
      showStatus(e.message, 'error')
    }
  }

  const currencyLabel = dashboard.currencies.length > 0 ? dashboard.currencies.join(', ') : 'OMR'

  return (
    <div className="flex min-h-screen flex-col bg-[#1e3a5f]">
      <header className="flex-shrink-0 border-b border-slate-600 bg-slate-800/90 px-4 py-3 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link to="/main" className="rounded-lg border border-slate-500 bg-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:bg-slate-600">
              ← Main
            </Link>
            <div>
              <h1 className="text-xl font-bold text-white">Expense Details</h1>
              <p className="text-sm text-slate-400">AI powered cash bill to expense</p>
            </div>
          </div>
          <nav className="flex items-center gap-2">
            <Link to="/expense-table" className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700">
              Expense Table
            </Link>
          </nav>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-auto px-4 py-6 sm:px-6 lg:px-8">
        <div className="grid gap-6 lg:grid-cols-3">
          <section className="space-y-4 lg:col-span-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold text-slate-800">📋 Extracted Information</h2>
              <ExpenseDetailView expense={selectedExpense} />
            </div>
          </section>

          <section className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold text-slate-800">Upload Cash bill</h2>
              {expenses.length > 0 && (
                <div className="mb-4">
                  <label className="mb-1 block text-sm font-medium text-slate-600">Load previous extraction</label>
                  <select
                    value={selectedId}
                    onChange={(e) => setSelectedId(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
                  >
                    <option value="">Select...</option>
                    {expenses.map((ex) => (
                      <option key={ex.expense_id} value={ex.expense_id}>
                        {ex.document_name || ex.expense_id} – {ex.vendor || ex.document_type || ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.gif,.bmp,.webp"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  {file ? file.name : 'Choose file'}
                </button>
                <button
                  type="button"
                  disabled={!file || extracting}
                  onClick={handleExtract}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  {extracting ? 'Extracting...' : 'Extract'}
                </button>
              </div>
              {statusMsg && (
                <p className={`mt-2 text-sm ${statusType === 'error' ? 'text-red-600' : statusType === 'success' ? 'text-emerald-600' : 'text-slate-600'}`}>
                  {statusMsg}
                </p>
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold text-slate-800">📊 Dashboard</h2>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-2">
                <div className="flex min-h-[75px] flex-col items-center justify-center rounded-lg border border-slate-200 bg-slate-50/80 px-2 py-2.5 text-center">
                  <div className="mb-1 text-2xl">🧾</div>
                  <div className="text-xl font-bold leading-tight text-slate-800">{dashboard.total_bills}</div>
                  <div className="text-xs font-medium text-slate-600">Total Bills</div>
                </div>
                <div className="flex min-h-[75px] flex-col items-center justify-center rounded-lg border border-slate-200 bg-slate-50/80 px-2 py-2.5 text-center">
                  <div className="mb-1 text-2xl">🏢</div>
                  <div className="text-xl font-bold leading-tight text-slate-800">{dashboard.unique_vendors}</div>
                  <div className="text-xs font-medium text-slate-600">Vendors</div>
                </div>
                <div className="flex min-h-[75px] flex-col items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50/80 px-2 py-2.5 text-center">
                  <div className="mb-1 text-2xl">💰</div>
                  <div className="text-lg font-bold leading-tight text-emerald-800">{formatAmount(dashboard.total_amount, currencyLabel)}</div>
                  <div className="text-xs font-medium text-slate-600">Total Amount</div>
                </div>
                <div className="flex min-h-[75px] flex-col items-center justify-center rounded-lg border border-amber-200 bg-amber-50/80 px-2 py-2.5 text-center">
                  <div className="mb-1 text-2xl">🏷️</div>
                  <div className="text-lg font-bold leading-tight text-amber-800">{formatAmount(dashboard.total_vat, currencyLabel)}</div>
                  <div className="text-xs font-medium text-slate-600">Total VAT</div>
                </div>
              </div>
            </div>

            {selectedExpense && (
              <button
                type="button"
                onClick={() => handleDelete(selectedExpense.expense_id)}
                className="w-full rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
              >
                Delete this expense
              </button>
            )}
          </section>
        </div>
      </main>
      <ExpenseChatbot />
    </div>
  )
}
