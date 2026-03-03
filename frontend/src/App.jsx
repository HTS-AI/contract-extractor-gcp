import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { CurrentExtractionProvider } from './context/CurrentExtractionContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import MainHub from './pages/MainHub'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import SelectedFactors from './pages/SelectedFactors'
import ExcelTable from './pages/ExcelTable'
import PaymentTable from './pages/PaymentTable'
import BillingTable from './pages/BillingTable'
import BuyerPortal from './pages/BuyerPortal'
import CashbillHome from './pages/CashbillHome'
import CashbillExpense from './pages/CashbillExpense'

function RequireMainUser({ children }) {
  return (
    <ProtectedRoute requireBuyer={false}>
      {children}
    </ProtectedRoute>
  )
}

function RequireBuyer({ children }) {
  return (
    <ProtectedRoute requireBuyer={true}>
      {children}
    </ProtectedRoute>
  )
}

function LoginRedirect() {
  const { isLoggedIn, isBuyer } = useAuth()
  if (isLoggedIn && isBuyer) return <Navigate to="/buyer-portal" replace />
  if (isLoggedIn) return <Navigate to="/main" replace />
  return <Login />
}

export default function App() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <AuthProvider>
        <BrowserRouter>
        <CurrentExtractionProvider>
        <Routes>
          <Route path="/login" element={<LoginRedirect />} />
          <Route
            path="/main"
            element={
              <RequireMainUser>
                <MainHub />
              </RequireMainUser>
            }
          />
          <Route
            path="/invoice-to-ap"
            element={
              <RequireMainUser>
                <Home />
              </RequireMainUser>
            }
          />
          <Route
            path="/"
            element={
              <RequireMainUser>
                <Navigate to="/main" replace />
              </RequireMainUser>
            }
          />
          <Route
            path="/dashboard"
            element={
              <RequireMainUser>
                <Dashboard />
              </RequireMainUser>
            }
          />
          <Route
            path="/selected-factors"
            element={
              <RequireMainUser>
                <SelectedFactors />
              </RequireMainUser>
            }
          />
          <Route
            path="/excel-table"
            element={
              <RequireMainUser>
                <ExcelTable />
              </RequireMainUser>
            }
          />
          <Route
            path="/billing-table"
            element={
              <RequireMainUser>
                <BillingTable />
              </RequireMainUser>
            }
          />
          <Route
            path="/payment-table"
            element={
              <RequireMainUser>
                <PaymentTable />
              </RequireMainUser>
            }
          />
          <Route
            path="/cashbill-expense"
            element={
              <RequireMainUser>
                <CashbillHome />
              </RequireMainUser>
            }
          />
          <Route
            path="/expense-table"
            element={
              <RequireMainUser>
                <CashbillExpense />
              </RequireMainUser>
            }
          />
          <Route
            path="/buyer-portal"
            element={
              <RequireBuyer>
                <BuyerPortal />
              </RequireBuyer>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </CurrentExtractionProvider>
      </BrowserRouter>
    </AuthProvider>
    </div>
  )
}
