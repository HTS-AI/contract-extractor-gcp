const API_BASE = ''

function handleResponse(res) {
  if (!res.ok) {
    return res.json().then((d) => { throw new Error(d.detail || d.message || 'Request failed') }).catch(() => { throw new Error('Request failed') })
  }
  return res.json()
}

// ——— Auth (client-side only) ———
export const SESSION_KEY = 'contractAppLoggedIn'
export const BUYER_ROLE_KEY = 'contractAppRole'
export const VALID_USERNAME = 'HtsAI-testuser'
export const VALID_PASSWORD = 'HTStest@2025'
export const BUYER_USERNAME = 'buyer'
export const BUYER_PASSWORD = 'buyer@2025'

// ——— Billing ———
export async function getBilling() {
  return fetch(`${API_BASE}/api/billing`).then(handleResponse)
}

export async function updateBilling(extractionId, payload) {
  const res = await fetch(`${API_BASE}/api/billing/${encodeURIComponent(extractionId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  return handleResponse(res)
}

// ——— Payment ———
export async function getPaymentStatus() {
  return fetch(`${API_BASE}/api/payment-status`).then(handleResponse)
}

export async function updatePaymentStatus(extractionId, payload) {
  const res = await fetch(`${API_BASE}/api/payment-status/${encodeURIComponent(extractionId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  return handleResponse(res)
}

// ——— Upload & Extract ———
export async function uploadFile(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: form })
  return handleResponse(res)
}

export async function extract(extractionId) {
  const res = await fetch(`${API_BASE}/api/extract/${extractionId}`, { method: 'POST' })
  return handleResponse(res)
}

export async function getExtractionStatus(extractionId) {
  const res = await fetch(`${API_BASE}/api/extraction-status/${extractionId}`)
  return handleResponse(res)
}

export async function getExtraction(extractionId) {
  const res = await fetch(`${API_BASE}/api/extraction/${extractionId}`)
  return handleResponse(res)
}

export async function getExtractionsList() {
  const res = await fetch(`${API_BASE}/api/extractions-list`)
  return handleResponse(res)
}

// ——— Dashboard (main) ———
export async function getDashboard() {
  const res = await fetch(`${API_BASE}/api/dashboard`)
  return handleResponse(res)
}

// ——— JSON data (dashboard page & selected factors) ———
export async function getJsonData() {
  const res = await fetch(`${API_BASE}/api/json-data`)
  return handleResponse(res)
}

// ——— Excel ———
export async function getExcelData() {
  const res = await fetch(`${API_BASE}/api/excel-data`)
  return handleResponse(res)
}

export function getDownloadExcelUrl() {
  return `${API_BASE}/api/download-excel`
}

// ——— Buyer portal ———
export async function uploadPO(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/api/upload-po`, { method: 'POST', body: form })
  return handleResponse(res)
}

export async function uploadGRN(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/api/upload-grn`, { method: 'POST', body: form })
  return handleResponse(res)
}

export async function getMatchStatus() {
  const res = await fetch(`${API_BASE}/api/match-status`)
  return handleResponse(res)
}

// ——— File manager ———
export async function getFilesList() {
  const res = await fetch(`${API_BASE}/api/files/list`)
  return handleResponse(res)
}

export async function deleteFile(payload) {
  const res = await fetch(`${API_BASE}/api/files/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  return handleResponse(res)
}

export async function deleteExtractionRecord(extractionId) {
  const res = await fetch(`${API_BASE}/api/files/extraction/${encodeURIComponent(extractionId)}`, {
    method: 'DELETE'
  })
  return handleResponse(res)
}

export async function clearAllFiles() {
  const res = await fetch(`${API_BASE}/api/files/clear-all`, { method: 'POST' })
  return handleResponse(res)
}

// ——— Chat ———
export async function chatUpload(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/api/chat/upload`, { method: 'POST', body: form })
  return handleResponse(res)
}

export async function chatLoadFromExtraction(extractionId) {
  const res = await fetch(`${API_BASE}/api/chat/load-from-extraction/${extractionId}`, { method: 'POST' })
  return handleResponse(res)
}

export async function chatLoadAllDocuments() {
  const res = await fetch(`${API_BASE}/api/chat/load-all-documents`, { method: 'POST' })
  return handleResponse(res)
}

export async function chatAsk(sessionId, question) {
  const res = await fetch(`${API_BASE}/api/chat/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, question })
  })
  return handleResponse(res)
}

export async function getChatSession(sessionId) {
  const res = await fetch(`${API_BASE}/api/chat/session/${sessionId}`)
  return handleResponse(res)
}

// ——— Notifications ———
export async function getNotifications() {
  const res = await fetch(`${API_BASE}/api/notifications`)
  return handleResponse(res)
}

export async function markAllNotificationsRead() {
  const res = await fetch(`${API_BASE}/api/notifications/read-all`, { method: 'PATCH' })
  return handleResponse(res)
}

export async function markNotificationRead(id) {
  const res = await fetch(`${API_BASE}/api/notifications/${id}/read`, { method: 'PATCH' })
  return handleResponse(res)
}

export async function clearNotifications() {
  const res = await fetch(`${API_BASE}/api/notifications`, { method: 'DELETE' })
  return handleResponse(res)
}

export async function deleteChatSession(sessionId) {
  const res = await fetch(`${API_BASE}/api/chat/session/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
  if (!res.ok) return res.json().then((d) => { throw new Error(d.detail || d.message || 'Request failed') }).catch(() => ({ success: false }))
  return res.json().catch(() => ({ success: true }))
}

// ——— Cash bill to Expense (GCP Vision; separate from Invoice to AP) ———
export async function expenseUpload(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/api/expense/upload`, { method: 'POST', body: form })
  return handleResponse(res)
}

export async function getExpenseList() {
  const res = await fetch(`${API_BASE}/api/expense/list`)
  return handleResponse(res)
}

export async function getExpenseDashboard() {
  const res = await fetch(`${API_BASE}/api/expense/dashboard`)
  return handleResponse(res)
}

export async function getExpense(expenseId) {
  const res = await fetch(`${API_BASE}/api/expense/${encodeURIComponent(expenseId)}`)
  return handleResponse(res)
}

export async function updateExpense(expenseId, payload) {
  const res = await fetch(`${API_BASE}/api/expense/${encodeURIComponent(expenseId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  return handleResponse(res)
}

export function getExpenseFileUrl(expenseId) {
  return `${API_BASE}/api/expense/${encodeURIComponent(expenseId)}/file`
}

export async function deleteExpense(expenseId) {
  const res = await fetch(`${API_BASE}/api/expense/${encodeURIComponent(expenseId)}`, { method: 'DELETE' })
  return handleResponse(res)
}

// ——— Expense Chatbot (separate from Invoice to AP chat) ———
export async function expenseChatStart() {
  const res = await fetch(`${API_BASE}/api/expense-chat/start`, { method: 'POST' })
  return handleResponse(res)
}

export async function expenseChatAsk(sessionId, question) {
  const res = await fetch(`${API_BASE}/api/expense-chat/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, question })
  })
  return handleResponse(res)
}

export async function expenseChatRefresh(sessionId) {
  const res = await fetch(`${API_BASE}/api/expense-chat/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId })
  })
  return handleResponse(res)
}
