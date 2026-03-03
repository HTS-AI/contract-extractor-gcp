import React, { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { uploadPO, uploadGRN, getMatchStatus } from '../api/client'

export default function BuyerPortal() {
  const { logout, isBuyer } = useAuth()
  const navigate = useNavigate()
  const [poFile, setPoFile] = useState(null)
  const [grnFile, setGrnFile] = useState(null)
  const [poStatus, setPoStatus] = useState({ msg: '', error: false })
  const [grnStatus, setGrnStatus] = useState({ msg: '', error: false })
  const [match, setMatch] = useState({ ready: [], pending: [] })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!isBuyer) {
      const ok = sessionStorage.getItem('contractAppLoggedIn') === 'true'
      const role = sessionStorage.getItem('contractAppRole')
      if (!ok || role !== 'buyer') navigate('/login')
    }
  }, [isBuyer, navigate])

  const loadMatch = useCallback(async () => {
    try {
      const res = await getMatchStatus()
      if (res.success) {
        setMatch({
          ready: res.ready_for_payment || [],
          pending: res.pending || []
        })
      }
    } catch (e) {
      console.error(e)
    }
  }, [])

  useEffect(() => { loadMatch() }, [loadMatch])

  const handlePoUpload = async () => {
    if (!poFile) return
    setLoading(true)
    setPoStatus({ msg: '', error: false })
    try {
      const res = await uploadPO(poFile)
      if (res.success) {
        setPoStatus({ msg: `PO uploaded: ${res.po_number || res.file_name || 'OK'}`, error: false })
        setPoFile(null)
        loadMatch()
      } else {
        setPoStatus({ msg: res.detail || res.error || 'Upload failed', error: true })
      }
    } catch (e) {
      setPoStatus({ msg: e.message || 'Error', error: true })
    } finally {
      setLoading(false)
    }
  }

  const handleGrnUpload = async () => {
    if (!grnFile) return
    setLoading(true)
    setGrnStatus({ msg: '', error: false })
    try {
      const res = await uploadGRN(grnFile)
      if (res.success) {
        setGrnStatus({ msg: `GRN uploaded. PO ref: ${res.po_number || '—'}`, error: false })
        setGrnFile(null)
        loadMatch()
      } else {
        setGrnStatus({ msg: res.detail || res.error || 'Upload failed', error: true })
      }
    } catch (e) {
      setGrnStatus({ msg: e.message || 'Error', error: true })
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen flex-col bg-[#1e3a5f]">
      <div className="min-h-0 flex-1 overflow-auto">
        <div className="mx-auto max-w-3xl px-4 py-8">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Buyer Portal</h1>
            <p className="mt-1 text-slate-200">
              Upload Purchase Orders and GRN. Payment is processed only when PO, GRN and Invoice match.
            </p>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Logout
          </button>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold text-slate-800">Upload Purchase Order (PO)</h2>
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="file"
                accept=".pdf,.docx,.doc,.txt"
                className="hidden"
                id="po-file"
                onChange={(e) => setPoFile(e.target.files?.[0] || null)}
              />
              <label
                htmlFor="po-file"
                className={`cursor-pointer rounded-lg border-2 border-dashed px-4 py-3 text-sm font-medium ${poFile ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-300 text-slate-600 hover:border-indigo-400'}`}
              >
                {poFile ? poFile.name : 'Choose PO file'}
              </label>
              <button
                type="button"
                onClick={handlePoUpload}
                disabled={!poFile || loading}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                Upload PO
              </button>
            </div>
            {poStatus.msg && (
              <p className={`mt-2 text-sm ${poStatus.error ? 'text-red-600' : 'text-emerald-600'}`}>
                {poStatus.msg}
              </p>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold text-slate-800">Upload GRN (Goods Received Note)</h2>
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="file"
                accept=".pdf,.docx,.doc,.txt"
                className="hidden"
                id="grn-file"
                onChange={(e) => setGrnFile(e.target.files?.[0] || null)}
              />
              <label
                htmlFor="grn-file"
                className={`cursor-pointer rounded-lg border-2 border-dashed px-4 py-3 text-sm font-medium ${grnFile ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-300 text-slate-600 hover:border-indigo-400'}`}
              >
                {grnFile ? grnFile.name : 'Choose GRN file'}
              </label>
              <button
                type="button"
                onClick={handleGrnUpload}
                disabled={!grnFile || loading}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                Upload GRN
              </button>
            </div>
            {grnStatus.msg && (
              <p className={`mt-2 text-sm ${grnStatus.error ? 'text-red-600' : 'text-emerald-600'}`}>
                {grnStatus.msg}
              </p>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-2 text-lg font-semibold text-slate-800">Match status (PO + GRN + Invoice)</h3>
            <p className="mb-4 text-sm text-slate-500">
              Payment is processed only when all three documents are present and matched for the same PO number.
            </p>
            <button
              type="button"
              onClick={loadMatch}
              className="mb-4 rounded-lg bg-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-300"
            >
              Refresh status
            </button>
            {match.ready.length > 0 && (
              <div className="mb-4">
                <p className="mb-2 font-medium text-slate-700">Ready for payment</p>
                <div className="space-y-2">
                  {match.ready.map((x, i) => (
                    <div key={i} className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                      {x.po_number} – {x.message || ''}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {match.pending.length > 0 && (
              <div>
                <p className="mb-2 font-medium text-slate-700">Pending (missing GRN or Invoice)</p>
                <div className="space-y-2">
                  {match.pending.map((x, i) => (
                    <div key={i} className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                      {x.po_number} – {x.reason || ''}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {match.ready.length === 0 && match.pending.length === 0 && (
              <p className="text-slate-500">No PO+GRN+Invoice matches yet.</p>
            )}
          </div>

          <p className="text-center">
            <a href="/" className="text-indigo-600 hover:underline">Back to main application</a>
          </p>
        </div>
      </div>
      </div>
    </div>
  )
}
