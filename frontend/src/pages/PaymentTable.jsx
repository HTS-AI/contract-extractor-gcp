import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { ResizableTh } from '../components/ResizableTable'
import { getPaymentStatus } from '../api/client'

function formatNum(n) {
  if (typeof n !== 'number' || isNaN(n)) return '0.00'
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatUploadedAt(isoStr) {
  if (!isoStr || typeof isoStr !== 'string') return '–'
  try {
    const d = new Date(isoStr)
    if (isNaN(d.getTime())) return isoStr
    return d.toLocaleString()
  } catch {
    return isoStr
  }
}

function statusLabel(val) {
  if (val === 'paid') return 'Full paid'
  if (val === 'partial_payment') return 'Partially paid'
  return 'Not paid'
}

function statusCls(val) {
  if (val === 'paid') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (val === 'partial_payment') return 'border-amber-200 bg-amber-50 text-amber-800'
  return 'border-slate-200 bg-slate-50 text-slate-800'
}

function PaymentTable() {
  const [rows, setRows] = useState([])
  const [totals, setTotals] = useState({ billed_amount: 0, amount_received: 0, balance_due: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [dueFrom, setDueFrom] = useState('')
  const [dueTo, setDueTo] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getPaymentStatus()
      if (!data.success || !Array.isArray(data.rows)) {
        setRows([])
        setTotals({ billed_amount: 0, amount_received: 0, balance_due: 0 })
        return
      }
      let filtered = data.rows
      if (dueFrom || dueTo) {
        filtered = filtered.filter((r) => {
          const d = r.due_date || ''
          if (!d) return true
          if (dueFrom && d < dueFrom) return false
          if (dueTo && d > dueTo) return false
          return true
        })
      }
      setRows(filtered)
      const billed = filtered.reduce((s, r) => s + (r.billed_amount || 0), 0)
      const rec = filtered.reduce((s, r) => s + (r.amount_received || 0), 0)
      const due = filtered.reduce((s, r) => s + (r.balance_due || 0), 0)
      setTotals({ billed_amount: billed, amount_received: rec, balance_due: due })
    } catch (e) {
      setError(e.message)
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [dueFrom, dueTo])

  useEffect(() => {
    load()
  }, [load])


  const payCols = [
    { label: 'Invoice uploaded', align: 'left' },
    { label: 'Account type', align: 'left' },
    { label: 'PO number', align: 'left' },
    { label: 'Invoice #', align: 'left' },
    { label: 'Inv date', align: 'left' },
    { label: 'Due date', align: 'left' },
    { label: 'Billed amount', align: 'right' },
    { label: 'Amt disbursed', align: 'right' },
    { label: 'Bal due', align: 'right' },
    { label: 'Payment status', align: 'left' },
  ]

  return (
    <Layout>
    <div className="flex min-h-full flex-col bg-[#1e3a5f]">
      <header className="border-b border-slate-700/50 bg-white/95 shadow-sm">
        <div className="mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h1 className="text-xl font-semibold text-slate-800">Invoice Details</h1>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <span>Due date:</span>
                <input
                  type="date"
                  value={dueFrom}
                  onChange={(e) => setDueFrom(e.target.value)}
                  className="rounded-md border border-slate-300 px-2 py-1.5 text-slate-800"
                />
                <span>–</span>
                <input
                  type="date"
                  value={dueTo}
                  onChange={(e) => setDueTo(e.target.value)}
                  className="rounded-md border border-slate-300 px-2 py-1.5 text-slate-800"
                />
              </div>
              <button
                onClick={load}
                disabled={loading}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:opacity-60"
              >
                Refresh
              </button>
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
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        )}

        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-emerald-600" />
            </div>
          ) : rows.length === 0 ? (
            <div className="py-16 text-center text-slate-500">No invoices to show</div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/80">
                  {payCols.map((c) => (
                    <ResizableTh
                      key={c.label}
                      className={`px-4 py-3 whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-slate-600 text-${c.align}`}
                    >
                      {c.label}
                    </ResizableTh>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r) => (
                  <tr key={r.extraction_id} className="hover:bg-slate-50/50">
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-700">{formatUploadedAt(r.uploaded_at)}</td>
                    <td className="px-4 py-3 text-sm text-slate-700">{r.account_type_desc || '–'}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-700">{r.po_number || '–'}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-slate-800">{r.invoice_number || r.file_name || '–'}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-700">{r.inv_date || '–'}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-700">{r.due_date || '–'}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-slate-700">
                      {formatNum(r.billed_amount)} {r.currency || ''}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-slate-700">
                      {formatNum(r.amount_received)} {r.currency || ''}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums font-medium text-slate-800">
                      {formatNum(r.balance_due)} {r.currency || ''}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block rounded-lg border px-3 py-1.5 text-sm font-medium ${statusCls(r.payment_status)}`}>
                        {statusLabel(r.payment_status)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-200 bg-amber-50/60 font-semibold">
                  <td colSpan={6} className="px-4 py-3 text-sm text-slate-700">Totals</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-slate-800">{formatNum(totals.billed_amount)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-slate-800">{formatNum(totals.amount_received)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-slate-800">{formatNum(totals.balance_due)}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      </main>
    </div>
    </Layout>
  )
}

export default PaymentTable
