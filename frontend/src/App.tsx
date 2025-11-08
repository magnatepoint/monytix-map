import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Callback from './pages/Callback'
import Console from './pages/Console'
import SpendSense from './pages/SpendSense'
import BudgetPilot from './pages/BudgetPilot'
import MoneyMoments from './pages/MoneyMoments'
import GoalCompass from './pages/GoalCompass'
import Layout from './components/Layout'
import Loading from './components/Loading'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  
  return <Layout>{children}</Layout>
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/callback" element={<Callback />} />
          <Route path="/" element={
            <ProtectedRoute>
              <Console />
            </ProtectedRoute>
          } />
          <Route path="/spendsense" element={
            <ProtectedRoute>
              <SpendSense />
            </ProtectedRoute>
          } />
          <Route path="/budgetpilot" element={
            <ProtectedRoute>
              <BudgetPilot />
            </ProtectedRoute>
          } />
          <Route path="/moneymoments" element={
            <ProtectedRoute>
              <MoneyMoments />
            </ProtectedRoute>
          } />
          <Route path="/goalcompass" element={
            <ProtectedRoute>
              <GoalCompass />
            </ProtectedRoute>
          } />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
