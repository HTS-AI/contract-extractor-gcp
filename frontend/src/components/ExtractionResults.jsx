import React from 'react'

function getNested(obj, ...paths) {
  for (const p of paths) {
    if (obj == null) return ''
    if (typeof p === 'string' && p.includes('.')) {
      for (const k of p.split('.')) obj = obj?.[k]
    } else {
      obj = obj?.[p]
    }
  }
  return obj != null && obj !== '' ? obj : ''
}

function formatAmountWithCurrency(amount, currency) {
  if (amount == null || amount === '') return '-'
  const num = parseFloat(String(amount).replace(/,/g, ''))
  if (isNaN(num)) return amount
  const formatted = num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const code = (currency || '').toUpperCase().trim()
  const symbols = { USD: '$', INR: '₹', EUR: '€', GBP: '£', QAR: 'QAR ', AED: 'AED ' }
  const prefix = symbols[code] || (code ? code + ' ' : '')
  return prefix + formatted
}

function riskLevel(score) {
  const n = parseInt(score, 10) || 0
  if (n >= 80) return { label: 'Critical', class: 'risk-critical' }
  if (n >= 60) return { label: 'High', class: 'risk-high' }
  if (n >= 30) return { label: 'Medium', class: 'risk-medium' }
  return { label: 'Low', class: 'risk-low' }
}

const TAX_ID_FIELDS = [
  { key: 'gstin', label: 'GSTIN' },
  { key: 'pan', label: 'PAN' },
  { key: 'vat', label: 'VAT Number' },
  { key: 'eori', label: 'EORI Number' },
  { key: 'tax_id', label: 'Tax ID' },
  { key: 'ein', label: 'EIN' },
  { key: 'tin', label: 'TIN' },
  { key: 'trn', label: 'TRN' },
  { key: 'cr_number', label: 'CR Number' },
  { key: 'other_id', labelKey: 'other_id_label' }
]

const INVOICE_DATE_FIELDS = [
  { key: 'invoice_date', label: 'Invoice Date' },
  { key: 'due_date', label: 'Due Date' },
  { key: 'supply_date', label: 'Supply Date' },
  { key: 'delivery_date', label: 'Delivery Date' },
  { key: 'order_date', label: 'Order Date' },
  { key: 'ship_date', label: 'Ship Date' }
]

const ADDITIONAL_TEXT_FIELDS = [
  { key: 'notes', label: 'Notes', icon: '📝' },
  { key: 'declaration', label: 'Declaration', icon: '📜' },
  { key: 'terms_and_conditions', label: 'Terms & Conditions', icon: '📋' },
  { key: 'remarks', label: 'Remarks', icon: '💬' },
  { key: 'additional_info', label: 'Additional Information', icon: 'ℹ️' }
]

function InfoCard({ title, icon, children, className = '' }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm ${className}`}>
      <div className="card-header mb-3 flex items-center gap-2 border-b border-slate-100 pb-2">
        <span>{icon}</span>
        <h3 className="text-base font-semibold text-slate-800">{title}</h3>
      </div>
      {children}
    </div>
  )
}

function InfoGrid({ children }) {
  return <div className="info-grid grid gap-3 sm:grid-cols-2">{children}</div>
}

function InfoItem({ label, value, mono }) {
  if (value == null || value === '') return null
  return (
    <div className="info-item">
      <label className="mb-0.5 block text-xs font-medium uppercase text-slate-500">{label}</label>
      <span className={mono ? 'font-mono text-sm text-slate-800' : 'text-sm text-slate-800'}>{value}</span>
    </div>
  )
}

export default function ExtractionResults({ results }) {
  if (!results || typeof results !== 'object') return null

  const r = results
  const payment = r.payment_terms || {}
  const parties = r.parties || {}
  const inv = r.invoice_details || {}
  const invPayment = inv.payment_details || {}
  const paymentDetails = r.payment_details || {}
  const isInvoice = (r.contract_type || '').toUpperCase() === 'INVOICE'

  const risk = riskLevel(r.risk_score)

  return (
    <div className="space-y-4">
      {/* 1. Basic Information */}
      <InfoCard title="Basic Information" icon="📊">
        <InfoGrid>
          <InfoItem label="Document Title" value={getNested(r, 'contract_title')} />
          <InfoItem label="Document Type" value={getNested(r, 'contract_type')} />
          <InfoItem label="Execution Date" value={getNested(r, 'execution_date')} />
          <div className="info-item">
            <label className="mb-0.5 block text-xs font-medium uppercase text-slate-500">Risk Score</label>
            <span className={`risk-badge inline-block rounded-full px-2 py-0.5 text-sm font-semibold ${risk.class}`}>
              {risk.label}
            </span>
          </div>
        </InfoGrid>
      </InfoCard>

      {/* 2. Invoice Details (ID, Type, Dates only - same as previous app) */}
      {isInvoice && Object.keys(inv).length > 0 && (
        <InfoCard title="Invoice Details" icon="🧾">
          <InfoGrid>
            <InfoItem label="Invoice ID" value={inv.invoice_id} />
            <InfoItem label="Invoice Type" value={inv.invoice_type} />
          </InfoGrid>
          {inv.dates && Object.keys(inv.dates).length > 0 && (
            <div className="mt-4 border-t border-slate-100 pt-4">
              <h4 className="mb-2 text-sm font-semibold text-slate-700">📅 Invoice Dates</h4>
              <InfoGrid>
                {INVOICE_DATE_FIELDS.map(({ key, label }) => {
                  const v = inv.dates[key]
                  return v ? <InfoItem key={key} label={label} value={v} /> : null
                })}
              </InfoGrid>
            </div>
          )}
        </InfoCard>
      )}

      {/* 3. Parties (below Invoice Details, same as previous app) */}
      <InfoCard title="Parties" icon="👥">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg bg-slate-50/80 p-3">
            <p className="text-xs font-medium text-slate-500">{parties.party_1_type || 'Party 1'}</p>
            <p className="font-medium text-slate-800">{parties.party_1_name || '-'}</p>
            <p className="text-sm text-slate-600 break-words">{parties.party_1_address || '-'}</p>
          </div>
          <div className="rounded-lg bg-slate-50/80 p-3">
            <p className="text-xs font-medium text-slate-500">{parties.party_2_type || 'Party 2'}</p>
            <p className="font-medium text-slate-800">{parties.party_2_name || '-'}</p>
            <p className="text-sm text-slate-600 break-words">{parties.party_2_address || '-'}</p>
          </div>
        </div>
      </InfoCard>

      {/* 4. Payment Terms (invoice only) */}
      {isInvoice && (inv.payment_terms || inv.payment_method || (inv.payment_details && (inv.payment_details.payment_terms || inv.payment_details.payment_method))) && (
        <InfoCard title="Payment Terms" icon="💳">
          <InfoGrid>
            <InfoItem label="Payment Terms" value={inv.payment_terms || inv.payment_details?.payment_terms} />
            <InfoItem label="Payment Method" value={inv.payment_method || inv.payment_details?.payment_method} />
          </InfoGrid>
        </InfoCard>
      )}

      {/* 5. Payment Details */}
      <InfoCard title="Payment Details" icon="💰">
        <InfoGrid>
          <div>
            <label className="mb-0.5 block text-xs font-medium uppercase text-slate-500">Amount</label>
            <span className="text-sm text-slate-800">{payment.amount != null ? formatAmountWithCurrency(payment.amount, payment.currency) : '-'}</span>
            {(payment.amount_explanation || r.amount_explanation) && (
              <small className="mt-1 block italic text-slate-500">{payment.amount_explanation || r.amount_explanation}</small>
            )}
          </div>
          <InfoItem label="Currency" value={payment.currency} />
          {invPayment.local_currency && invPayment.local_amount && (
            <>
              <InfoItem label="Local Amount" value={formatAmountWithCurrency(invPayment.local_amount, invPayment.local_currency)} />
              <InfoItem label="Local Currency" value={invPayment.local_currency} />
              {invPayment.exchange_rate && <InfoItem label="Exchange Rate" value={invPayment.exchange_rate} />}
            </>
          )}
        </InfoGrid>
      </InfoCard>

      {/* 6. Amount Breakdown (invoice only) */}
      {isInvoice && (inv.tax_details || inv.amounts) && (() => {
        const amounts = inv.amounts || inv.tax_details || {}
        const taxes = amounts.taxes || []
        const additionalCharges = amounts.additional_charges || []
        const hasSubtotal = amounts.subtotal != null
        const hasTotal = amounts.total != null
        const hasTax = Array.isArray(taxes) && taxes.length > 0
        const hasCharges = Array.isArray(additionalCharges) && additionalCharges.length > 0
        const hasDiscount = amounts.discount != null
        if (!hasSubtotal && !hasTotal && !hasTax && !hasCharges && !hasDiscount) return null
        return (
          <InfoCard title="Amount Breakdown" icon="💹">
            <InfoGrid>
              {hasSubtotal && <InfoItem label="Subtotal" value={amounts.subtotal} />}
              {hasCharges && additionalCharges.map((c, i) => c?.label && c?.amount && <InfoItem key={i} label={c.label} value={c.amount} />)}
              {hasDiscount && <InfoItem label="Discount" value={amounts.discount} />}
              {hasTax && taxes.map((t, i) => t?.label && t?.amount && <InfoItem key={i} label={t.label + (t.percent ? ` (${t.percent}%)` : '')} value={t.amount} />)}
              {hasTotal && <InfoItem label="Total" value={amounts.total} />}
              {amounts.amount_due != null && <InfoItem label="Amount Due" value={amounts.amount_due} />}
              {amounts.balance_due != null && <InfoItem label="Balance Due" value={amounts.balance_due} />}
            </InfoGrid>
          </InfoCard>
        )
      })()}

      {/* 7. Vendor/Supplier Tax IDs (invoice only) */}
      {isInvoice && ((inv.vendor_tax_ids && Object.keys(inv.vendor_tax_ids).length > 0) || inv.vendor_gstin || inv.vendor_pan) && (
        <InfoCard title="Vendor/Supplier Tax IDs" icon="🏢">
          <InfoGrid>
            {TAX_ID_FIELDS.map(({ key, label, labelKey }) => {
              const tax = inv.vendor_tax_ids || {}
              let v = tax[key]
              if (key === 'other_id' && labelKey && tax[labelKey]) return <InfoItem key={key} label={tax[labelKey]} value={v} mono />
              if (!v && key === 'gstin') v = inv.vendor_gstin
              if (!v && key === 'pan') v = inv.vendor_pan
              return v ? <InfoItem key={key} label={label} value={v} mono /> : null
            })}
          </InfoGrid>
        </InfoCard>
      )}

      {/* 8. Customer/Buyer Tax IDs (invoice only) */}
      {isInvoice && ((inv.customer_tax_ids && Object.keys(inv.customer_tax_ids).length > 0) || inv.customer_gstin) && (
        <InfoCard title="Customer/Buyer Tax IDs" icon="🤝">
          <InfoGrid>
            {TAX_ID_FIELDS.map(({ key, label, labelKey }) => {
              const tax = inv.customer_tax_ids || {}
              let v = tax[key]
              if (key === 'other_id' && labelKey && tax[labelKey]) return <InfoItem key={key} label={tax[labelKey]} value={v} mono />
              if (!v && key === 'gstin') v = inv.customer_gstin
              return v ? <InfoItem key={key} label={label} value={v} mono /> : null
            })}
          </InfoGrid>
        </InfoCard>
      )}

      {/* 9. Bank Details (invoice only) */}
      {isInvoice && (inv.bank_name || inv.bank_address) && (
        <InfoCard title="Bank Details" icon="🏦">
          <InfoGrid>
            <InfoItem label="Bank Name" value={inv.bank_name} />
            <div className="info-item sm:col-span-2">
              <label className="mb-0.5 block text-xs font-medium uppercase text-slate-500">Bank Address</label>
              <span className="text-sm text-slate-800 break-words">{inv.bank_address || '-'}</span>
            </div>
          </InfoGrid>
        </InfoCard>
      )}

      {/* 10. Account Details */}
      {(paymentDetails.account_holder_name || paymentDetails.account_number || paymentDetails.account_number_iban || paymentDetails.ifsc_code || paymentDetails.swift_code || paymentDetails.branch || paymentDetails.bank_address) && (
        <InfoCard title="Account Details" icon="🏧">
          {(paymentDetails.ifsc_code || (paymentDetails.account_number && !paymentDetails.swift_code && !paymentDetails.account_number_iban)) ? (
            <InfoGrid>
              <InfoItem label="Name" value={paymentDetails.account_holder_name} />
              <InfoItem label="Account No" value={paymentDetails.account_number} />
              <InfoItem label="IFSC Code" value={paymentDetails.ifsc_code} />
              <InfoItem label="Branch" value={paymentDetails.branch} />
            </InfoGrid>
          ) : (
            <InfoGrid>
              <InfoItem label="Account Name" value={paymentDetails.account_holder_name} />
              <InfoItem label="Account Number" value={paymentDetails.account_number} />
              <InfoItem label="IBAN" value={paymentDetails.account_number_iban} />
              <InfoItem label="SWIFT Code" value={paymentDetails.swift_code} />
            </InfoGrid>
          )}
          {paymentDetails.bank_address && (
            <div className="mt-3 border-t border-slate-100 pt-3">
              <InfoItem label="Bank Address" value={paymentDetails.bank_address} />
            </div>
          )}
        </InfoCard>
      )}

      {/* 11. Additional Information (invoice only) */}
      {isInvoice && ADDITIONAL_TEXT_FIELDS.some((f) => getNested(inv, f.key)) && (
        <InfoCard title="Additional Information" icon="📝">
          <div className="space-y-4">
            {ADDITIONAL_TEXT_FIELDS.map(({ key, label, icon: ico }) => {
              const v = getNested(inv, key)
              return v ? (
                <div key={key}>
                  <label className="mb-1 flex items-center gap-1 text-xs font-medium text-slate-600">{ico} {label}</label>
                  <div className="whitespace-pre-wrap rounded-lg border-l-4 border-amber-400 bg-slate-50 p-3 text-sm text-slate-800">{v}</div>
                </div>
              ) : null
            })}
          </div>
        </InfoCard>
      )}

      {/* 12. Deliverables */}
      <InfoCard title="Deliverables" icon="✅">
        <ul className="list-inside list-disc text-sm text-slate-700">
          {r.deliverables && r.deliverables.length > 0
            ? r.deliverables.map((item, i) => <li key={i}>{item}</li>)
            : <li className="text-slate-500">No deliverables specified</li>}
        </ul>
      </InfoCard>

      {/* 13. Missing Clauses */}
      {r.missing_clauses && r.missing_clauses.length > 0 && (
        <InfoCard title="Missing Clauses" icon="⚠️" className="border-amber-200 bg-amber-50/50">
          <ul className="list-inside list-disc text-sm text-amber-900">
            {r.missing_clauses.map((clause, i) => <li key={i}>{clause}</li>)}
          </ul>
        </InfoCard>
      )}

      <style>{`
        .risk-low { background: #d1fae5; color: #065f46; }
        .risk-medium { background: #fef3c7; color: #92400e; }
        .risk-high { background: #fed7aa; color: #9a3412; }
        .risk-critical { background: #fecaca; color: #991b1b; }
      `}</style>
    </div>
  )
}
