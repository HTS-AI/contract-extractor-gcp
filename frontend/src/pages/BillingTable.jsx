import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { ResizableTh } from '../components/ResizableTable'
import { getBilling, updateBilling } from '../api/client'

function formatNum(n) {
  if (typeof n !== 'number' || isNaN(n)) return '0.00'
  return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const STATUS_OPTIONS = [
  { value: 'draft', label: 'Draft', cls: 'border-slate-200 bg-slate-50 text-slate-800' },
  { value: 'approved', label: 'Approved', cls: 'border-emerald-200 bg-emerald-50 text-emerald-800' },
  { value: 'submitted', label: 'Submitted', cls: 'border-blue-200 bg-blue-50 text-blue-800' },
  { value: 'rejected', label: 'Rejected', cls: 'border-red-200 bg-red-50 text-red-800' },
]

function statusCls(val) {
  const opt = STATUS_OPTIONS.find((o) => o.value === val)
  return opt ? opt.cls : STATUS_OPTIONS[0].cls
}

const COLS = [
  { label: 'Billing Date', align: 'left' },
  { label: 'Invoice #', align: 'left' },
  { label: 'Vendor', align: 'left' },
  { label: 'PO Number', align: 'left' },
  { label: 'Description', align: 'left' },
  { label: 'Invoice Amt', align: 'right' },
  { label: 'Amt Received', align: 'right' },
  { label: 'Tax %', align: 'right' },
  { label: 'Tax Amt', align: 'right' },
  { label: 'Total Payable', align: 'right' },
  { label: 'Currency', align: 'left' },
  { label: 'Due Date', align: 'left' },
  { label: 'Payment Terms', align: 'left' },
  { label: 'Status', align: 'left' },
  { label: 'Remarks', align: 'left' },
]

export default function BillingTable() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [updatingId, setUpdatingId] = useState(null)
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getBilling()
      if (data.success && Array.isArray(data.rows)) {
        setRows(data.rows)
      } else {
        setRows([])
      }
    } catch (e) {
      setError(e.message)
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const update = async (extractionId, field, value) => {
    setUpdatingId(extractionId)
    try {
      await updateBilling(extractionId, { [field]: value })
      await load()
      if (field === 'billing_status' && value === 'approved') {
        setMessage('Billing approved - amount received will reflect in Payment Table')
        setTimeout(() => setMessage(''), 4000)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <Layout>
      <div className="flex min-h-full flex-col bg-[#1e3a5f]">
        <header className="border-b border-slate-700/50 bg-white/95 shadow-sm">
          <div className="px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h1 className="text-xl font-semibold text-slate-800">Billing Table</h1>
                <p className="text-sm text-slate-500">Manage billing amounts for matched invoices. Approved billings flow to Payment Table.</p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={load}
                  disabled={loading}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:opacity-60"
                >
                  Refresh
                </button>
                <Link
                  to="/payment-table"
                  className="rounded-lg bg-gradient-to-r from-emerald-600 to-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:from-emerald-700 hover:to-emerald-800"
                >
                  Payment Table
                </Link>
                <Link
                  to="/"
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Back to app
                </Link>
              </div>
            </div>
          </div>
        </header>

        <main className="px-4 py-6 sm:px-6 lg:px-8">
          {message && (
            <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              {message}
            </div>
          )}
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              {error}
            </div>
          )}

          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
              </div>
            ) : rows.length === 0 ? (
              <div className="py-16 text-center text-slate-500">No matched invoices to bill. Extract and match invoices first.</div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200 bg-gradient-to-r from-indigo-600 to-indigo-700 text-xs font-semibold uppercase tracking-wider text-white">
                    {COLS.map((c) => (
                      <ResizableTh key={c.label} className={`px-4 py-3 whitespace-nowrap text-${c.align}`}>
                        {c.label}
                      </ResizableTh>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rows.map((r) => {
                    const disabled = updatingId === r.extraction_id
                    return (
                      <tr key={r.extraction_id} className="hover:bg-slate-50/50">
                        <td className="whitespace-nowrap px-4 py-3">
                          <input
                            type="date"
                            defaultValue={r.billing_date || ''}
                            onBlur={(e) => update(r.extraction_id, 'billing_date', e.target.value)}
                            disabled={disabled}
                            className="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-800 disabled:opacity-60"
                          />
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-slate-800">
                          {r.invoice_number || '–'}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-700">{r.vendor || '–'}</td>
                        <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-700">{r.po_number || '–'}</td>
                        <td className="px-4 py-3 text-sm text-slate-700" title={r.description}>{r.description || '–'}</td>
                        <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-slate-600">
                          {formatNum(r.invoice_amount)}
                        </td>
                        {/* Amt Received - EDITABLE */}
                        <td className="whitespace-nowrap px-4 py-3 text-right">
                          <input
                            type="number"
                            min={0}
                            step={0.01}
                            defaultValue={r.amt_received ?? 0}
                            onBlur={(e) => update(r.extraction_id, 'amt_received', e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur() }}
                            disabled={disabled}
                            className="w-28 rounded-md border border-slate-300 py-1.5 pr-2 text-right text-sm tabular-nums text-slate-800 disabled:opacity-60"
                          />
                        </td>
                        {/* Tax % - read-only from invoice */}
                        <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-slate-600">
                          {r.tax_percent > 0 ? `${r.tax_percent}%` : '–'}
                        </td>
                        {/* Tax Amount - auto-calculated, read-only */}
                        <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-slate-600">
                          {formatNum(r.tax_amount)}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums font-semibold text-slate-800">
                          {formatNum(r.total_payable)}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-700">{r.currency || '–'}</td>
                        <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-700">{r.due_date || '–'}</td>
                        <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-700">{r.payment_terms || '–'}</td>
                        {/* Billing Status - EDITABLE dropdown */}
                        <td className="px-4 py-3">
                          <select
                            value={r.billing_status || 'draft'}
                            onChange={(e) => update(r.extraction_id, 'billing_status', e.target.value)}
                            disabled={disabled}
                            className={`rounded-lg border px-3 py-1.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60 ${statusCls(r.billing_status)}`}
                          >
                            {STATUS_OPTIONS.map((opt) => (
                              <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                          </select>
                        </td>
                        {/* Remarks - EDITABLE */}
                        <td className="px-4 py-3">
                          <input
                            type="text"
                            defaultValue={r.remarks || ''}
                            placeholder="Add note..."
                            onBlur={(e) => update(r.extraction_id, 'remarks', e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur() }}
                            disabled={disabled}
                            className="w-36 rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-800 placeholder:text-slate-400 disabled:opacity-60"
                          />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-slate-200 bg-indigo-50/60 font-semibold">
                    <td colSpan={5} className="px-4 py-3 text-sm text-slate-700">Totals</td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-slate-600">
                      {formatNum(rows.reduce((s, r) => s + (r.invoice_amount || 0), 0))}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-slate-800">
                      {formatNum(rows.reduce((s, r) => s + (r.amt_received || 0), 0))}
                    </td>
                    <td className="px-4 py-3" />
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-slate-800">
                      {formatNum(rows.reduce((s, r) => s + (r.tax_amount || 0), 0))}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums font-bold text-slate-800">
                      {formatNum(rows.reduce((s, r) => s + (r.total_payable || 0), 0))}
                    </td>
                    <td colSpan={5} />
                  </tr>
                </tfoot>
              </table>
            )}
          </div>

          <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            <strong>How it works:</strong> Enter the <strong>Amount Received</strong> (full or partial). Tax is auto-calculated from the invoice's original tax rate.
            Change Status to <strong>Approved</strong> to reflect the amount in the <Link to="/payment-table" className="font-semibold underline">Payment Table</Link>.
            Draft billings do not affect payment tracking.
          </div>
        </main>
      </div>
    </Layout>
  )
}
