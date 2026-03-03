import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')
    const result = login(username.trim(), password)
    if (result.error) {
      setError(result.error)
      return
    }
    if (result.redirect) navigate(result.redirect)
    else navigate('/')
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-900/20 to-slate-900 px-4">
      <div className="w-full max-w-md">
        <div className="rounded-2xl border border-slate-200/50 bg-white/95 p-8 shadow-xl backdrop-blur-sm">
          <div className="mb-8 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-100 text-3xl">
              🔐
            </div>
            <h1 className="text-xl font-bold text-slate-800">Invoice to AP</h1>
            <p className="mt-1 text-sm text-slate-500">AI-Powered Document Extraction</p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="username" className="mb-1.5 block text-sm font-medium text-slate-700">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                autoComplete="username"
                required
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-slate-800 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-700">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                autoComplete="current-password"
                required
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-slate-800 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
                {error}
              </div>
            )}
            <button
              type="submit"
              className="w-full rounded-lg bg-gradient-to-r from-indigo-600 to-indigo-700 py-3 font-medium text-white shadow-lg transition hover:from-indigo-700 hover:to-indigo-800"
            >
              Sign in
            </button>
          </form>
          <p className="mt-6 text-center text-xs text-slate-500">
            Buyers: use <strong>buyer</strong> / <strong>buyer@2025</strong> for Buyer Portal.
          </p>
        </div>
      </div>
    </div>
  )
}
