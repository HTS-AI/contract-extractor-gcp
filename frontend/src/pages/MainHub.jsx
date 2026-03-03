import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function MainHub() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-br from-slate-900 via-indigo-900/20 to-slate-900">
      <header className="flex-shrink-0 border-b border-slate-700/50 bg-slate-800/80 px-4 py-3 sm:px-6">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-white">Document Processing</h1>
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-lg border border-slate-500 bg-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:bg-slate-600"
          >
            Logout
          </button>
        </div>
      </header>
      <main className="flex-1 px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <h2 className="mb-2 text-center text-2xl font-bold text-white sm:text-3xl">
            Choose a module
          </h2>
          <p className="mb-10 text-center text-slate-300">
            Select Invoice to AP or Cash bill to Expense to get started.
          </p>
          <div className="grid gap-6 sm:grid-cols-2">
            <Link
              to="/invoice-to-ap"
              className="group flex flex-col rounded-2xl border border-slate-600 bg-slate-800/60 p-8 shadow-xl transition hover:border-indigo-500 hover:bg-slate-800"
            >
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-indigo-500/20 text-3xl group-hover:bg-indigo-500/30">
                📄
              </div>
              <h3 className="mb-2 text-xl font-bold text-white">Invoice to Accounts Payable</h3>
              <p className="text-slate-300">
                Upload invoices, match with POs and GRNs, manage billing and payment status.
              </p>
              <span className="mt-4 inline-flex items-center text-sm font-medium text-indigo-400 group-hover:text-indigo-300">
                Open →
              </span>
            </Link>
            <Link
              to="/cashbill-expense"
              className="group flex flex-col rounded-2xl border border-slate-600 bg-slate-800/60 p-8 shadow-xl transition hover:border-emerald-500 hover:bg-slate-800"
            >
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-emerald-500/20 text-3xl group-hover:bg-emerald-500/30">
                🧾
              </div>
              <h3 className="mb-2 text-xl font-bold text-white">Cash bill to Expense</h3>
              <p className="text-slate-300">
                Upload cash bills and receipts. Extract data with GCP Vision and view in the Expense table.
              </p>
              <span className="mt-4 inline-flex items-center text-sm font-medium text-emerald-400 group-hover:text-emerald-300">
                Open →
              </span>
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}
