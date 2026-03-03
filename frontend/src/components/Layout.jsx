import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Chatbot from './Chatbot'
import NotificationPanel from './NotificationPanel'

export default function Layout({ children }) {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen flex-col bg-[#1e3a5f]">
      <header className="flex-shrink-0 border-b border-slate-200/80 bg-white/95 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <Link to="/main" className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700">
            🏠 Main
          </Link>
          <Link to="/invoice-to-ap" className="flex items-center gap-2 text-slate-800 hover:text-indigo-600">
            <span className="text-2xl">📄</span>
            <div>
              <h1 className="text-xl font-semibold">Invoice to AP</h1>
              <p className="text-sm text-slate-500">Extract & manage invoices</p>
            </div>
          </Link>
          <nav className="flex flex-wrap items-center gap-2">
            <Link
              to="/selected-factors"
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700"
            >
              📋 Selected Factors
            </Link>
            <Link
              to="/excel-table"
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700"
            >
              📊 Data Table
            </Link>
            <Link
              to="/billing-table"
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700"
            >
              🧾 Billing Table
            </Link>
            <Link
              to="/payment-table"
              className="rounded-lg bg-gradient-to-r from-emerald-600 to-emerald-700 px-3 py-2 text-sm font-medium text-white shadow-sm transition hover:from-emerald-700 hover:to-emerald-800"
            >
              💳 Payment Table
            </Link>
            <NotificationPanel />
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-red-200 hover:bg-red-50 hover:text-red-700"
            >
              🚪 Logout
            </button>
          </nav>
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-auto px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      <Chatbot />
    </div>
  )
}
