import React, { useState, useCallback, useRef, useEffect } from 'react'
import Layout from '../components/Layout'
import ExtractionResults from '../components/ExtractionResults'
import FileManagerModal from '../components/FileManagerModal'
import {
  uploadFile,
  extract,
  getExtractionStatus,
  getExtraction,
  getExtractionsList,
  getDashboard
} from '../api/client'
import { useCurrentExtraction } from '../context/CurrentExtractionContext'

const STEP_MAP = {
  uploaded: { text: 'Upload completed', percent: 10 },
  extraction_started: { text: 'Extraction started', percent: 15 },
  parse_document: { text: 'Parsing document', percent: 30 },
  classify_document: { text: 'Classifying document', percent: 45 },
  extract_data: { text: 'Extracting data', percent: 60 },
  enhance_data: { text: 'Enhancing data', percent: 75 },
  calculate_risk: { text: 'Calculating risk', percent: 90 },
  finalize: { text: 'Finalizing', percent: 95 },
  completed: { text: 'Completed', percent: 100 }
} 

export default function Home() {
  const { setCurrentExtractionId } = useCurrentExtraction()
  const [file, setFile] = useState(null)
  const [statusMsg, setStatusMsg] = useState('')
  const [statusType, setStatusType] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [progress, setProgress] = useState({ text: '', percent: 0 })
  const [showProgress, setShowProgress] = useState(false)
  const [extractions, setExtractions] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [results, setResults] = useState(null)
  const [dashboard, setDashboard] = useState({ total_invoices: 0, total_pos: 0, total_grn: 0, matched_invoices: 0, unmatched_invoices: 0 })
  const [fileManagerOpen, setFileManagerOpen] = useState(false)
  const [poNotFoundDetails, setPoNotFoundDetails] = useState(null)
  const [poNotFoundNotifications, setPoNotFoundNotifications] = useState([])
  const [duplicateInvoiceDetails, setDuplicateInvoiceDetails] = useState(null)
  const pollRef = useRef(null)
  const fileInputRef = useRef(null)

  const showStatus = useCallback((msg, type = 'info') => {
    setStatusMsg(msg)
    setStatusType(type)
    if (msg) setTimeout(() => { setStatusMsg(''); setStatusType('') }, 5000)
  }, [])

  const loadDashboard = useCallback(async () => {
    try {
      const data = await getDashboard()
      setDashboard({
        total_invoices: data.total_invoices ?? 0,
        total_pos: data.total_pos ?? 0,
        total_grn: data.total_grn ?? 0,
        matched_invoices: data.matched_invoices ?? 0,
        unmatched_invoices: data.unmatched_invoices ?? 0
      })
    } catch (e) {
      console.error(e)
    }
  }, [])

  const loadList = useCallback(async () => {
    try {
      const data = await getExtractionsList()
      if (data.success && Array.isArray(data.extractions)) {
        setExtractions(data.extractions)
        if (!selectedId && data.extractions.length > 0) setSelectedId(data.extractions[0].extraction_id)
      }
    } catch (e) {
      console.error(e)
    }
  }, [selectedId])

  useEffect(() => {
    loadDashboard()
    loadList()
  }, [loadDashboard, loadList])

  const loadExtraction = useCallback(async (extractionId) => {
    if (!extractionId) {
      setResults(null)
      return
    }
    try {
      const data = await getExtraction(extractionId)
      if (data.success && data.results) {
        setResults(data.results)
        showStatus(`Loaded: ${data.file_name || ''}`, 'success')
      }
    } catch (e) {
      showStatus('Failed to load: ' + e.message, 'error')
      setResults(null)
    }
  }, [showStatus])

  useEffect(() => {
    if (selectedId) loadExtraction(selectedId)
    else setResults(null)
    setCurrentExtractionId(selectedId || null)
  }, [selectedId, loadExtraction, setCurrentExtractionId])

  const startPolling = useCallback((extractionId) => {
    let progressShown = false
    const interval = setInterval(async () => {
      try {
        const statusData = await getExtractionStatus(extractionId)
        if (statusData.status === 'not_found') return
        if (statusData.skip_progress) {
          clearInterval(interval)
          pollRef.current = null
          if (statusData.from_cache) showStatus('Data retrieved from cache', 'success')
          return
        }
        if (!progressShown) {
          setShowProgress(true)
          progressShown = true
        }
        const step = STEP_MAP[statusData.current_step] || {
          text: statusData.step_description || 'Processing...',
          percent: statusData.progress_percent || 0
        }
        setProgress({ text: step.text, percent: step.percent })
        if (statusData.is_complete) {
          clearInterval(interval)
          pollRef.current = null
          setTimeout(() => setShowProgress(false), 2000)
        }
      } catch (e) {
        console.error(e)
      }
    }, 500)
    pollRef.current = interval
    return interval
  }, [showStatus])

  const handleExtract = async () => {
    if (!file) {
      showStatus('Please select a file first', 'error')
      return
    }
    setExtracting(true)
    setStatusMsg('Uploading...')
    try {
      const uploadData = await uploadFile(file)
      const extractionId = uploadData.extraction_id
      if (!extractionId) throw new Error('No extraction ID')
      startPolling(extractionId)
      setStatusMsg('Extracting...')
      const extractData = await extract(extractionId)
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      setShowProgress(false)
      if (extractData.status === 'duplicate_invoice' && extractData.warning) {
        setDuplicateInvoiceDetails(extractData.details || { invoice_id: 'Unknown' })
        showStatus(`Duplicate invoice: ${extractData.details?.invoice_id || 'Unknown'}`, 'error')
        setExtracting(false)
        return
      }
      if (extractData.status === 'po_not_found' && extractData.warning) {
        const d = extractData.details || { invoice_file: 'Unknown' }
        d.failure_reason = extractData.failure_reason || 'po_not_found'
        setPoNotFoundDetails(d)
        setPoNotFoundNotifications(extractData.notifications || [])
        showStatus('Invoice matching failed: invoice not saved to data table', 'error')
        if (extractData.results) setResults(extractData.results)
      } else if (extractData.results) {
        setResults(extractData.results)
        setSelectedId(extractionId)
        showStatus('Extraction completed', 'success')
      }
      loadDashboard()
      loadList()
    } catch (e) {
      showStatus(e.message || 'Extraction failed', 'error')
    } finally {
      setExtracting(false)
    }
  }

  return (
    <Layout>
      <div className="grid gap-6 lg:grid-cols-3">
        <section className="lg:col-span-2 space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-slate-800">📋 Extracted Information</h2>
            {!results ? (
              <p className="text-slate-500">Upload a file and click Extract, or select a document below.</p>
            ) : (
              <ExtractionResults results={results} />
            )}
          </div>
        </section>

        <section className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-slate-800">Upload Invoice</h2>
            {extractions.length > 0 && (
              <div className="mb-4">
                <label className="mb-1 block text-sm font-medium text-slate-600">Load previous extraction</label>
                <select
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                >
                  <option value="">Select...</option>
                  {extractions.map((ex) => (
                    <option key={ex.extraction_id} value={ex.extraction_id}>
                      {ex.file_name || ex.extraction_id} – {ex.document_type || ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc"
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
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {extracting ? 'Processing...' : 'Extract'}
              </button>
            </div>
            {showProgress && (
              <div className="mt-3">
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full bg-indigo-600 transition-all duration-300"
                    style={{ width: `${progress.percent}%` }}
                  />
                </div>
                <p className="mt-1 text-sm text-slate-600">{progress.text}</p>
              </div>
            )}
            {statusMsg && (
              <p className={`mt-2 text-sm ${statusType === 'error' ? 'text-red-600' : statusType === 'success' ? 'text-emerald-600' : 'text-slate-600'}`}>
                {statusMsg}
              </p>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-slate-800">📊 Dashboard</h2>
            <div className="dashboard-grid grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <div className="stat-card flex min-h-[75px] flex-col items-center justify-center rounded-lg border border-slate-200 bg-slate-50/80 px-2 py-2.5 text-center">
                <div className="stat-icon mb-1 text-2xl">🧾</div>
                <div className="stat-value text-xl font-bold leading-tight text-slate-800">{dashboard.total_invoices}</div>
                <div className="stat-label text-xs font-medium text-slate-600">Total Invoices</div>
              </div>
              <div className="stat-card flex min-h-[75px] flex-col items-center justify-center rounded-lg border border-slate-200 bg-slate-50/80 px-2 py-2.5 text-center">
                <div className="stat-icon mb-1 text-2xl">📋</div>
                <div className="stat-value text-xl font-bold leading-tight text-slate-800">{dashboard.total_pos}</div>
                <div className="stat-label text-xs font-medium text-slate-600">Total POs</div>
              </div>
              <div className="stat-card flex min-h-[75px] flex-col items-center justify-center rounded-lg border border-slate-200 bg-slate-50/80 px-2 py-2.5 text-center">
                <div className="stat-icon mb-1 text-2xl">📦</div>
                <div className="stat-value text-xl font-bold leading-tight text-slate-800">{dashboard.total_grn}</div>
                <div className="stat-label text-xs font-medium text-slate-600">Total GRN</div>
              </div>
              <div className="stat-card flex min-h-[75px] flex-col items-center justify-center rounded-lg border border-slate-200 bg-slate-50/80 px-2 py-2.5 text-center">
                <div className="stat-icon mb-1 text-2xl">✅</div>
                <div className="stat-value text-xl font-bold leading-tight text-slate-800">{dashboard.matched_invoices}</div>
                <div className="stat-label text-xs font-medium text-slate-600">Matched</div>
              </div>
              <div className="stat-card flex min-h-[75px] flex-col items-center justify-center rounded-lg border border-slate-200 bg-slate-50/80 px-2 py-2.5 text-center">
                <div className="stat-icon mb-1 text-2xl">⚠️</div>
                <div className="stat-value text-xl font-bold leading-tight text-slate-800">{dashboard.unmatched_invoices}</div>
                <div className="stat-label text-xs font-medium text-slate-600">Not Matched</div>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setFileManagerOpen(true)}
            className="w-full rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
          >
            🗂️ Manage Files
          </button>
        </section>
      </div>

      {fileManagerOpen && (
        <FileManagerModal onClose={() => setFileManagerOpen(false)} onRefresh={loadList} />
      )}

      {poNotFoundDetails != null && (
        <PONotFoundModal
          details={poNotFoundDetails}
          notifications={poNotFoundNotifications}
          onClose={() => { setPoNotFoundDetails(null); setPoNotFoundNotifications([]) }}
        />
      )}

      {duplicateInvoiceDetails != null && (
        <DuplicateInvoiceModal
          details={duplicateInvoiceDetails}
          onClose={() => setDuplicateInvoiceDetails(null)}
        />
      )}
    </Layout>
  )
}

function formatAmountCurrency(amount, currency) {
  if (amount == null || amount === '') return '-'
  const num = parseFloat(String(amount).replace(/,/g, ''))
  if (isNaN(num)) return amount
  const formatted = num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return currency ? `${formatted} ${currency}` : formatted
}

function PONotFoundModal({ details, notifications, onClose }) {
  const invoiceFile = details.invoice_file || 'Unknown'
  const vendor = details.vendor || 'Not found'
  const customer = details.customer || 'Not found'
  const amount = details.amount != null ? formatAmountCurrency(details.amount, details.currency || '') : 'Not found'
  const poNumber = details.po_number_in_invoice || ''
  const itemIssues = details.item_issues || []
  const notifs = notifications || []
  const reason = details.failure_reason || 'po_not_found'

  const headerConfig = {
    po_not_found: {
      icon: '🚫', title: 'Purchase Order Not Found',
      subtitle: 'No matching PO exists in the system. Invoice cannot enter Accounts Payable.',
      borderColor: 'border-red-200', bgColor: 'bg-red-50', titleColor: 'text-red-900',
      btnColor: 'bg-red-600 hover:bg-red-700',
      tip: 'Upload the corresponding Purchase Order first, then re-upload this invoice.',
    },
    vendor_mismatch: {
      icon: '🏢', title: 'Vendor / Supplier Mismatch',
      subtitle: 'The vendor on the invoice does not match the vendor on the PO.',
      borderColor: 'border-red-200', bgColor: 'bg-red-50', titleColor: 'text-red-900',
      btnColor: 'bg-red-600 hover:bg-red-700',
      tip: 'Verify that the invoice is from the same vendor listed on the PO. If the vendor changed, update the PO or contact the vendor.',
    },
    item_mismatch: {
      icon: '📦', title: 'Item / Quantity Mismatch',
      subtitle: 'Invoice line items or quantities do not match what was received (GRN) or ordered (PO).',
      borderColor: 'border-orange-200', bgColor: 'bg-orange-50', titleColor: 'text-orange-900',
      btnColor: 'bg-orange-600 hover:bg-orange-700',
      tip: 'Review the invoice quantities and items against the GRN/PO. Ensure the invoice only bills for items and quantities that were actually received or ordered.',
    },
    grn_not_found: {
      icon: '📋', title: 'GRN Not Uploaded',
      subtitle: 'No Goods Receipt Note found for this PO. Only a 2-way match (Invoice vs PO) was performed.',
      borderColor: 'border-amber-200', bgColor: 'bg-amber-50', titleColor: 'text-amber-900',
      btnColor: 'bg-amber-600 hover:bg-amber-700',
      tip: 'Upload the GRN for this PO to complete 3-way matching (PO + GRN + Invoice). Payment will be processed once all three documents match.',
    },
  }

  const hdr = headerConfig[reason] || headerConfig.po_not_found

  const typeStyles = {
    error:   { bg: 'bg-red-50',    border: 'border-red-300',   icon: '❌', text: 'text-red-800' },
    warning: { bg: 'bg-amber-50',  border: 'border-amber-300', icon: '⚠️', text: 'text-amber-800' },
    success: { bg: 'bg-emerald-50', border: 'border-emerald-300', icon: '✅', text: 'text-emerald-800' },
    info:    { bg: 'bg-blue-50',   border: 'border-blue-300',  icon: 'ℹ️', text: 'text-blue-800' },
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`border-b ${hdr.borderColor} ${hdr.bgColor} px-5 py-4`}>
          <div className="flex items-center gap-2">
            <span className="text-2xl">{hdr.icon}</span>
            <div>
              <h2 className={`text-lg font-bold uppercase tracking-wide ${hdr.titleColor}`}>
                {hdr.title}
              </h2>
              <p className="mt-0.5 text-xs text-slate-600">{hdr.subtitle}</p>
            </div>
          </div>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div className="text-slate-700">
            <p className="font-semibold">This invoice cannot be processed in Accounts Payable.</p>
            <p className="mt-1 text-sm">The invoice will not be saved to the data table until all matching requirements are met.</p>
          </div>
          <div>
            <h4 className="mb-2 font-semibold text-slate-800">Invoice details</h4>
            <ul className="list-inside list-disc space-y-1 text-sm text-slate-700">
              {poNumber ? <li><strong>PO number on invoice:</strong> {poNumber}</li> : null}
              <li><strong>Invoice file:</strong> {invoiceFile}</li>
              <li><strong>Vendor:</strong> {vendor}</li>
              <li><strong>Customer:</strong> {customer}</li>
              <li><strong>Amount:</strong> {amount}</li>
            </ul>
          </div>

          {notifs.length > 0 && (
            <div>
              <h4 className="mb-2 font-semibold text-slate-800">Matching Results</h4>
              <div className="space-y-2">
                {notifs.map((n, i) => {
                  const s = typeStyles[n.type] || typeStyles.info
                  return (
                    <div key={i} className={`rounded-lg border ${s.border} ${s.bg} px-4 py-2.5`}>
                      <div className={`flex items-center gap-1.5 text-sm font-semibold ${s.text}`}>
                        <span>{s.icon}</span> {n.title}
                      </div>
                      <p className="mt-0.5 whitespace-pre-wrap text-xs text-slate-700 leading-relaxed">{n.detail}</p>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {itemIssues.length > 0 && notifs.length === 0 && (
            <div>
              <h4 className="mb-2 font-semibold text-slate-800">Item / Quantity Issues</h4>
              <ul className="list-inside list-disc space-y-1 text-sm text-red-700">
                {itemIssues.map((issue, i) => <li key={i}>{issue}</li>)}
              </ul>
            </div>
          )}

          <div className={`rounded-lg border ${hdr.borderColor} ${hdr.bgColor} px-4 py-3 text-sm ${hdr.titleColor}`}>
            <strong>💡 What to do:</strong> {hdr.tip}
          </div>
        </div>
        <div className="border-t border-slate-200 px-5 py-3 text-right">
          <button
            type="button"
            onClick={onClose}
            className={`rounded-lg ${hdr.btnColor} px-4 py-2 text-sm font-medium text-white`}
          >
            OK
          </button>
        </div>
      </div>
    </div>
  )
}

function DuplicateInvoiceModal({ details, onClose }) {
  const invoiceId = details.invoice_id || 'Unknown'
  const existingDoc = details.existing_document || 'Unknown'
  const processedDate = details.processed_date
  const vendor = details.vendor || ''
  const amount = details.amount
  const currency = details.currency || ''
  const processedDateStr = processedDate
    ? (() => {
        try {
          return new Date(processedDate).toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
          })
        } catch {
          return String(processedDate)
        }
      })()
    : 'Unknown'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-red-200 bg-red-50 px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl">⚠️</span>
            <h2 className="text-lg font-bold uppercase tracking-wide text-red-900">
              Duplicate Invoice Detected
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-red-700 hover:bg-red-100"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="text-sm font-medium text-slate-600">Invoice ID</label>
            <p className="text-slate-900 font-semibold">{invoiceId}</p>
          </div>
          <p className="font-semibold text-slate-700">This invoice already exists in the system:</p>
          <div className="space-y-2 text-sm">
            <div className="flex items-start gap-2">
              <span>📄</span>
              <div>
                <label className="text-slate-500">Existing file</label>
                <p className="font-medium text-slate-800">{existingDoc}</p>
              </div>
            </div>
            {vendor ? (
              <div className="flex items-start gap-2">
                <span>🏢</span>
                <div>
                  <label className="text-slate-500">Vendor</label>
                  <p className="font-medium text-slate-800">{vendor}</p>
                </div>
              </div>
            ) : null}
            {amount != null && String(amount).trim() !== '' ? (
              <div className="flex items-start gap-2">
                <span>💰</span>
                <div>
                  <label className="text-slate-500">Amount</label>
                  <p className="font-medium text-slate-800">{formatAmountCurrency(amount, currency)}</p>
                </div>
              </div>
            ) : null}
            <div className="flex items-start gap-2">
              <span>📅</span>
              <div>
                <label className="text-slate-500">Processed date</label>
                <p className="font-medium text-slate-800">{processedDateStr}</p>
              </div>
            </div>
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <strong>⚠️ Important:</strong> The duplicate invoice was not saved to the database.
            Please verify and re-upload the correct document.
          </div>
        </div>
        <div className="border-t border-slate-200 px-5 py-3 text-right">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            OK
          </button>
        </div>
      </div>
    </div>
  )
}

