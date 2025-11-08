import { useState, useEffect } from 'react'
import { CheckCircle2, Target, TrendingUp, TrendingDown } from 'lucide-react'
import { apiClient } from '../lib/api'

interface Recommendation {
  reco_id: string
  plan_code: string
  plan_name: string
  needs_budget_pct: number
  wants_budget_pct: number
  savings_budget_pct: number
  score: number
  recommendation_reason: string
}

interface BudgetCommit {
  user_id: string
  month: string
  plan_code: string
  alloc_needs_pct: number
  alloc_wants_pct: number
  alloc_assets_pct: number
  notes?: string
  committed_at: string
}

interface MonthlyAggregate {
  user_id: string
  month: string
  income_amt: number
  needs_amt: number
  planned_needs_amt: number
  variance_needs_amt: number
  wants_amt: number
  planned_wants_amt: number
  variance_wants_amt: number
  assets_amt: number
  planned_assets_amt: number
  variance_assets_amt: number
}

interface GoalAllocation {
  goal_id: string
  goal_name: string
  weight_pct: number
  planned_amount: number
}

export default function BudgetPilot() {
  const [loading, setLoading] = useState(true)
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [currentCommit, setCurrentCommit] = useState<BudgetCommit | null>(null)
  const [monthlyAggregate, setMonthlyAggregate] = useState<MonthlyAggregate | null>(null)
  const [goalAllocations, setGoalAllocations] = useState<GoalAllocation[]>([])
  const [selectedMonth, setSelectedMonth] = useState(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
  })
  const [committing, setCommitting] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    loadBudgetPilotData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMonth])

  const loadBudgetPilotData = async () => {
    try {
      setLoading(true)
      setError(null)

      // Load all data in parallel
      const [recos, commit, aggregate, allocations] = await Promise.all([
        apiClient.getBudgetRecommendations(selectedMonth).catch(() => []),
        apiClient.getBudgetCommit(selectedMonth).catch(() => null),
        apiClient.getMonthlyAggregate(selectedMonth).catch(() => null),
        apiClient.getGoalAllocations(selectedMonth).catch(() => [])
      ])

      // Sort recommendations by score (highest first) and take top 3
      const sorted = (recos || []).sort((a, b) => b.score - a.score)
      setRecommendations(sorted.slice(0, 3))

      setCurrentCommit(commit)
      setMonthlyAggregate(aggregate)
      setGoalAllocations(allocations || [])
    } catch (err: unknown) {
      console.error('Error loading BudgetPilot data:', err)
      setError(err instanceof Error ? err.message : 'Failed to load budget data')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateRecommendations = async () => {
    try {
      setGenerating(true)
      setError(null)
      setSuccess(null)

      await apiClient.generateBudgetRecommendations(selectedMonth)
      setSuccess('Recommendations generated successfully!')
      
      // Reload data
      await loadBudgetPilotData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate recommendations')
    } finally {
      setGenerating(false)
      setTimeout(() => {
        setSuccess(null)
      }, 3000)
    }
  }

  const handleCommit = async (planCode: string) => {
    try {
      setCommitting(true)
      setError(null)
      setSuccess(null)

      const notes = prompt('Add notes (optional):') || undefined
      await apiClient.commitToPlan(selectedMonth, planCode, notes)
      setSuccess(`Committed to ${planCode}!`)
      
      // Reload data
      await loadBudgetPilotData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to commit to plan')
    } finally {
      setCommitting(false)
      setTimeout(() => {
        setSuccess(null)
      }, 3000)
    }
  }

  const getVarianceColor = (variance: number) => {
    if (variance > 0) return 'text-success'
    if (variance < 0) return 'text-destructive'
    return 'text-muted-foreground'
  }

  const getVarianceIcon = (variance: number) => {
    if (variance > 0) return <TrendingUp className="h-4 w-4" />
    if (variance < 0) return <TrendingDown className="h-4 w-4" />
    return null
  }

  if (loading && !recommendations.length && !currentCommit) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-foreground">BudgetPilot</h1>
          <p className="text-muted-foreground mt-1">Smart budgeting and financial planning engine</p>
        </div>
        <div className="flex items-center gap-4">
          <input
            type="month"
            value={selectedMonth.slice(0, 7)}
            onChange={(e) => setSelectedMonth(`${e.target.value}-01`)}
            className="border border-border rounded-lg px-4 py-2 bg-secondary text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
          <button
            onClick={loadBudgetPilotData}
            className="bg-primary text-background px-4 py-2 rounded-lg font-medium hover:bg-primary/90 transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Status Messages */}
      {error && (
        <div className="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded-lg">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-success/10 border border-success text-success px-4 py-3 rounded-lg">
          {success}
        </div>
      )}

      {/* Current Commitment Status */}
      {currentCommit && (
        <div className="bg-card rounded-xl border border-border p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold text-foreground">Current Budget Plan</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Committed on {new Date(currentCommit.committed_at).toLocaleDateString()}
              </p>
            </div>
            <div className="px-4 py-2 bg-primary/10 text-primary rounded-lg font-medium">
              {currentCommit.plan_code}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 mt-4">
            <div className="text-center p-4 bg-secondary rounded-lg">
              <p className="text-sm text-muted-foreground">Needs</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {(currentCommit.alloc_needs_pct * 100).toFixed(0)}%
              </p>
            </div>
            <div className="text-center p-4 bg-secondary rounded-lg">
              <p className="text-sm text-muted-foreground">Wants</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {(currentCommit.alloc_wants_pct * 100).toFixed(0)}%
              </p>
            </div>
            <div className="text-center p-4 bg-secondary rounded-lg">
              <p className="text-sm text-muted-foreground">Savings</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {(currentCommit.alloc_assets_pct * 100).toFixed(0)}%
              </p>
            </div>
          </div>
          {currentCommit.notes && (
            <p className="mt-4 text-sm text-muted-foreground">Notes: {currentCommit.notes}</p>
          )}
        </div>
      )}

      {/* Top 3 Recommendations */}
      {recommendations.length > 0 && (
        <div className="bg-card rounded-xl border border-border">
          <div className="p-6 border-b border-border">
            <h2 className="text-xl font-semibold text-foreground">Top 3 Budget Plan Recommendations</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Based on your spending patterns, income flow, and goal priorities
            </p>
          </div>
          <div className="divide-y divide-border">
            {recommendations.map((reco, index) => (
              <div key={reco.reco_id} className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                        index === 0 ? 'bg-primary text-background' : 'bg-secondary text-foreground'
                      }`}>
                        {index + 1}
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-foreground">{reco.plan_name}</h3>
                        <p className="text-sm text-muted-foreground">{reco.plan_code}</p>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground mt-2">{reco.recommendation_reason}</p>
                  </div>
                  <div className="text-right ml-4">
                    <p className="text-sm text-muted-foreground">Score</p>
                    <p className="text-2xl font-bold text-foreground">
                      {reco.score.toFixed(1)}
                    </p>
                  </div>
                </div>
                
                {/* Allocation Breakdown */}
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div className="p-3 bg-secondary rounded-lg">
                    <p className="text-xs text-muted-foreground">Needs</p>
                    <p className="text-lg font-semibold text-foreground">
                      {(reco.needs_budget_pct * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="p-3 bg-secondary rounded-lg">
                    <p className="text-xs text-muted-foreground">Wants</p>
                    <p className="text-lg font-semibold text-foreground">
                      {(reco.wants_budget_pct * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="p-3 bg-secondary rounded-lg">
                    <p className="text-xs text-muted-foreground">Savings</p>
                    <p className="text-lg font-semibold text-foreground">
                      {(reco.savings_budget_pct * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => handleCommit(reco.plan_code)}
                  disabled={committing || (currentCommit?.plan_code === reco.plan_code)}
                  className={`w-full px-4 py-2 rounded-lg font-medium transition-colors ${
                    currentCommit?.plan_code === reco.plan_code
                      ? 'bg-success text-white cursor-not-allowed'
                      : 'bg-primary text-background hover:bg-primary/90'
                  } disabled:opacity-50`}
                >
                  {currentCommit?.plan_code === reco.plan_code ? (
                    <>
                      <CheckCircle2 className="inline h-4 w-4 mr-2" />
                      Currently Active
                    </>
                  ) : committing ? (
                    'Committing...'
                  ) : (
                    'Commit to This Plan'
                  )}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Monthly Actuals vs Plan */}
      {monthlyAggregate && (
        <div className="bg-card rounded-xl border border-border">
          <div className="p-6 border-b border-border">
            <h2 className="text-xl font-semibold text-foreground">Monthly Actuals vs Plan</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Income: ₹{monthlyAggregate.income_amt.toLocaleString()}
            </p>
          </div>
          <div className="divide-y divide-border">
            {/* Needs */}
            <div className="p-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-foreground">Needs</h3>
                <div className={`flex items-center gap-2 ${getVarianceColor(monthlyAggregate.variance_needs_amt)}`}>
                  {getVarianceIcon(monthlyAggregate.variance_needs_amt)}
                  <span className="font-medium">
                    ₹{Math.abs(monthlyAggregate.variance_needs_amt).toLocaleString()}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Actual</p>
                  <p className="text-lg font-semibold text-foreground">
                    ₹{monthlyAggregate.needs_amt.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Planned</p>
                  <p className="text-lg font-semibold text-foreground">
                    ₹{monthlyAggregate.planned_needs_amt.toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="mt-3 w-full bg-muted rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    monthlyAggregate.variance_needs_amt >= 0 ? 'bg-success' : 'bg-destructive'
                  }`}
                  style={{
                    width: `${Math.min(100, Math.max(0, (monthlyAggregate.needs_amt / monthlyAggregate.planned_needs_amt) * 100))}%`
                  }}
                />
              </div>
            </div>

            {/* Wants */}
            <div className="p-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-foreground">Wants</h3>
                <div className={`flex items-center gap-2 ${getVarianceColor(monthlyAggregate.variance_wants_amt)}`}>
                  {getVarianceIcon(monthlyAggregate.variance_wants_amt)}
                  <span className="font-medium">
                    ₹{Math.abs(monthlyAggregate.variance_wants_amt).toLocaleString()}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Actual</p>
                  <p className="text-lg font-semibold text-foreground">
                    ₹{monthlyAggregate.wants_amt.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Planned</p>
                  <p className="text-lg font-semibold text-foreground">
                    ₹{monthlyAggregate.planned_wants_amt.toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="mt-3 w-full bg-muted rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    monthlyAggregate.variance_wants_amt >= 0 ? 'bg-success' : 'bg-destructive'
                  }`}
                  style={{
                    width: `${Math.min(100, Math.max(0, (monthlyAggregate.wants_amt / monthlyAggregate.planned_wants_amt) * 100))}%`
                  }}
                />
              </div>
            </div>

            {/* Assets/Savings */}
            <div className="p-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-foreground">Savings</h3>
                <div className={`flex items-center gap-2 ${getVarianceColor(monthlyAggregate.variance_assets_amt)}`}>
                  {getVarianceIcon(monthlyAggregate.variance_assets_amt)}
                  <span className="font-medium">
                    ₹{Math.abs(monthlyAggregate.variance_assets_amt).toLocaleString()}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Actual</p>
                  <p className="text-lg font-semibold text-foreground">
                    ₹{monthlyAggregate.assets_amt.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Planned</p>
                  <p className="text-lg font-semibold text-foreground">
                    ₹{monthlyAggregate.planned_assets_amt.toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="mt-3 w-full bg-muted rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    monthlyAggregate.variance_assets_amt >= 0 ? 'bg-success' : 'bg-destructive'
                  }`}
                  style={{
                    width: `${Math.min(100, Math.max(0, (monthlyAggregate.assets_amt / monthlyAggregate.planned_assets_amt) * 100))}%`
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Goal-Level Allocations */}
      {goalAllocations.length > 0 && (
        <div className="bg-card rounded-xl border border-border">
          <div className="p-6 border-b border-border">
            <h2 className="text-xl font-semibold text-foreground">Goal-Level Allocations</h2>
            <p className="text-sm text-muted-foreground mt-1">
              How your savings are allocated across your goals
            </p>
          </div>
          <div className="divide-y divide-border">
            {goalAllocations.map((alloc) => (
              <div key={alloc.goal_id} className="p-6">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <h3 className="font-semibold text-foreground">{alloc.goal_name}</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      {((alloc.weight_pct || 0) * 100).toFixed(2)}% of savings allocation
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold text-foreground">
                      ₹{alloc.planned_amount.toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <div
                    className="h-2 rounded-full bg-primary"
                    style={{ width: `${Math.min(100, (alloc.weight_pct || 0) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && recommendations.length === 0 && !currentCommit && !monthlyAggregate && (
        <div className="bg-card rounded-xl border border-border p-12 text-center">
          <Target className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">No Budget Recommendations Yet</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Generate personalized budget recommendations based on your spending patterns and goals.
          </p>
          <button
            onClick={handleGenerateRecommendations}
            disabled={generating}
            className="bg-primary text-background px-6 py-3 rounded-lg font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? 'Generating...' : 'Generate Recommendations'}
          </button>
          <div className="mt-6 text-xs text-muted-foreground">
            <p className="mb-2">Make sure you have:</p>
            <ul className="space-y-1 text-left inline-block">
              <li>• Transactions uploaded or synced</li>
              <li>• Goals set up in GoalTrack</li>
              <li>• At least one month of transaction history</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

