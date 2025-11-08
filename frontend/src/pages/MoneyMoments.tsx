import { useState, useEffect } from 'react'
import { Lightbulb, TrendingDown, TrendingUp, RefreshCw, X, Eye, MousePointerClick, Bell, Settings, BarChart3, Target } from 'lucide-react'
import { apiClient } from '../lib/api'
import { format } from 'date-fns'

interface Nudge {
  delivery_id?: string
  candidate_id?: string
  rule_id: string
  rule_name: string
  title_template: string
  body_template: string
  cta_text: string | null
  cta_deeplink: string | null
  score?: number
  reason_json?: any
  sent_at?: string
  created_at: string
  interaction_count?: number
}

interface Signals {
  dining_txn_7d: number
  dining_spend_7d: number
  shopping_txn_7d: number
  shopping_spend_7d: number
  wants_share_30d: number | null
  wants_vs_plan_pct: number | null
}

interface CTR {
  total_delivered: number
  total_viewed: number
  total_clicked: number
  view_rate: number
  ctr: number
}

export default function MoneyMoments() {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [activeTab, setActiveTab] = useState<'feed' | 'analytics' | 'settings'>('feed')
  
  const [nudges, setNudges] = useState<Nudge[]>([])
  const [signals, setSignals] = useState<Signals | null>(null)
  const [ctr, setCtr] = useState<CTR | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)

      const today = new Date().toISOString().split('T')[0]
      
      const [deliveredNudges, signalsData, ctrData] = await Promise.all([
        apiClient.getDeliveredNudges(20).catch(() => ({ nudges: [] })),
        apiClient.getMoneyMomentsSignals(today).catch(() => null),
        apiClient.getMoneyMomentsCTR(30).catch(() => null)
      ])

      setNudges(deliveredNudges.nudges || [])
      setSignals(signalsData)
      setCtr(ctrData)
    } catch (err: unknown) {
      console.error('Error loading MoneyMoments data:', err)
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    try {
      setRefreshing(true)
      setError(null)
      setSuccess(null)

      const today = new Date().toISOString().split('T')[0]
      
      // Derive signals, candidates, and queue deliveries
      await apiClient.deriveMoneyMomentsSignals(today)
      await apiClient.deriveNudgeCandidates(today)
      await apiClient.queueNudgeDeliveries(today)

      setSuccess('Nudges refreshed successfully')
      await loadData()
    } catch (err: unknown) {
      console.error('Error refreshing nudges:', err)
      setError(err instanceof Error ? err.message : 'Failed to refresh nudges')
    } finally {
      setRefreshing(false)
    }
  }

  const handleInteraction = async (nudge: Nudge, eventType: 'view' | 'click' | 'dismiss') => {
    if (!nudge.delivery_id) return

    try {
      await apiClient.logNudgeInteraction(nudge.delivery_id, eventType)
      
      if (eventType === 'click' && nudge.cta_deeplink) {
        // Handle deeplink navigation
        window.location.href = nudge.cta_deeplink
      }
    } catch (err) {
      console.error('Error logging interaction:', err)
    }
  }

  const renderNudgeContent = (nudge: Nudge) => {
    // Simple template rendering (replace placeholders)
    let title = nudge.title_template
    let body = nudge.body_template

    // Replace common placeholders with sample values
    if (nudge.reason_json) {
      const reason = nudge.reason_json
      if (reason.dining_txn_7d) {
        body = body.replace('{{save}}', `₹${(reason.dining_spend_7d / reason.dining_txn_7d || 0).toFixed(0)}`)
        body = body.replace('{{goal}}', 'vacation fund')
      }
      if (reason.rank1_goal_underfund_amt) {
        body = body.replace('{{goal}}', 'top goal')
      }
    }

    return { title, body }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(amount)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading MoneyMoments...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-xl bg-gradient-to-r from-amber-800 to-amber-700 border border-border p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold flex items-center gap-2">
              <Lightbulb className="w-6 h-6" />
              MoneyMoments
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              Personalized behavioral nudges to improve your financial habits
            </p>
          </div>
          <div className="flex items-center gap-3">
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
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab('feed')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'feed'
              ? 'text-primary border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          <Bell className="w-4 h-4 inline mr-2" />
          Nudge Feed
        </button>
        <button
          onClick={() => setActiveTab('analytics')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'analytics'
              ? 'text-primary border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          <BarChart3 className="w-4 h-4 inline mr-2" />
          Analytics
        </button>
        <button
          onClick={() => setActiveTab('settings')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'settings'
              ? 'text-primary border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          <Settings className="w-4 h-4 inline mr-2" />
          Settings
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

      {/* Feed Tab */}
      {activeTab === 'feed' && (
        <div className="space-y-4">
          {/* Signal Summary */}
          {signals && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-sm text-muted-foreground">Dining (7d)</div>
                <div className="text-xl font-semibold mt-1">
                  {signals.dining_txn_7d} times
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {formatCurrency(signals.dining_spend_7d)}
                </div>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-sm text-muted-foreground">Shopping (7d)</div>
                <div className="text-xl font-semibold mt-1">
                  {signals.shopping_txn_7d} times
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {formatCurrency(signals.shopping_spend_7d)}
                </div>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-sm text-muted-foreground">Wants Share</div>
                <div className="text-xl font-semibold mt-1">
                  {signals.wants_share_30d ? `${(signals.wants_share_30d * 100).toFixed(1)}%` : 'N/A'}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Last 30 days
                </div>
              </div>
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="text-sm text-muted-foreground">Vs Plan</div>
                <div className={`text-xl font-semibold mt-1 flex items-center gap-1 ${
                  signals.wants_vs_plan_pct && signals.wants_vs_plan_pct > 0 ? 'text-red-400' : 'text-green-400'
                }`}>
                  {signals.wants_vs_plan_pct ? (
                    <>
                      {signals.wants_vs_plan_pct > 0 ? (
                        <TrendingUp className="w-5 h-5" />
                      ) : (
                        <TrendingDown className="w-5 h-5" />
                      )}
                      {Math.abs(signals.wants_vs_plan_pct * 100).toFixed(1)}%
                    </>
                  ) : (
                    'N/A'
                  )}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Budget variance
                </div>
              </div>
            </div>
          )}

          {/* Nudge Cards */}
          {nudges.length === 0 ? (
            <div className="bg-card border border-border rounded-lg p-12 text-center">
              <Lightbulb className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
              <h3 className="text-lg font-semibold mb-2">No Nudges Yet</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Nudges will appear here as we analyze your spending patterns.
              </p>
              <button
                onClick={handleRefresh}
                className="px-4 py-2 rounded bg-primary text-white"
              >
                Generate Nudges
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {nudges.map((nudge) => {
                const { title, body } = renderNudgeContent(nudge)
                return (
                  <div
                    key={nudge.delivery_id || nudge.candidate_id}
                    className="bg-card border border-border rounded-lg p-6 space-y-4 hover:shadow-lg transition-shadow"
                    onMouseEnter={() => handleInteraction(nudge, 'view')}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Target className="w-5 h-5 text-amber-400" />
                          <span className="text-xs font-medium text-muted-foreground">
                            {nudge.rule_name}
                          </span>
                        </div>
                        <h3 className="text-lg font-semibold mb-2">{title}</h3>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                          {body}
                        </p>
                      </div>
                      <button
                        onClick={() => handleInteraction(nudge, 'dismiss')}
                        className="p-1 hover:bg-secondary rounded transition-colors"
                      >
                        <X className="w-4 h-4 text-muted-foreground" />
                      </button>
                    </div>

                    <div className="flex items-center justify-between pt-4 border-t border-border">
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        {nudge.sent_at && (
                          <span>{format(new Date(nudge.sent_at), 'MMM d, yyyy')}</span>
                        )}
                        {nudge.interaction_count !== undefined && (
                          <span className="flex items-center gap-1">
                            <Eye className="w-3 h-3" />
                            {nudge.interaction_count} views
                          </span>
                        )}
                      </div>
                      {nudge.cta_text && (
                        <button
                          onClick={() => handleInteraction(nudge, 'click')}
                          className="px-4 py-2 rounded bg-amber-600 text-white text-sm font-medium hover:bg-amber-700 transition-colors flex items-center gap-2"
                        >
                          <MousePointerClick className="w-4 h-4" />
                          {nudge.cta_text}
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Analytics Tab */}
      {activeTab === 'analytics' && (
        <div className="space-y-6">
          {ctr ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-card border border-border rounded-lg p-6">
                  <div className="text-sm text-muted-foreground mb-2">Click-Through Rate</div>
                  <div className="text-3xl font-bold mb-1">{ctr.ctr.toFixed(1)}%</div>
                  <div className="text-xs text-muted-foreground">
                    {ctr.total_clicked} clicks / {ctr.total_viewed} views
                  </div>
                </div>
                <div className="bg-card border border-border rounded-lg p-6">
                  <div className="text-sm text-muted-foreground mb-2">View Rate</div>
                  <div className="text-3xl font-bold mb-1">{ctr.view_rate.toFixed(1)}%</div>
                  <div className="text-xs text-muted-foreground">
                    {ctr.total_viewed} views / {ctr.total_delivered} delivered
                  </div>
                </div>
                <div className="bg-card border border-border rounded-lg p-6">
                  <div className="text-sm text-muted-foreground mb-2">Total Delivered</div>
                  <div className="text-3xl font-bold mb-1">{ctr.total_delivered}</div>
                  <div className="text-xs text-muted-foreground">
                    Last 30 days
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="bg-card border border-border rounded-lg p-12 text-center">
              <BarChart3 className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
              <h3 className="text-lg font-semibold mb-2">No Analytics Yet</h3>
              <p className="text-sm text-muted-foreground">
                Analytics will appear after you start receiving nudges.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Settings Tab */}
      {activeTab === 'settings' && (
        <div className="space-y-4">
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Notification Settings</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Configure how often you receive behavioral nudges.
            </p>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-secondary rounded">
                <div>
                  <div className="font-medium">Daily Cap</div>
                  <div className="text-sm text-muted-foreground">Maximum nudges per day</div>
                </div>
                <select className="px-3 py-2 rounded border border-border bg-background">
                  <option>3</option>
                  <option>5</option>
                  <option>10</option>
                  <option>Unlimited</option>
                </select>
              </div>
              <div className="flex items-center justify-between p-3 bg-secondary rounded">
                <div>
                  <div className="font-medium">Mute Notifications</div>
                  <div className="text-sm text-muted-foreground">Temporarily disable nudges</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" className="sr-only peer" />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/30 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                </label>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
