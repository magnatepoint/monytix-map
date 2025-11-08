import { useState, useEffect, useMemo } from 'react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { TrendingUp, AlertCircle, Target } from 'lucide-react'
import { apiClient } from '../lib/api'
import TransactionEditDialog, { type TransactionData } from '../components/TransactionEditDialog'
import TransactionAddDialog from '../components/TransactionAddDialog'
import CalendarDatePicker from '../components/CalendarDatePicker'

interface CategoryData {
  name: string
  value: number
  color: string
}

export default function SpendSense() {
  const [loading, setLoading] = useState(true)
  const [categoryData, setCategoryData] = useState<CategoryData[]>([
    { name: 'Food & Dining', value: 12000, color: '#F4D03F' },
    { name: 'Shopping', value: 8500, color: '#8B5CF6' },
    { name: 'Transport', value: 5600, color: '#10B981' },
    { name: 'Bills & Utilities', value: 4300, color: '#F59E0B' },
    { name: 'Entertainment', value: 2100, color: '#EF4444' },
    { name: 'Healthcare', value: 1500, color: '#06B6D4' },
  ])

  const [stats, setStats] = useState<{
    total_spending: number
    top_category: string
    budget_status: number
  }>({
    total_spending: 34400,
    top_category: 'Food',
    budget_status: 68
  })

  const [monthlyData, setMonthlyData] = useState<Array<{
    month: string
    spending: number
    budget: number
  }>>([
    { month: 'Jan', spending: 42000, budget: 50000 },
    { month: 'Feb', spending: 38000, budget: 50000 },
    { month: 'Mar', spending: 45000, budget: 50000 },
    { month: 'Apr', spending: 39000, budget: 50000 },
  ])

  const [insights, setInsights] = useState([
    { type: 'high_spending', category: 'Food & Dining', message: 'You\'re spending 40% more on food this month' },
    { type: 'good_trend', category: 'Transport', message: 'Your transport costs decreased by 15%' },
    { type: 'budget_alert', category: 'Shopping', message: 'You\'ve used 85% of your shopping budget' },
  ])

  // Colors for pie chart - memoized to avoid dependency issues
  const COLORS = useMemo(() => ['#F4D03F', '#D4AF37', '#F97316', '#8B5CF6', '#84CC16', '#0FB9B1'], [])

  // Spending distribution view: amount (INR) or percent
  const [distMode, setDistMode] = useState<'amount'|'percent'>('amount')
  const [topN] = useState<number>(6)
  const [rawCats, setRawCats] = useState<Array<{category: string; amount: number}>>([])
  const [totalAmt, setTotalAmt] = useState<number>(0)

  useEffect(() => {
    loadSpendSenseData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadSpendSenseData = async () => {
    try {
      setLoading(true)

      // We will compute the top cards directly from distribution below to
      // ensure consistency with the visible breakdown (independent of MV state)

      // Load category breakdown
      const catResp = await apiClient.getSpendingByCategory('month')
      interface CategoryItem {
        category: string
        amount: number
      }
      const total = catResp.total || catResp.categories.reduce((s: number, c: CategoryItem) => s + (c.amount || 0), 0)
      const raw = catResp.categories.map((c: CategoryItem) => ({ category: c.category || 'Uncategorized', amount: c.amount || 0 }))
      setRawCats(raw)
      setTotalAmt(total)
      // Compute initial distribution based on current distMode/topN
      const compute = (cats: Array<{category: string; amount: number}>, t: number): CategoryData[] => {
        const sorted = [...cats].sort((a, b) => b.amount - a.amount)
        const head = sorted.slice(0, topN)
        const tail = sorted.slice(topN)
        const othersAmt = tail.reduce((s, c) => s + c.amount, 0)
        const base = head.map((cat, idx) => ({
          name: cat.category,
          value: distMode === 'amount' ? cat.amount : Math.round(((cat.amount || 0) / (t || 1)) * 100),
          color: COLORS[idx % COLORS.length]
        }))
        if (othersAmt > 0) base.push({ name: 'Others', value: distMode === 'amount' ? othersAmt : Math.round((othersAmt / (t || 1)) * 100), color: '#64748B' })
        return base
      }
      setCategoryData(compute(raw, total))
      // Update top cards from same data source for coherence
      const topCatName = raw.sort((a,b)=>b.amount-a.amount)[0]?.category || '—'
      setStats({
        total_spending: total,
        top_category: topCatName,
        budget_status: Math.min((total / 50000) * 100, 100)
      })
      // Save raw for ranking card (for future use)
      // const ranked = raw.sort((a,b)=>b.amount-a.amount).map(c => ({ category: c.category, amount: c.amount, percent: total ? c.amount/total : 0 }))
      // setRankItems(ranked)

      // Load insights
      const insightsData = await apiClient.getInsights()
      setInsights(insightsData.insights)

      // Load trends
      const trendsData = await apiClient.getSpendingTrends('3months')
      const formattedTrends = trendsData.trends.map(trend => ({
        month: new Date(trend.date).toLocaleDateString('en-US', { month: 'short' }),
        spending: trend.spending,
        budget: 50000 // Default budget
      }))
      setMonthlyData(formattedTrends)

    } catch (error) {
      console.error('Error loading SpendSense data:', error)
      // Keep default data on error
    } finally {
      setLoading(false)
    }
  }

  // const [rankItems, setRankItems] = useState<Array<{category: string; amount: number; percent: number}>>([])

  // Recompute distribution when mode/topN changes
  useEffect(() => {
    if (!rawCats.length) return
    const sorted = [...rawCats].sort((a, b) => b.amount - a.amount)
    const head = sorted.slice(0, topN)
    const tail = sorted.slice(topN)
    const othersAmt = tail.reduce((s, c) => s + c.amount, 0)
    const base: CategoryData[] = head.map((cat, idx) => ({
      name: cat.category,
      value: distMode === 'amount' ? cat.amount : Math.round(((cat.amount || 0) / (totalAmt || 1)) * 100),
      color: COLORS[idx % COLORS.length]
    }))
    if (othersAmt > 0) base.push({ name: 'Others', value: distMode === 'amount' ? othersAmt : Math.round((othersAmt / (totalAmt || 1)) * 100), color: '#64748B' })
    setCategoryData(base)
  }, [distMode, topN, rawCats, totalAmt, COLORS])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold text-foreground mb-2 tracking-tight">SpendSense</h1>
          <p className="text-muted-foreground text-lg">AI-powered spending insights & analytics</p>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="card-modern p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-full blur-2xl"></div>
          <div className="flex items-center justify-between relative z-10">
            <div className="flex-1">
              <p className="text-sm font-medium text-muted-foreground mb-2">Total Spending</p>
              <p className="text-3xl font-bold text-foreground">₹{stats.total_spending.toLocaleString()}</p>
            </div>
            <div className="p-4 rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 group-hover:scale-110 transition-transform duration-200">
              <TrendingUp className="h-7 w-7 text-primary" />
            </div>
          </div>
        </div>
        <div className="card-modern p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-accent/10 rounded-full blur-2xl"></div>
          <div className="flex items-center justify-between relative z-10">
            <div className="flex-1">
              <p className="text-sm font-medium text-muted-foreground mb-2">Top Category</p>
              <p className="text-3xl font-bold text-foreground">{stats.top_category}</p>
            </div>
            <div className="p-4 rounded-xl bg-gradient-to-br from-accent/20 to-accent/5 group-hover:scale-110 transition-transform duration-200">
              <Target className="h-7 w-7 text-accent" />
            </div>
          </div>
        </div>
        <div className="card-modern p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-success/10 rounded-full blur-2xl"></div>
          <div className="flex items-center justify-between relative z-10">
            <div className="flex-1">
              <p className="text-sm font-medium text-muted-foreground mb-2">Budget Status</p>
              <p className="text-3xl font-bold text-success">{Math.round(stats.budget_status)}%</p>
            </div>
            <div className="p-4 rounded-xl bg-gradient-to-br from-success/20 to-success/5 group-hover:scale-110 transition-transform duration-200">
              <AlertCircle className="h-7 w-7 text-success" />
            </div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Category Distribution */}
        <div className="card-modern p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-foreground">Spending by Category</h2>
            <div className="flex items-center gap-2 bg-secondary/50 rounded-lg p-1">
              <button
                onClick={() => setDistMode('amount')}
                className={`px-3 py-1.5 text-xs rounded-md font-medium transition-all duration-200 ${
                  distMode==='amount' 
                    ? 'bg-primary text-primary-foreground shadow-sm' 
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >INR</button>
              <button
                onClick={() => setDistMode('percent')}
                className={`px-3 py-1.5 text-xs rounded-md font-medium transition-all duration-200 ${
                  distMode==='percent' 
                    ? 'bg-primary text-primary-foreground shadow-sm' 
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >%</button>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={categoryData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value }) => distMode==='amount' ? `${name}: ₹${Number(value).toLocaleString()}` : `${name}: ${value}%`}
                outerRadius={80}
                fill="#F4D03F"
                dataKey="value"
              >
                {categoryData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          {/* Ranked list removed per request */}
        </div>

        {/* Monthly Trend */}
        <div className="card-modern p-6">
          <h2 className="text-xl font-semibold text-foreground mb-6">Monthly Trend</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={monthlyData}>
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="spending" fill="#F4D03F" name="Spending" />
              <Bar dataKey="budget" fill="#8B5CF6" name="Budget" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* AI Insights */}
      <div className="card-modern mb-8">
        <div className="p-6 border-b border-border">
          <h2 className="text-xl font-semibold text-foreground">AI Insights</h2>
        </div>
        <div className="divide-y divide-border">
          {insights.map((insight, index) => (
            <div key={index} className="p-6 hover:bg-secondary/30 transition-colors duration-200 group">
              <div className="flex items-start space-x-4">
                <div className="p-3 rounded-xl bg-gradient-to-br from-info/20 to-info/5 group-hover:scale-110 transition-transform duration-200">
                  <AlertCircle className="h-6 w-6 text-info" />
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-foreground mb-1">{insight.category}</p>
                  <p className="text-sm text-muted-foreground">{insight.message}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Transactions (CRUD + Pagination) */}
      <TransactionsSection />
    </div>
  )
}

interface TransactionItem {
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

function TransactionsSection() {
  const [items, setItems] = useState<TransactionItem[]>([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(0)
  const pageSize = 10
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [selectedTransaction, setSelectedTransaction] = useState<TransactionItem | null>(null)
  
  // Filters
  const [filters, setFilters] = useState<{
    category?: string
    startDate?: string
    endDate?: string
    direction?: 'all' | 'credit' | 'debit'
  }>({
    direction: 'all'
  })
  const [categories, setCategories] = useState<Array<{category_code: string; category_name: string}>>([])

  // Load categories for filter dropdown
  useEffect(() => {
    const loadCategories = async () => {
      try {
        const cats = await apiClient.getCategories()
        setCategories(cats || [])
      } catch (e) {
        console.error('Failed to load categories:', e)
      }
    }
    loadCategories()
  }, [])

  const load = async () => {
    setLoading(true)
    try {
      const response = await apiClient.getTransactions(
        page * pageSize, 
        pageSize,
        filters.category,
        filters.startDate,
        filters.endDate
      )
      // Handle both old format (array) and new format (TransactionListResponse with data field)
      // Handle both old format (array) and new format (object with data field)
      const data = Array.isArray(response) ? response : ((response as any)?.data || [])
      
      // Apply direction filter on frontend if needed (backend doesn't support it)
      let filtered = Array.isArray(data) ? data : []
      if (filters.direction && filters.direction !== 'all') {
        filtered = filtered.filter((t: any) => 
          (t.direction || t.transaction_type) === filters.direction
        )
      }
      setItems(filtered)
    } catch (error) {
      console.error('Error loading transactions:', error)
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  // Reset page when filters change
  useEffect(() => {
    setPage(0)
  }, [filters.category, filters.startDate, filters.endDate, filters.direction])

  useEffect(() => { 
    load() 
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, filters.category, filters.startDate, filters.endDate, filters.direction])

  const onAdd = () => {
    setAddDialogOpen(true)
  }

  const handleAddSuccess = async () => {
    await load()
  }

  const handleEdit = (transaction: TransactionItem) => {
    setSelectedTransaction(transaction)
    setEditDialogOpen(true)
  }

  const handleSaveEdit = async (updates: {
    description?: string
    merchant?: string
    amount?: number
    direction?: 'credit' | 'debit' | 'credit_card'
    transaction_type?: 'credit' | 'debit'
    category?: string
    category_code?: string
    subcategory?: string
    subcategory_code?: string
    transaction_date?: string
    currency?: string
    payment_method?: string
  }) => {
    if (!selectedTransaction) return
    
    const id = selectedTransaction.id || selectedTransaction.txn_id
    if (!id) return

    try {
      // Map updates to API format
      const apiUpdates: {
        description?: string
        merchant?: string
        amount?: number
        transaction_type?: string
        category?: string
        subcategory?: string
        transaction_date?: string
        currency?: string
        payment_method?: string
      } = {}

      if (updates.description !== undefined) apiUpdates.description = updates.description
      if (updates.merchant !== undefined) apiUpdates.merchant = updates.merchant
      if (updates.amount !== undefined) apiUpdates.amount = updates.amount
      if (updates.direction !== undefined || updates.transaction_type !== undefined) {
        // Handle credit_card type - store as debit with payment_method
        if (updates.direction === 'credit_card') {
          apiUpdates.transaction_type = 'debit'
          apiUpdates.payment_method = 'credit_card'
        } else {
          apiUpdates.transaction_type = (updates.direction || updates.transaction_type) || 'debit'
        }
      }
      if (updates.category !== undefined || updates.category_code !== undefined) {
        apiUpdates.category = updates.category || updates.category_code
      }
      if (updates.subcategory !== undefined || updates.subcategory_code !== undefined) {
        apiUpdates.subcategory = updates.subcategory || updates.subcategory_code
      }
      if (updates.transaction_date !== undefined) apiUpdates.transaction_date = updates.transaction_date
      if (updates.currency !== undefined) apiUpdates.currency = updates.currency

      await apiClient.updateTransaction(id, apiUpdates)
      await load()
      setEditDialogOpen(false)
      setSelectedTransaction(null)
    } catch (error) {
      console.error('Error updating transaction:', error)
      alert('Failed to update transaction. Please try again.')
    }
  }

  const onDelete = async (id: string) => {
    if (!window.confirm('Delete this transaction?')) return
    try {
      await apiClient.deleteTransaction(id)
      await load()
    } catch (error) {
      console.error('Error deleting transaction:', error)
      alert('Failed to delete transaction. Please try again.')
    }
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '—'
    try {
      const date = new Date(dateStr)
      return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
    } catch {
      return dateStr
    }
  }

  const resetFilters = () => {
    setFilters({ direction: 'all' })
    setPage(0)
  }

  return (
    <div className="card-modern">
      <div className="p-6 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-foreground">Transactions</h2>
          <button onClick={onAdd} className="btn-primary text-sm px-4 py-2.5">Add</button>
        </div>
        
        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-4">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Category</label>
            <select
              value={filters.category || ''}
              onChange={(e) => setFilters({ ...filters, category: e.target.value || undefined })}
              className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground"
            >
              <option value="">All Categories</option>
              {categories.map(cat => (
                <option key={cat.category_code} value={cat.category_code}>
                  {cat.category_name}
                </option>
              ))}
            </select>
          </div>
          
          <CalendarDatePicker
            label="Start Date"
            value={filters.startDate}
            onChange={(date) => setFilters({ ...filters, startDate: date })}
            placeholder="Select start date"
          />
          
          <CalendarDatePicker
            label="End Date"
            value={filters.endDate}
            onChange={(date) => setFilters({ ...filters, endDate: date })}
            placeholder="Select end date"
          />
          
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Type</label>
            <select
              value={filters.direction || 'all'}
              onChange={(e) => setFilters({ ...filters, direction: e.target.value as 'all' | 'credit' | 'debit' })}
              className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground"
            >
              <option value="all">All</option>
              <option value="debit">Debit</option>
              <option value="credit">Credit</option>
            </select>
          </div>
        </div>
        
        {(filters.category || filters.startDate || filters.endDate || filters.direction !== 'all') && (
          <button
            onClick={resetFilters}
            className="mt-3 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground border border-border rounded-md hover:bg-secondary transition-colors"
          >
            Reset Filters
          </button>
        )}
      </div>
      <div className="divide-y divide-border">
        {items.map((t) => {
          // Get merchant name (clean, not the full UPI string)
          // Try merchant_name_norm first, then merchant, then extract from description
          let merchantName = t.merchant_name_norm || t.merchant
          
          // If no merchant, try to extract from description (for UPI transactions)
          if (!merchantName && t.description) {
            // Extract merchant from UPI format: "UPI-MERCHANT-..."
            const upiMatch = t.description.match(/UPI-([A-Z][A-Z\s]+?)(?:-|@)/i)
            if (upiMatch && upiMatch[1]) {
              merchantName = upiMatch[1].trim()
            }
          }
          
          if (!merchantName) {
            merchantName = 'Unknown'
          }
          
          // Get category/subcategory display
          const category = t.category || t.category_code || 'others'
          const subcategory = t.subcategory || t.subcategory_code
          const categoryDisplay = subcategory ? `${category} · ${subcategory}` : category
          
          const txnDate = t.transaction_date || t.txn_date
          const formattedDate = formatDate(txnDate)
          
          return (
            <div key={t.id || t.txn_id} className="p-4 flex items-center justify-between hover:bg-secondary transition-colors">
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <p className="font-medium text-foreground">{merchantName}</p>
                  <span className={`font-semibold text-sm ${
                    (t.direction === 'credit' || t.transaction_type === 'credit') ? 'text-success' : 'text-destructive'
                  }`}>
                    {(t.direction === 'credit' || t.transaction_type === 'credit') ? '+' : ''}₹{Math.abs(Number(t.amount ?? 0)).toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>{categoryDisplay}</span>
                  {txnDate && (
                    <>
                      <span>•</span>
                      <span>{formattedDate}</span>
                    </>
                  )}
                </div>
              </div>
              <div className="flex items-center space-x-3 ml-4">
                <button onClick={() => handleEdit(t)} className="text-primary text-sm hover:underline">Edit</button>
                <button onClick={() => {
                  const id = t.id || t.txn_id
                  if (id) onDelete(id)
                }} className="text-destructive text-sm hover:underline">Delete</button>
              </div>
            </div>
          )
        })}
        {loading && (
          <div className="p-6 text-sm text-muted-foreground text-center">Loading transactions...</div>
        )}
        {!loading && items.length === 0 && (
          <div className="p-6 text-sm text-muted-foreground text-center">
            {filters.category || filters.startDate || filters.endDate || filters.direction !== 'all' 
              ? 'No transactions match the selected filters.' 
              : 'No transactions found.'}
          </div>
        )}
      </div>
      <div className="p-4 flex items-center justify-between">
        <button className="px-3 py-1.5 border border-border rounded-md text-sm" onClick={() => setPage(p => Math.max(0, p-1))} disabled={page===0}>Previous</button>
        <span className="text-sm text-muted-foreground">Page {page+1}</span>
        <button className="px-3 py-1.5 border border-border rounded-md text-sm" onClick={() => setPage(p => p+1)}>Next</button>
      </div>

      {/* Edit Dialog */}
      <TransactionEditDialog
        isOpen={editDialogOpen}
        onClose={() => {
          setEditDialogOpen(false)
          setSelectedTransaction(null)
        }}
        onSave={handleSaveEdit}
        transaction={selectedTransaction as TransactionData | null}
      />

      {/* Add Dialog */}
      <TransactionAddDialog
        isOpen={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
        onSuccess={handleAddSuccess}
      />
    </div>
  )
}

