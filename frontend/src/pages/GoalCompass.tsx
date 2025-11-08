import { useState, useEffect, useMemo } from 'react'
import { Target, AlertTriangle, CheckCircle2, RefreshCw, ChevronDown, ChevronUp, Edit2, X, Plus, Save } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { apiClient } from '../lib/api'

// Types
interface GoalProgress {
  goal_id: string
  goal_name: string
  goal_category: string
  goal_type: string
  progress_pct: number
  progress_amount: number
  remaining_amount: number
  months_remaining: number | null
  suggested_monthly_need: number
  on_track_flag: boolean
  risk_level: 'low' | 'medium' | 'high'
  commentary: string
}

interface Dashboard {
  month: string
  active_goals_count: number
  avg_progress_pct: number
  total_remaining_amount: number
  goals_on_track_count: number
  goals_high_risk_count: number
}

interface GoalCard {
  goal_id: string
  name: string
  progress_pct: number
  remaining: number
  on_track: boolean
  risk: 'low' | 'medium' | 'high'
  suggested_monthly: number
}

type CatalogItem = {
  goal_category: string
  goal_name: string
  default_horizon: 'short_term' | 'medium_term' | 'long_term' | string
  policy_linked_txn_type: 'needs' | 'wants' | 'assets'
  auto_suggest?: string | null
  recommended?: boolean
  context_hint?: string | null
}

type Catalog = {
  short: CatalogItem[]
  medium: CatalogItem[]
  long: CatalogItem[]
}

type Selection = {
  [key: string]: { estimated_cost: number; target_date?: string; current_savings: number; notes?: string }
}

type Tab = 'setup' | 'create' | 'track'
type Filter = 'all' | 'short' | 'medium' | 'long'

interface PortfolioGoal {
  goal_id: string
  goal_category: string
  goal_name: string
  goal_type: string
  priority_rank: number | null
  linked_txn_type: string
  estimated_cost: number
  current_savings: number
  target_date: string | null
  funding_gap: number
}

export default function GoalCompass() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState<Tab>('setup')
  
  // Track Progress state
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [goals, setGoals] = useState<GoalProgress[]>([])
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [insights, setInsights] = useState<GoalCard[]>([])
  const [selectedMonth, setSelectedMonth] = useState(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
  })
  
  // Setup state
  const [contextExpanded, setContextExpanded] = useState(false)
  const [context, setContext] = useState({
    age_band: '25-34',
    dependents_spouse: false,
    dependents_children_count: 0,
    dependents_parents_care: false,
    housing: 'rent',
    employment: 'salaried',
    income_regularity: 'stable',
    region_code: 'IN-KA',
    emergency_opt_out: false
  })
  
  // Create Goals state
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [selected, setSelected] = useState<Selection>({})
  const [portfolio, setPortfolio] = useState<PortfolioGoal[] | null>(null)
  const [portfolioLoading, setPortfolioLoading] = useState(false)
  
  // Edit modal state
  const [editModal, setEditModal] = useState<{ open: boolean; goal: PortfolioGoal | null }>({ open: false, goal: null })
  const [editForm, setEditForm] = useState({
    estimated_cost: 0,
    current_savings: 0,
    target_date: '',
    notes: ''
  })
  
  // Messages
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  // Load context on mount
  useEffect(() => {
    loadContext()
  }, [])

  // Load catalog and portfolio when Create tab is active
  useEffect(() => {
    if (activeTab === 'create') {
      loadCatalog()
      loadPortfolio()
    }
  }, [activeTab])

  // Load progress data when Track tab is active
  useEffect(() => {
    if (activeTab === 'track') {
      loadGoalCompassData()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, selectedMonth])

  async function loadContext() {
    try {
      const data = await apiClient.getGoalsContext?.() || null
      if (data) {
        setContext({
          age_band: data.age_band || '25-34',
          dependents_spouse: data.dependents_spouse || false,
          dependents_children_count: data.dependents_children_count || 0,
          dependents_parents_care: data.dependents_parents_care || false,
          housing: data.housing || 'rent',
          employment: data.employment || 'salaried',
          income_regularity: data.income_regularity || 'stable',
          region_code: data.region_code || 'IN-KA',
          emergency_opt_out: false
        })
      }
    } catch {
      // Ignore errors, use defaults
    }
  }

  async function loadCatalog() {
    setCatalogLoading(true)
    setError(null)
    try {
      const data = await apiClient.getGoalsCatalog()
      setCatalog(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load catalog')
    } finally {
      setCatalogLoading(false)
    }
  }

  async function loadPortfolio() {
    setPortfolioLoading(true)
    try {
      const data = await apiClient.getGoalsSummary()
      const goals = Array.isArray(data) ? data : (data?.goals || [])
      setPortfolio(goals)
    } catch {
      // Ignore errors in sidebar
    } finally {
      setPortfolioLoading(false)
    }
  }

  const loadGoalCompassData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [progressData, dashboardData, insightsData] = await Promise.all([
        apiClient.getGoalProgress(undefined, selectedMonth).catch(() => ({ goals: [] })),
        apiClient.getGoalDashboard(selectedMonth).catch(() => null),
        apiClient.getGoalInsights(selectedMonth).catch(() => ({ goal_cards: [] }))
      ])

      setGoals(progressData.goals || [])
      setDashboard(dashboardData)
      setInsights(insightsData.goal_cards || [])
    } catch (err: unknown) {
      console.error('Error loading GoalCompass data:', err)
      setError(err instanceof Error ? err.message : 'Failed to load goal data')
    } finally {
      setLoading(false)
    }
  }

  async function saveContext() {
    setCatalogLoading(true)
    setError(null)
    setStatus(null)
    try {
      await apiClient.putGoalsContext(context)
      setStatus('Context saved successfully')
      setTimeout(() => setStatus(null), 3000)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save context')
    } finally {
      setCatalogLoading(false)
    }
  }

  function toggleSelect(item: CatalogItem) {
    const key = `${item.goal_category}::${item.goal_name}`
    setSelected(prev => {
      const next = { ...prev }
      if (next[key]) delete next[key]
      else next[key] = { estimated_cost: 0, current_savings: 0 }
      return next
    })
  }

  async function submitSelection() {
    if (!catalog) return
    const selected_goals = Object.entries(selected).map(([key, v]) => {
      const [goal_category, goal_name] = key.split('::')
      const horizons: ('short' | 'medium' | 'long')[] = ['short', 'medium', 'long']
      const found = horizons.flatMap((k) => catalog[k]).find((c: CatalogItem) => c.goal_category === goal_category && c.goal_name === goal_name)
      const goal_type = found?.default_horizon || 'short_term'
      return {
        goal_category,
        goal_name,
        goal_type,
        estimated_cost: Number(v.estimated_cost) || 0,
        target_date: v.target_date || undefined,
        current_savings: Number(v.current_savings) || 0,
        notes: v.notes || undefined
      }
    })

    const payload = { context, selected_goals }
    setCatalogLoading(true)
    setError(null)
    setStatus(null)
    try {
      const data = await apiClient.submitGoals(payload)
      setStatus(`Goals submitted successfully (${data.created.length})`)
      setSelected({})
      await loadPortfolio()
      setTimeout(() => setStatus(null), 3000)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to submit goals')
    } finally {
      setCatalogLoading(false)
    }
  }

  function openEditModal(goal: PortfolioGoal) {
    setEditModal({ open: true, goal })
    setEditForm({
      estimated_cost: goal.estimated_cost || 0,
      current_savings: goal.current_savings || 0,
      target_date: goal.target_date ? goal.target_date.slice(0, 10) : '',
      notes: ''
    })
  }

  async function saveEdit() {
    if (!editModal.goal) return
    setCatalogLoading(true)
    setError(null)
    setStatus(null)
    try {
      await apiClient.updateGoal(editModal.goal.goal_id, {
        estimated_cost: editForm.estimated_cost,
        current_savings: editForm.current_savings,
        target_date: editForm.target_date || undefined,
        notes: editForm.notes || undefined
      })
      setStatus('Goal updated successfully')
      setEditModal({ open: false, goal: null })
      await loadPortfolio()
      setTimeout(() => setStatus(null), 3000)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update goal')
    } finally {
      setCatalogLoading(false)
    }
  }

  const handleRefresh = async () => {
    try {
      setRefreshing(true)
      setError(null)
      setSuccess(null)

      await apiClient.refreshGoalCompass(selectedMonth)
      setSuccess('GoalCompass refreshed successfully')

      await loadGoalCompassData()
    } catch (err: unknown) {
      console.error('Error refreshing GoalCompass:', err)
      setError(err instanceof Error ? err.message : 'Failed to refresh GoalCompass')
    } finally {
      setRefreshing(false)
    }
  }

  // Filtered catalog
  const filteredCatalog = useMemo(() => {
    if (!catalog) return []
    if (filter === 'all') {
      return [...catalog.short, ...catalog.medium, ...catalog.long]
    }
    return catalog[filter] || []
  }, [catalog, filter])

  const selectedCount = useMemo(() => Object.keys(selected).length, [selected])
  const todayStr = useMemo(() => new Date().toISOString().slice(0,10), [])

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'high': return 'text-red-400 bg-red-400/10 border-red-400/20'
      case 'medium': return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20'
      case 'low': return 'text-green-400 bg-green-400/10 border-green-400/20'
      default: return 'text-gray-400 bg-gray-400/10 border-gray-400/20'
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(amount)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-xl bg-gradient-to-r from-purple-800 to-purple-700 border border-border p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold flex items-center gap-2">
              <Target className="w-6 h-6" />
              GoalCompass
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              Setup, create, and track your financial goals.
            </p>
          </div>
          <div className="text-xs text-muted-foreground">{user?.email}</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab('setup')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'setup'
              ? 'text-primary border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Setup
        </button>
        <button
          onClick={() => setActiveTab('create')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'create'
              ? 'text-primary border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Create Goals
        </button>
        <button
          onClick={() => setActiveTab('track')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'track'
              ? 'text-primary border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Track Progress
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 p-4">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 p-4">
          {success}
        </div>
      )}
      {status && (
        <div className="rounded-lg bg-primary/10 border border-primary/20 text-primary p-4">
          {status}
        </div>
      )}

      {/* Setup Tab */}
      {activeTab === 'setup' && (
        <div className="space-y-4">
          {/* Context Section */}
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <button
              onClick={() => setContextExpanded(!contextExpanded)}
              className="w-full flex items-center justify-between p-4 hover:bg-secondary/50 transition-colors"
            >
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-lg">Life Context</h3>
                <span className="text-xs text-muted-foreground">Set up your personal context for goal recommendations</span>
              </div>
              {contextExpanded ? (
                <ChevronUp className="w-5 h-5 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-5 h-5 text-muted-foreground" />
              )}
            </button>
            
            {contextExpanded && (
              <div className="p-4 border-t border-border space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-muted-foreground">Age band</label>
                    <select
                      value={context.age_band}
                      onChange={e => setContext({...context, age_band: e.target.value})}
                      className="border border-border rounded px-3 py-2 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                    >
                      {['18-24','25-34','35-44','45-54','55+'].map(a => <option key={a} value={a}>{a}</option>)}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-muted-foreground">Dependents: spouse</label>
                    <label className="flex items-center gap-2 text-sm mt-2">
                      <input
                        type="checkbox"
                        checked={context.dependents_spouse}
                        onChange={e => setContext({...context, dependents_spouse: e.target.checked})}
                        className="rounded border-border"
                      />
                      Spouse
                    </label>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-muted-foreground">Children (count)</label>
                    <input
                      type="number"
                      min={0}
                      className="border border-border rounded px-3 py-2 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                      value={context.dependents_children_count}
                      onChange={e => setContext({...context, dependents_children_count: Number(e.target.value) || 0})}
                      placeholder="0"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-muted-foreground">Parents care</label>
                    <label className="flex items-center gap-2 text-sm mt-2">
                      <input
                        type="checkbox"
                        checked={context.dependents_parents_care}
                        onChange={e => setContext({...context, dependents_parents_care: e.target.checked})}
                        className="rounded border-border"
                      />
                      Parents care
                    </label>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-muted-foreground">Housing</label>
                    <select
                      value={context.housing}
                      onChange={e => setContext({...context, housing: e.target.value})}
                      className="border border-border rounded px-3 py-2 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                    >
                      {['rent','own_mortgage','own_nomortgage'].map(v => <option key={v} value={v}>{v}</option>)}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-muted-foreground">Employment</label>
                    <select
                      value={context.employment}
                      onChange={e => setContext({...context, employment: e.target.value})}
                      className="border border-border rounded px-3 py-2 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                    >
                      {['salaried','self_employed','student','homemaker','retired'].map(v => <option key={v} value={v}>{v}</option>)}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-muted-foreground">Income regularity</label>
                    <select
                      value={context.income_regularity}
                      onChange={e => setContext({...context, income_regularity: e.target.value})}
                      className="border border-border rounded px-3 py-2 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                    >
                      {['very_stable','stable','variable'].map(v => <option key={v} value={v}>{v}</option>)}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-muted-foreground">Region code</label>
                    <input
                      className="border border-border rounded px-3 py-2 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                      value={context.region_code}
                      onChange={e => setContext({...context, region_code: e.target.value})}
                      placeholder="IN-KA"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-muted-foreground">Emergency opt-out</label>
                    <label className="flex items-center gap-2 text-sm mt-2">
                      <input
                        type="checkbox"
                        checked={context.emergency_opt_out}
                        onChange={e => setContext({...context, emergency_opt_out: e.target.checked})}
                        className="rounded border-border"
                      />
                      Allow skip
                    </label>
                  </div>
                </div>
                
                <div className="flex justify-end">
                  <button
                    onClick={saveContext}
                    disabled={catalogLoading}
                    className="px-4 py-2 rounded bg-primary text-white disabled:opacity-50 flex items-center gap-2"
                  >
                    <Save className="w-4 h-4" />
                    Save Context
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create Goals Tab */}
      {activeTab === 'create' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Left: Catalog */}
          <div className="xl:col-span-2 space-y-4">
            {/* Filter Chips */}
            <div className="flex gap-2 flex-wrap">
              {(['all', 'short', 'medium', 'long'] as Filter[]).map((f) => {
                const labels: Record<Filter, string> = {
                  all: 'All Goals',
                  short: 'Short Term',
                  medium: 'Medium Term',
                  long: 'Long Term'
                }
                return (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                      filter === f
                        ? 'bg-primary text-white shadow-md'
                        : 'bg-secondary text-foreground hover:bg-secondary/80'
                    }`}
                  >
                    {labels[f]}
                  </button>
                )
              })}
            </div>

            {/* Catalog Cards */}
            <form autoComplete="off" data-lpignore="true" data-1p-ignore="true" className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {catalogLoading && <div className="col-span-2 text-center py-8">Loading catalog...</div>}
              
              {/* Custom Goal Card */}
              {!catalogLoading && (
                <div className="border border-dashed border-border rounded-lg p-4 bg-card" data-lpignore="true" data-1p-ignore="true">
                  <div className="font-medium mb-1 flex items-center gap-2">
                    <Plus className="w-4 h-4" />
                    Add Custom Goal
                  </div>
                  <div className="text-xs text-muted-foreground mb-2">
                    Create a custom goal for {filter === 'all' ? 'any' : filter} horizon
                  </div>
                  <div className="flex gap-2 items-center flex-wrap">
                    <input
                      autoComplete="off"
                      data-lpignore="true"
                      data-1p-ignore="true"
                      spellCheck={false}
                      autoCapitalize="off"
                      inputMode="text"
                      name="custom_goal_name"
                      placeholder="Goal name"
                      className="border border-border rounded px-3 py-2 flex-1 bg-secondary text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                      onChange={(e) => {
                        const key = `Custom::${e.target.value || 'Custom Goal'}`
                        setSelected(prev => ({...prev, [key]: prev[key] || { estimated_cost: 0, current_savings: 0 }}))
                      }}
                    />
                    <input
                      autoComplete="off"
                      data-lpignore="true"
                      data-1p-ignore="true"
                      name="custom_amount"
                      type="number"
                      min={0}
                      step={100}
                      inputMode="numeric"
                      className="border border-border rounded px-3 py-2 w-32 text-right bg-secondary text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                      placeholder="Amount"
                      onChange={(e) => {
                        const entries = Object.entries(selected)
                        if (entries.length === 0) return
                        const [lastKey] = entries[entries.length - 1]
                        if (!lastKey.startsWith('Custom::')) return
                        setSelected(prev => ({...prev, [lastKey]: {...(prev[lastKey] || {estimated_cost: 0, current_savings: 0}), estimated_cost: Number(e.target.value) || 0 }}))
                      }}
                    />
                    <div className="w-16 shrink-0" />
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">Tip: You can adjust amount/date later.</div>
                </div>
              )}

              {/* Catalog Items */}
              {!catalogLoading && filteredCatalog.map(item => {
                const key = `${item.goal_category}::${item.goal_name}`
                const isSelected = !!selected[key]
                const canSelect = !!selected[key] && (selected[key]?.estimated_cost || 0) > 0
                return (
                  <div
                    key={key}
                    className={`border border-border rounded-lg p-4 bg-card min-h-56 relative overflow-hidden transition-all ${
                      isSelected ? 'ring-2 ring-primary shadow-md' : ''
                    }`}
                    data-lpignore="true"
                    data-1p-ignore="true"
                  >
                    <div className="flex items-start gap-2">
                      <div className="font-medium text-foreground flex-1">{item.goal_name}</div>
                      {item.recommended && (
                        <span className="text-xs px-2 py-0.5 rounded bg-amber-200/40 text-amber-300 border border-amber-300/50 whitespace-nowrap">
                          Recommended
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {item.goal_category} • {item.default_horizon}
                    </div>
                    {item.context_hint && (
                      <div className="mt-1 text-xs text-sky-400">{item.context_hint}</div>
                    )}
                    {item.auto_suggest && (
                      <div className="mt-1 text-xs text-muted-foreground">Hint: {item.auto_suggest}</div>
                    )}

                    <div className="mt-3 flex flex-col gap-2">
                      <div className="flex gap-2 items-center flex-wrap">
                        <input
                          autoComplete="off"
                          data-lpignore="true"
                          data-1p-ignore="true"
                          spellCheck={false}
                          autoCapitalize="off"
                          name="amount"
                          type="number"
                          min={0}
                          step={100}
                          inputMode="numeric"
                          className="border border-border rounded px-3 py-2 w-32 text-right bg-secondary text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                          placeholder="Amount"
                          value={selected[key]?.estimated_cost ?? ''}
                          onChange={e => setSelected(prev => ({
                            ...prev,
                            [key]: {...(prev[key] || {estimated_cost: 0, current_savings: 0}), estimated_cost: Number(e.target.value) || 0 }
                          }))}
                        />
                        <input
                          autoComplete="off"
                          data-lpignore="true"
                          data-1p-ignore="true"
                          name="target_date"
                          type="date"
                          className="border border-border rounded px-3 py-2 w-36 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                          min={todayStr}
                          value={selected[key]?.target_date ?? ''}
                          onChange={e => setSelected(prev => ({
                            ...prev,
                            [key]: {...(prev[key] || {estimated_cost: 0, current_savings: 0}), target_date: e.target.value }
                          }))}
                        />
                        <input
                          autoComplete="off"
                          data-lpignore="true"
                          data-1p-ignore="true"
                          spellCheck={false}
                          autoCapitalize="off"
                          name="saved"
                          type="number"
                          min={0}
                          step={100}
                          inputMode="numeric"
                          className="border border-border rounded px-3 py-2 w-28 text-right bg-secondary text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                          placeholder="Saved"
                          value={selected[key]?.current_savings ?? ''}
                          onChange={e => setSelected(prev => ({
                            ...prev,
                            [key]: {...(prev[key] || {estimated_cost: 0, current_savings: 0}), current_savings: Number(e.target.value) || 0 }
                          }))}
                        />
                        <div className="w-16 shrink-0" />
                      </div>
                      <textarea
                        className="border border-border rounded px-3 py-2 bg-secondary text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary text-sm"
                        placeholder="Notes (optional)"
                        value={selected[key]?.notes ?? ''}
                        onChange={e => setSelected(prev => ({
                          ...prev,
                          [key]: {...(prev[key] || {estimated_cost: 0, current_savings: 0}), notes: e.target.value }
                        }))}
                      />
                    </div>

                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={() => toggleSelect(item)}
                        disabled={!canSelect}
                        className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                          isSelected
                            ? 'bg-secondary text-foreground hover:bg-secondary/80'
                            : 'bg-primary text-white hover:bg-primary/90'
                        } disabled:opacity-50 disabled:cursor-not-allowed`}
                      >
                        {isSelected ? 'Remove' : 'Select'}
                      </button>
                    </div>
                  </div>
                )
              })}
            </form>
          </div>

          {/* Right: Selection Summary + Portfolio */}
          <div className="xl:col-span-1">
            <div className="sticky top-6 space-y-4">
              {/* Selection Summary */}
              <div className="border border-border bg-card rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="font-medium">Selection</div>
                  <div className="text-xs text-muted-foreground">{selectedCount} items</div>
                </div>
                <div className="space-y-2 max-h-[40vh] overflow-auto pr-1 mb-3">
                  {Object.entries(selected).length === 0 && (
                    <div className="text-xs text-muted-foreground text-center py-4">No items selected.</div>
                  )}
                  {Object.entries(selected).map(([key, v]) => (
                    <div key={key} className="text-xs flex items-center justify-between gap-2 p-2 rounded bg-secondary/50">
                      <div className="truncate">{key.replace('::', ' · ')}</div>
                      <div className="text-muted-foreground whitespace-nowrap">
                        {formatCurrency(v.estimated_cost || 0)}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="border-t border-border pt-3 text-sm flex items-center justify-between mb-3">
                  <div>Total</div>
                  <div className="font-semibold">
                    {formatCurrency(Object.values(selected).reduce((s: number, v) => s + (v.estimated_cost || 0), 0))}
                  </div>
                </div>
                <button
                  onClick={submitSelection}
                  disabled={catalogLoading || selectedCount === 0}
                  className="w-full px-3 py-2 rounded bg-emerald-600 text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-emerald-700 transition-colors"
                >
                  Submit {selectedCount > 0 ? `(${selectedCount})` : ''}
                </button>
              </div>

              {/* Portfolio */}
              <div className="border border-border bg-card rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="font-medium">Portfolio</div>
                  <button
                    onClick={loadPortfolio}
                    className="text-xs text-primary hover:underline"
                  >
                    Refresh
                  </button>
                </div>
                {portfolioLoading && (
                  <div className="text-xs text-muted-foreground py-4 text-center">Loading...</div>
                )}
                {!portfolioLoading && (
                  <div className="space-y-2 max-h-[50vh] overflow-auto pr-1">
                    {(!portfolio || portfolio.length === 0) && (
                      <div className="text-xs text-muted-foreground text-center py-4">No goals yet.</div>
                    )}
                    {portfolio && portfolio.map((g) => {
                      const bucket = g.priority_rank && g.priority_rank <= 1 ? 'A' : g.priority_rank === 2 ? 'B' : g.priority_rank === 3 ? 'C' : 'D'
                      return (
                        <div
                          key={g.goal_id}
                          className="text-xs flex items-center justify-between gap-2 p-2 rounded bg-secondary/50 hover:bg-secondary transition-colors group"
                        >
                          <div className="truncate flex-1">
                            <span className="text-muted-foreground">[{bucket}]</span> {g.goal_name}
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-muted-foreground whitespace-nowrap">
                              {formatCurrency(g.estimated_cost || 0)}
                            </span>
                            <button
                              onClick={() => openEditModal(g)}
                              className="opacity-0 group-hover:opacity-100 p-1 hover:bg-secondary rounded transition-opacity"
                              title="Edit goal"
                            >
                              <Edit2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
                {portfolio && !portfolio.some((g: PortfolioGoal) => g.goal_category === 'Emergency' && String(g.goal_name || '').toLowerCase().startsWith('emergency fund')) && (
                  <div className="mt-3 text-xs rounded border border-amber-400/40 bg-amber-400/10 text-amber-300 p-2">
                    Emergency Fund recommended
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Track Progress Tab */}
      {activeTab === 'track' && (
        <>
          {/* Controls */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <input
                type="month"
                value={selectedMonth.slice(0, 7)}
                onChange={(e) => setSelectedMonth(`${e.target.value}-01`)}
                className="px-3 py-2 rounded border border-border bg-secondary text-foreground"
              />
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="px-4 py-2 rounded bg-primary text-white flex items-center gap-2 disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
          </div>

          {/* Dashboard Summary */}
          {dashboard && (
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-sm text-muted-foreground">Active Goals</div>
                <div className="text-2xl font-semibold mt-1">{dashboard.active_goals_count}</div>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-sm text-muted-foreground">Avg Progress</div>
                <div className="text-2xl font-semibold mt-1">{dashboard.avg_progress_pct.toFixed(1)}%</div>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-sm text-muted-foreground">Remaining</div>
                <div className="text-2xl font-semibold mt-1">{formatCurrency(dashboard.total_remaining_amount)}</div>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-sm text-muted-foreground">On Track</div>
                <div className="text-2xl font-semibold mt-1">{dashboard.goals_on_track_count}</div>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-sm text-muted-foreground">High Risk</div>
                <div className="text-2xl font-semibold mt-1 text-red-400">{dashboard.goals_high_risk_count}</div>
              </div>
            </div>
          )}

          {/* Goal Cards */}
          {loading ? (
            <div className="text-center py-12">Loading...</div>
          ) : insights.length === 0 ? (
            <div className="bg-card border border-border rounded-lg p-12 text-center">
              <Target className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
              <h3 className="text-lg font-semibold mb-2">No Goals Found</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Create goals in the Create Goals tab to see progress here.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {insights.map((card) => {
                const goal = goals.find(g => g.goal_id === card.goal_id)
                return (
                  <div
                    key={card.goal_id}
                    className="bg-card border border-border rounded-lg p-6 space-y-4"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-semibold text-lg">{card.name}</h3>
                        {goal && (
                          <div className="text-xs text-muted-foreground mt-1">
                            {goal.goal_category} • {goal.goal_type.replace('_', ' ')}
                          </div>
                        )}
                      </div>
                      <span className={`px-2 py-1 rounded text-xs border ${getRiskColor(card.risk)}`}>
                        {card.risk.toUpperCase()}
                      </span>
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-muted-foreground">Progress</span>
                        <span className="text-sm font-semibold">{card.progress_pct.toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-purple-500 to-purple-600 transition-all"
                          style={{ width: `${Math.min(card.progress_pct, 100)}%` }}
                        />
                      </div>
                    </div>

                    <div className="space-y-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Remaining</span>
                        <span className="font-semibold">{formatCurrency(card.remaining)}</span>
                      </div>
                      {goal?.months_remaining && (
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Months Left</span>
                          <span className="font-semibold">{goal.months_remaining}</span>
                        </div>
                      )}
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Suggested Monthly</span>
                        <span className="font-semibold">{formatCurrency(card.suggested_monthly)}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 pt-2 border-t border-border">
                      {card.on_track ? (
                        <>
                          <CheckCircle2 className="w-4 h-4 text-green-400" />
                          <span className="text-xs text-green-400">On Track</span>
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="w-4 h-4 text-yellow-400" />
                          <span className="text-xs text-yellow-400">Needs Attention</span>
                        </>
                      )}
                    </div>

                    {goal?.commentary && (
                      <div className="text-xs text-muted-foreground pt-2 border-t border-border">
                        {goal.commentary}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {/* Edit Modal */}
      {editModal.open && editModal.goal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-card border border-border rounded-lg p-6 max-w-md w-full space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Edit Goal</h3>
              <button
                onClick={() => setEditModal({ open: false, goal: null })}
                className="p-1 hover:bg-secondary rounded transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div>
              <div className="font-medium text-sm mb-1">{editModal.goal.goal_name}</div>
              <div className="text-xs text-muted-foreground">{editModal.goal.goal_category}</div>
            </div>
            <div className="space-y-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-foreground">Estimated Cost</label>
                <input
                  type="number"
                  min={0}
                  step={100}
                  className="border border-border rounded px-3 py-2 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                  value={editForm.estimated_cost}
                  onChange={e => setEditForm({...editForm, estimated_cost: Number(e.target.value) || 0})}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-foreground">Current Savings</label>
                <input
                  type="number"
                  min={0}
                  step={100}
                  className="border border-border rounded px-3 py-2 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                  value={editForm.current_savings}
                  onChange={e => setEditForm({...editForm, current_savings: Number(e.target.value) || 0})}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-foreground">Target Date</label>
                <input
                  type="date"
                  className="border border-border rounded px-3 py-2 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                  value={editForm.target_date}
                  onChange={e => setEditForm({...editForm, target_date: e.target.value})}
                  min={todayStr}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-foreground">Notes</label>
                <textarea
                  className="border border-border rounded px-3 py-2 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                  value={editForm.notes}
                  onChange={e => setEditForm({...editForm, notes: e.target.value})}
                  rows={3}
                />
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setEditModal({ open: false, goal: null })}
                className="px-4 py-2 rounded border border-border hover:bg-secondary transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={saveEdit}
                disabled={catalogLoading}
                className="px-4 py-2 rounded bg-primary text-white disabled:opacity-50 flex items-center gap-2"
              >
                <Save className="w-4 h-4" />
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
