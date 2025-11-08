import { useEffect, useMemo, useRef, useState } from 'react'
import { TrendingUp, TrendingDown, DollarSign, CreditCard, ArrowUp, ArrowDown } from 'lucide-react'
import PasswordDialog from '../components/PasswordDialog'
import TransactionAddDialog from '../components/TransactionAddDialog'
import { apiClient } from '../lib/api'

// Declare Google Identity Services types
declare global {
  interface Window {
    google?: {
      accounts: {
        oauth2: {
          initTokenClient: (config: {
            client_id: string
            scope: string
            callback: (response: { access_token: string }) => void
            error_callback?: (error: { type: string; message: string }) => void
          }) => {
            requestAccessToken: () => void
          }
        }
      }
    }
  }
}

// Transaction type from API
interface TransactionResponse {
  id?: string
  txn_id?: string
  merchant?: string
  merchant_name_norm?: string
  amount?: number | string
  direction?: 'credit' | 'debit'
  transaction_type?: 'credit' | 'debit'
  category?: string
  category_code?: string
  subcategory?: string
  subcategory_code?: string
  description?: string
  transaction_date?: string
  txn_date?: string
}

interface TxnItem {
  id: string
  merchant?: string
  amount: number
  direction?: 'credit' | 'debit'
  category?: string
  transaction_date?: string
  description?: string
  subcategory?: string
}

export default function Console() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [gmailConnected, setGmailConnected] = useState(false)
  const [gmailConnections, setGmailConnections] = useState<Array<{
    id: string
    email: string | null
    display_name: string | null
    is_active: boolean
    sync_enabled: boolean
    last_sync_at: string | null
    total_emails_fetched: number
    total_transactions_extracted: number
    created_at: string
  }>>([])

  // Stats
  const [statsData, setStatsData] = useState<{
    total_spending: number
    total_income: number
    net_flow: number
    cumulative_balance?: number
    transaction_count: number
  } | null>(null)

  // Transactions
  const [recentTransactions, setRecentTransactions] = useState<TxnItem[]>([])

  // Upload state
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [showPasswordDialog, setShowPasswordDialog] = useState(false)
  const [pendingPdfInfo, setPendingPdfInfo] = useState<{ file: File; bank?: string } | null>(null)
  const [addDialogOpen, setAddDialogOpen] = useState(false)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        // Check Gmail connection status and list connections
        try {
          const status = await apiClient.gmailStatus()
          setGmailConnected(status?.active || false)
          
          // Load list of connections
          const connectionsRes = await apiClient.listGmailConnections()
          setGmailConnections(connectionsRes?.connections || [])
        } catch {
          // Ignore status check errors
        }

        // Fetch stats
        const stats = await apiClient.getSpendingStats('month')
        setStatsData({
          total_spending: stats.total_spending || 0,
          total_income: stats.total_income || 0,
          net_flow: stats.net_flow || 0,
          cumulative_balance: stats.cumulative_balance ?? stats.net_flow ?? 0,
          transaction_count: stats.transaction_count || 0,
        })

        // Fetch recent transactions (5)
        const txnsResponse = await apiClient.getTransactions(0, 5)
        // Handle both old format (array) and new format (object with data field)
        const txns = Array.isArray(txnsResponse) ? txnsResponse : ((txnsResponse as any)?.data || [])
        const mapped: TxnItem[] = (txns || []).map((t: TransactionResponse) => ({
          id: t.id || t.txn_id || Math.random().toString(36).slice(2),
          merchant: t.merchant || t.merchant_name_norm || '—',
          amount: Number(t.amount ?? 0),
          direction: t.direction || t.transaction_type || 'debit',
          category: t.category || t.category_code,
          transaction_date: t.transaction_date || t.txn_date,
          description: t.description,
          subcategory: t.subcategory || t.subcategory_code,
        }))
        setRecentTransactions(mapped)
      } catch (e) {
        const error = e instanceof Error ? e : new Error('Failed to load data')
        setError(error.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const statCards = useMemo(() => {
    // Net Flow for current month (income - spending)
    const netFlow = statsData?.net_flow || 0
    // Total Balance shows cumulative balance from all transactions
    const totalBalance = statsData?.cumulative_balance ?? netFlow
    return [
      { name: 'Total Balance', value: `₹${Math.round(totalBalance).toLocaleString()}`, change: '', trend: totalBalance >= 0 ? 'up' : 'down', icon: DollarSign },
      { name: 'Monthly Spend', value: `₹${Math.round(statsData?.total_spending || 0).toLocaleString()}`, change: '', trend: 'down', icon: CreditCard },
      { name: 'Income', value: `₹${Math.round(statsData?.total_income || 0).toLocaleString()}`, change: '', trend: 'up', icon: TrendingUp },
      { name: 'Net Flow', value: `₹${Math.round(netFlow).toLocaleString()}`, change: '', trend: netFlow >= 0 ? 'up' : 'down', icon: TrendingDown },
    ] as Array<{ name: string; value: string; change: string; trend: 'up'|'down'; icon: React.ComponentType<{ className?: string }> }>
  }, [statsData])

  const onClickUpload = () => {
    fileInputRef.current?.click()
  }

  const onFileSelected: React.ChangeEventHandler<HTMLInputElement> = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      setLoading(true)
      setError(null)
      if (file.name.toLowerCase().endsWith('.csv')) {
        await apiClient.uploadCSV(file)
        // After CSV staging, load to fact + enrichment
        try { 
          const result = await apiClient.loadStagingToFact()
          console.log('✅ Loaded staging to fact:', result)
        } catch (err) {
          const errorMessage = (err as Error & { detail?: string }).detail || (err as Error).message || 'Unknown error'
          console.error('❌ Failed to load staging to fact:', errorMessage)
          // Show user-friendly error
          if (!errorMessage.includes('Request failed')) {
            setError(`Upload succeeded but failed to load transactions: ${errorMessage}`)
          }
        }
      } else if (file.name.toLowerCase().endsWith('.xls') || file.name.toLowerCase().endsWith('.xlsx')) {
        await apiClient.uploadXLS(file)
        try { 
          const result = await apiClient.loadStagingToFact()
          console.log('✅ Loaded staging to fact:', result)
        } catch (err) {
          const errorMessage = (err as Error & { detail?: string }).detail || (err as Error).message || 'Unknown error'
          console.error('❌ Failed to load staging to fact:', errorMessage)
          if (!errorMessage.includes('Request failed')) {
            setError(`Upload succeeded but failed to load transactions: ${errorMessage}`)
          }
        }
      } else if (file.name.toLowerCase().endsWith('.pdf')) {
        const res = await apiClient.uploadPDF(file)
        if (res?.requires_password) {
          setPendingPdfInfo({ file, bank: res.bank })
          setShowPasswordDialog(true)
          return
        }
        // PDFs also stage -> attempt load
        try { 
          const result = await apiClient.loadStagingToFact()
          console.log('✅ Loaded staging to fact:', result)
        } catch (err) {
          const errorMessage = (err as Error & { detail?: string }).detail || (err as Error).message || 'Unknown error'
          console.error('❌ Failed to load staging to fact:', errorMessage)
          if (!errorMessage.includes('Request failed')) {
            setError(`Upload succeeded but failed to load transactions: ${errorMessage}`)
          }
        }
      } else {
        await apiClient.uploadCSV(file)
        try { 
          const result = await apiClient.loadStagingToFact()
          console.log('✅ Loaded staging to fact:', result)
        } catch (err) {
          const errorMessage = (err as Error & { detail?: string }).detail || (err as Error).message || 'Unknown error'
          console.error('❌ Failed to load staging to fact:', errorMessage)
          if (!errorMessage.includes('Request failed')) {
            setError(`Upload succeeded but failed to load transactions: ${errorMessage}`)
          }
        }
      }
      // Refresh transactions after upload (5)
      const txns = await apiClient.getTransactions(0, 5) as TransactionResponse[]
        setRecentTransactions((txns || []).map((t) => ({
          id: t.id || t.txn_id || Math.random().toString(36).slice(2),
          merchant: t.merchant || t.merchant_name_norm || '—',
          amount: Number(t.amount ?? 0),
          direction: t.direction || t.transaction_type || 'debit',
          category: t.category || t.category_code,
          transaction_date: t.transaction_date || t.txn_date,
          description: t.description,
          subcategory: t.subcategory || t.subcategory_code,
        })))
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Upload failed')
      setError(error.message)
    } finally {
      setLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const onConfirmPdfPassword = async (password: string) => {
    if (!pendingPdfInfo) return
    try {
      setLoading(true)
      await apiClient.uploadPDF(pendingPdfInfo.file, pendingPdfInfo.bank, password)
      setShowPasswordDialog(false)
      setPendingPdfInfo(null)
      // Refresh transactions after PDF upload
      try {
        await apiClient.loadStagingToFact()
      } catch (err) {
        console.warn('Failed to load staging to fact:', err)
      }
      const txns = await apiClient.getTransactions(0, 5) as TransactionResponse[]
      setRecentTransactions((txns || []).map((t) => ({
        id: t.id || t.txn_id || Math.random().toString(36).slice(2),
        merchant: t.merchant || t.merchant_name_norm || '—',
        amount: Number(t.amount ?? 0),
        direction: t.direction || t.transaction_type || 'debit',
        category: t.category || t.category_code,
        transaction_date: t.transaction_date || t.txn_date,
        description: t.description,
        subcategory: t.subcategory || t.subcategory_code,
      })))
    } catch (e) {
      const error = e instanceof Error ? e : new Error('PDF decryption failed')
      setError(error.message)
    } finally {
      setLoading(false)
    }
  }

  const handleAddTransactionSuccess = async () => {
    // Reload recent transactions after adding
    try {
      const txns = await apiClient.getTransactions(0, 5) as TransactionResponse[]
      setRecentTransactions((txns || []).map((t) => ({
        id: t.id || t.txn_id || Math.random().toString(36).slice(2),
        merchant: t.merchant || t.merchant_name_norm || '—',
        amount: Number(t.amount ?? 0),
        direction: t.direction || t.transaction_type || 'debit',
        category: t.category || t.category_code,
        transaction_date: t.transaction_date || t.txn_date,
        description: t.description,
        subcategory: t.subcategory || t.subcategory_code,
      })))
      
      // Reload stats
      const stats = await apiClient.getSpendingStats('month')
      setStatsData({
        total_spending: stats.total_spending || 0,
        total_income: stats.total_income || 0,
        net_flow: stats.net_flow || 0,
        cumulative_balance: stats.cumulative_balance ?? stats.net_flow ?? 0,
        transaction_count: stats.transaction_count || 0,
      })
      
      setSuccess('Transaction added successfully')
    } catch (e) {
      console.error('Failed to reload data after adding transaction:', e)
    }
  }

  const onConnectGmail = async () => {
    setError(null)
    setSuccess(null)

    // Always start OAuth flow to add a new account (even if already connected)
    // This allows users to add multiple accounts
    try {
      setLoading(true)
      const auth = await startGmailOAuth() // opens popup synchronously
      if (!auth) {
        setError('Gmail connection cancelled')
        setLoading(false)
        return
      }

      if (auth.mode === 'code') {
        await apiClient.exchangeGmailCode(auth.value)
      } else { // token fallback
        await apiClient.connectGmail(auth.value)
      }

      // After connecting, optionally sync the new account
      const res = await apiClient.syncGmail()
      setGmailConnected(true)
      setSuccess(`Gmail connected. ${res?.transactions_extracted ?? 0} transactions extracted.`)
      
      // Reload connections list
      const connectionsRes = await apiClient.listGmailConnections()
      setGmailConnections(connectionsRes?.connections || [])
    } catch (e) {
      const error = e as Error & { detail?: string }
      setError(error?.detail || error?.message || 'Gmail connect failed')
    } finally {
      setLoading(false)
    }
  }

  const loadGoogleIdentityServices = (): Promise<void> => {
    return new Promise((resolve, reject) => {
      // Check if already loaded
      if (window.google?.accounts?.oauth2) {
        resolve()
        return
      }
      
      // Check if script is already being loaded
      const existingScript = document.querySelector('script[src*="accounts.google.com/gsi/client"]')
      if (existingScript) {
        // Wait for existing script to load
        const checkInterval = setInterval(() => {
          if (window.google?.accounts?.oauth2) {
            clearInterval(checkInterval)
            resolve()
          }
        }, 100)
        
        // Timeout after 5 seconds
        setTimeout(() => {
          clearInterval(checkInterval)
          if (!window.google?.accounts?.oauth2) {
            reject(new Error('Google Identity Services failed to load'))
          }
        }, 5000)
        return
      }
      
      // Load script dynamically
      const script = document.createElement('script')
      script.src = 'https://accounts.google.com/gsi/client'
      script.async = true
      script.defer = true
      script.onload = () => {
        // Wait for Google object to be available
        const checkInterval = setInterval(() => {
          if (window.google?.accounts?.oauth2) {
            clearInterval(checkInterval)
            resolve()
          }
        }, 100)
        
        // Timeout after 5 seconds
        setTimeout(() => {
          clearInterval(checkInterval)
          if (!window.google?.accounts?.oauth2) {
            reject(new Error('Google Identity Services failed to initialize'))
          }
        }, 5000)
      }
      script.onerror = () => {
        reject(new Error('Failed to load Google Identity Services script'))
      }
      document.head.appendChild(script)
    })
  }

  const startGmailOAuth = async (): Promise<{ mode: 'code'|'token'; value: string } | null> => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
    if (!clientId) {
      alert('Missing VITE_GOOGLE_CLIENT_ID')
      return null
    }

    // Ensure script is loaded, but don't block the gesture if it already loaded
    await loadGoogleIdentityServices()

    return await new Promise((resolve) => {
      try {
        // Prefer Authorization Code flow (refreshable)
        // @ts-expect-error GIS runtime provided
        const codeClient = window.google!.accounts.oauth2.initCodeClient({
          client_id: clientId,
          scope: 'https://www.googleapis.com/auth/gmail.readonly openid email profile',
          redirect_uri: 'postmessage',
          prompt: 'select_account',  // forces account chooser (allows selecting different account)
          ux_mode: 'popup',
          callback: (resp: { code?: string; error?: string }) => {
            if (resp?.code) {
              console.log('✅ Code client received authorization code')
              return resolve({ mode: 'code', value: resp.code })
            }
            // Fallback to token client if code flow fails (rare)
            console.warn('Code client failed, trying token client fallback')
            const tokenClient = window.google!.accounts.oauth2.initTokenClient({
              client_id: clientId,
              scope: 'https://www.googleapis.com/auth/gmail.readonly',
              callback: (r: { access_token?: string }) => {
                resolve(r?.access_token ? { mode: 'token', value: r.access_token } : null)
              },
              error_callback: () => resolve(null)
            })
            tokenClient.requestAccessToken()
          }
        })

        // IMPORTANT: call immediately in the same click tick (no awaits before this!)
        console.log('🚀 Requesting authorization code (popup should open immediately)...')
        codeClient.requestCode()
      } catch (e) {
        console.error('GIS init failed', e)
        resolve(null)
      }
    })
  }


  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold text-foreground mb-2 tracking-tight">Monytix Console</h1>
          <p className="text-muted-foreground text-lg">Your financial command center</p>
        </div>
        <button 
          onClick={() => setAddDialogOpen(true)}
          className="btn-primary flex items-center gap-2"
        >
          <span>Add Transaction</span>
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat, index) => (
          <div 
            key={stat.name} 
            className="card-modern p-6 relative overflow-hidden group"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            {/* Gradient accent */}
            <div className={`absolute top-0 right-0 w-32 h-32 rounded-full blur-2xl opacity-20 ${
              stat.trend === 'up' ? 'bg-success' : 'bg-destructive'
            }`}></div>
            
            <div className="flex items-center justify-between relative z-10">
              <div className="flex-1">
                <p className="text-sm font-medium text-muted-foreground mb-2">{stat.name}</p>
                <p className="text-3xl font-bold text-foreground mb-2">{stat.value}</p>
                <div className={`flex items-center text-sm font-medium ${
                  stat.trend === 'up' ? 'text-success' : 'text-destructive'
                }`}>
                  {stat.trend === 'up' ? (
                    <ArrowUp className="h-4 w-4 mr-1" />
                  ) : (
                    <ArrowDown className="h-4 w-4 mr-1" />
                  )}
                  {stat.change}
                </div>
              </div>
              <div className={`p-4 rounded-xl bg-gradient-to-br ${
                stat.trend === 'up' 
                  ? 'from-success/20 to-success/5' 
                  : 'from-destructive/20 to-destructive/5'
              } group-hover:scale-110 transition-transform duration-200`}>
                <stat.icon className={`h-7 w-7 ${
                  stat.trend === 'up' ? 'text-success' : 'text-destructive'
                }`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Transactions */}
      <div className="card-modern mb-8">
        <div className="p-6 border-b border-border">
          <h2 className="text-xl font-semibold text-foreground">Recent Transactions</h2>
        </div>
        <div className="divide-y divide-border">
          {recentTransactions.map((transaction) => (
            <div key={transaction.id} className="p-6 hover:bg-secondary/50 transition-all duration-200 group">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4 flex-1">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center shadow-lg transition-transform group-hover:scale-110 ${
                    transaction.direction === 'credit' 
                      ? 'bg-gradient-to-br from-success/20 to-success/5' 
                      : 'bg-gradient-to-br from-destructive/20 to-destructive/5'
                  }`}>
                    {transaction.direction === 'credit' ? (
                      <ArrowUp className="h-6 w-6 text-success" />
                    ) : (
                      <ArrowDown className="h-6 w-6 text-destructive" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-semibold text-foreground truncate">{transaction.merchant || transaction.description || 'Transaction'}</p>
                      <span className={`font-bold text-base ml-4 ${
                        transaction.direction === 'credit' ? 'text-success' : 'text-destructive'
                      }`}>
                        {transaction.direction === 'credit' ? '+' : ''}₹{Math.abs(transaction.amount).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
                      <span className="px-2 py-1 rounded-md bg-secondary/50 text-xs font-medium">
                        {transaction.category || '—'}{transaction.subcategory ? ` • ${transaction.subcategory}` : ''}
                      </span>
                      {transaction.transaction_date && (
                        <>
                          <span className="text-muted-foreground/50">•</span>
                          <span>{new Date(transaction.transaction_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
                        </>
                      )}
                    </div>
                    {transaction.description && (
                      <p className="text-xs text-muted-foreground/70 line-clamp-1 mt-2">{transaction.description}</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="card-modern p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-primary/10 rounded-full blur-2xl"></div>
          <div className="relative z-10">
            <h3 className="font-semibold text-foreground mb-2 text-lg">Connect Email Accounts</h3>
            <p className="text-sm text-muted-foreground mb-4">
              {gmailConnections.length > 0 ? `${gmailConnections.length} account(s) connected` : 'Automatically sync transactions from emails'}
            </p>
            <button 
              onClick={onConnectGmail} 
              className="btn-primary text-sm px-4 py-2.5" 
              disabled={loading}
            >
              {loading ? 'Connecting…' : gmailConnections.length > 0 ? 'Add Another Account' : 'Connect Gmail'}
            </button>
          </div>
        </div>
        <div className="card-modern p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-accent/10 rounded-full blur-2xl"></div>
          <div className="relative z-10">
            <h3 className="font-semibold text-foreground mb-2 text-lg">Upload Statement</h3>
            <p className="text-sm text-muted-foreground mb-4">PDF, CSV, or Excel (XLS/XLSX) file</p>
            <input ref={fileInputRef} type="file" accept=".csv,.pdf,.xls,.xlsx" className="hidden" onChange={onFileSelected} />
            <button 
              onClick={onClickUpload} 
              className="px-4 py-2.5 rounded-lg text-sm font-semibold bg-accent text-accent-foreground hover:bg-accent/90 transition-all duration-200 shadow-lg shadow-accent/20 hover:shadow-xl hover:shadow-accent/30 disabled:opacity-60" 
              disabled={loading}
            >
              {loading ? 'Uploading…' : 'Upload File'}
            </button>
          </div>
        </div>
        <div className="card-modern p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-success/10 rounded-full blur-2xl"></div>
          <div className="relative z-10">
            <h3 className="font-semibold text-foreground mb-2 text-lg">Set Budget</h3>
            <p className="text-sm text-muted-foreground mb-4">Track your spending limits</p>
            <button className="px-4 py-2.5 rounded-lg text-sm font-semibold bg-success text-success-foreground hover:bg-success/90 transition-all duration-200 shadow-lg shadow-success/20 hover:shadow-xl hover:shadow-success/30">
              Create Budget
            </button>
          </div>
        </div>
      </div>

      {/* Gmail Connections List */}
      {gmailConnections.length > 0 && (
        <div className="card-modern p-6 mb-8">
          <h3 className="font-semibold text-foreground mb-6 text-lg">Connected Email Accounts</h3>
          <div className="space-y-3">
            {gmailConnections.map((conn) => (
              <div key={conn.id} className="flex items-center justify-between p-4 rounded-xl border border-border bg-secondary/30 hover:bg-secondary/50 transition-all duration-200 group">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="font-semibold text-foreground truncate">
                      {conn.display_name || conn.email || 'Unknown Account'}
                    </span>
                    {conn.is_active ? (
                      <span className="px-2.5 py-1 text-xs rounded-full bg-success/20 text-success font-medium border border-success/30">Active</span>
                    ) : (
                      <span className="px-2.5 py-1 text-xs rounded-full bg-muted text-muted-foreground font-medium border border-border">Inactive</span>
                    )}
                  </div>
                  {conn.email && (
                    <p className="text-sm text-muted-foreground mb-2 truncate">{conn.email}</p>
                  )}
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <span className="font-medium">{conn.total_transactions_extracted} transactions</span>
                    {conn.last_sync_at && (
                      <span>Last synced: {new Date(conn.last_sync_at).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>
                <div className="flex gap-2 ml-4">
                  <button
                    onClick={async () => {
                      try {
                        setLoading(true)
                        await apiClient.syncGmailConnection(conn.id)
                        setSuccess(`Syncing ${conn.display_name || conn.email}...`)
                        // Reload connections after a delay
                        setTimeout(async () => {
                          const connectionsRes = await apiClient.listGmailConnections()
                          setGmailConnections(connectionsRes?.connections || [])
                        }, 2000)
                      } catch (e) {
                        const error = e as Error & { detail?: string }
                        setError(error?.detail || error?.message || 'Sync failed')
                      } finally {
                        setLoading(false)
                      }
                    }}
                    className="px-4 py-2 text-sm rounded-lg bg-primary/10 text-primary hover:bg-primary/20 font-medium transition-all duration-200 disabled:opacity-60 hover:scale-105"
                    disabled={loading}
                  >
                    Sync
                  </button>
                  <button
                    onClick={async () => {
                      if (confirm(`Remove ${conn.display_name || conn.email}?`)) {
                        try {
                          setLoading(true)
                          await apiClient.deleteGmailConnection(conn.id)
                          setSuccess(`Removed ${conn.display_name || conn.email}`)
                          // Reload connections
                          const connectionsRes = await apiClient.listGmailConnections()
                          setGmailConnections(connectionsRes?.connections || [])
                          const status = await apiClient.gmailStatus()
                          setGmailConnected(status?.active || false)
                        } catch (e) {
                          const error = e as Error & { detail?: string }
                          setError(error?.detail || error?.message || 'Delete failed')
                        } finally {
                          setLoading(false)
                        }
                      }
                    }}
                    className="px-4 py-2 text-sm rounded-lg bg-destructive/10 text-destructive hover:bg-destructive/20 font-medium transition-all duration-200 disabled:opacity-60 hover:scale-105"
                    disabled={loading}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Status Messages */}
      {error && (
        <div className="rounded-xl bg-destructive/10 border border-destructive/30 text-destructive p-4 mb-4 flex items-center gap-3 shadow-lg">
          <div className="h-5 w-5 rounded-full bg-destructive/20 flex items-center justify-center flex-shrink-0">
            <span className="text-xs">!</span>
          </div>
          <span className="font-medium">{error}</span>
        </div>
      )}
      {success && (
        <div className="rounded-xl bg-success/10 border border-success/30 text-success p-4 mb-4 flex items-center gap-3 shadow-lg">
          <div className="h-5 w-5 rounded-full bg-success/20 flex items-center justify-center flex-shrink-0">
            <span className="text-xs">✓</span>
          </div>
          <span className="font-medium">{success}</span>
        </div>
      )}

      <PasswordDialog
        isOpen={showPasswordDialog}
        onClose={() => setShowPasswordDialog(false)}
        onConfirm={onConfirmPdfPassword}
        fileName={pendingPdfInfo?.file?.name || ''}
        bank={pendingPdfInfo?.bank || ''}
      />

      <TransactionAddDialog
        isOpen={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
        onSuccess={handleAddTransactionSuccess}
      />
    </div>
  )
}

