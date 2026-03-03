import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { SESSION_KEY, BUYER_ROLE_KEY, VALID_USERNAME, VALID_PASSWORD, BUYER_USERNAME, BUYER_PASSWORD } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [isLoggedIn, setIsLoggedIn] = useState(() => sessionStorage.getItem(SESSION_KEY) === 'true')
  const [role, setRole] = useState(() => sessionStorage.getItem(BUYER_ROLE_KEY) || null)

  const login = useCallback((username, password) => {
    if (username === BUYER_USERNAME && password === BUYER_PASSWORD) {
      sessionStorage.setItem(SESSION_KEY, 'true')
      sessionStorage.setItem(BUYER_ROLE_KEY, 'buyer')
      setIsLoggedIn(true)
      setRole('buyer')
      return { redirect: '/buyer-portal' }
    }
    if (username === VALID_USERNAME && password === VALID_PASSWORD) {
      sessionStorage.setItem(SESSION_KEY, 'true')
      sessionStorage.removeItem(BUYER_ROLE_KEY)
      setIsLoggedIn(true)
      setRole(null)
      return { redirect: '/main' }
    }
    return { error: 'Invalid username or password.' }
  }, [])

  const logout = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY)
    sessionStorage.removeItem(BUYER_ROLE_KEY)
    setIsLoggedIn(false)
    setRole(null)
  }, [])

  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_KEY) === 'true'
    const storedRole = sessionStorage.getItem(BUYER_ROLE_KEY)
    setIsLoggedIn(stored)
    setRole(storedRole || null)
  }, [])

  const value = { isLoggedIn, role, login, logout, isBuyer: role === 'buyer' }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
