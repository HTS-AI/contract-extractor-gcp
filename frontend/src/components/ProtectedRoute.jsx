import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute({ children, requireBuyer = false }) {
  const { isLoggedIn, isBuyer } = useAuth()
  const location = useLocation()

  if (!isLoggedIn) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (requireBuyer && !isBuyer) {
    return <Navigate to="/" replace />
  }

  if (!requireBuyer && isBuyer) {
    return <Navigate to="/buyer-portal" replace />
  }

  return children
}
