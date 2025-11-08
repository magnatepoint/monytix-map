/**
 * API Client for Monytix Backend
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://backend.mallaapp.org'

export interface ApiResponse<T> {
  data?: T
  error?: string
}

class ApiClient {
  private baseUrl: string
  
  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }
  
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    // Get token from Supabase session
    const { supabase } = await import('./supabase')
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token || null
    
    if (!token) {
      console.warn('No auth token available. User may need to log in.')
    }
    
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>)
    }
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers
      })
      
      // Read response text once (can only read body once)
      const contentType = response.headers.get('content-type') || ''
      const text = await response.text()
      
      if (!response.ok) {
        let errorData: { detail?: string; message?: string }
        if (text) {
          try {
            errorData = JSON.parse(text) as { detail?: string; message?: string }
          } catch {
            errorData = { detail: text || 'Request failed', message: text || 'Request failed' }
          }
        } else {
          errorData = { detail: 'Request failed', message: 'Request failed' }
        }
        // FastAPI returns error details in 'detail' field
        const errorMessage = errorData.detail || errorData.message || 'Request failed'
        const errorWithStatus = new Error(errorMessage) as Error & { status?: number, response?: Response, detail?: string }
        errorWithStatus.status = response.status
        errorWithStatus.response = response
        errorWithStatus.detail = errorData.detail || errorMessage
        throw errorWithStatus
      }
      
      // Success response - parse JSON if available
      if (!text || text.trim() === '') {
        return null
      }
      
      // Try to parse as JSON if content-type suggests JSON or if it looks like JSON
      if (contentType.includes('application/json') || (text.trim().startsWith('{') || text.trim().startsWith('['))) {
        try {
          return JSON.parse(text)
        } catch (parseError) {
          console.error('JSON parse error:', parseError, 'Response text:', text.substring(0, 200))
          throw new Error(`Invalid JSON response: ${parseError}`)
        }
      } else {
        // Non-JSON response - return as text
        return text || null
      }
    } catch (error) {
      console.error('API Request failed:', error)
      throw error
    }
  }
  
  // SpendSense APIs
  async getSpendingStats(period: string = 'month') {
    return this.request<{
      period: string
      total_spending: number
      total_income: number
      net_flow: number
      cumulative_balance?: number
      transaction_count: number
      top_category: string | null
      top_merchant: string | null
      avg_transaction: number
    }>(`/api/spendsense/stats?period=${period}`)
  }
  
  async getSpendingByCategory(period: string = 'month') {
    return this.request<{
      period: string
      categories: Array<{
        category: string
        amount: number
        percentage: number
        transaction_count: number
      }>
      total: number
    }>(`/api/spendsense/by-category?period=${period}`)
  }
  
  async getSpendingTrends(period: string = '3months') {
    return this.request<{
      period: string
      trends: Array<{
        period: string
        spending: number
        date: string
      }>
    }>(`/api/spendsense/trends?period=${period}`)
  }
  
  async getTopMerchants(limit: number = 10, period: string = 'month') {
    return this.request<{
      period: string
      merchants: Array<{
        merchant: string
        total_spending: number
        transaction_count: number
      }>
    }>(`/api/spendsense/merchants?limit=${limit}&period=${period}`)
  }
  
  async getInsights() {
    return this.request<{
      insights: Array<{
        type: string
        category: string
        change_percentage: number
        message: string
      }>
    }>('/api/spendsense/insights')
  }
  
  async getTransactions(
    skip: number = 0,
    limit: number = 50,
    category?: string,
    startDate?: string,
    endDate?: string,
    subcategory?: string,
    direction?: 'debit' | 'credit',
    sort?: 'date_desc' | 'date_asc' | 'amt_desc' | 'amt_asc',
    search?: string
  ): Promise<Array<{
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
  }>> {
    const params = new URLSearchParams()
    params.append('skip', skip.toString())
    params.append('limit', limit.toString())
    if (category) params.append('category', category)
    if (subcategory) params.append('subcategory', subcategory)
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    if (direction) params.append('direction', direction)
    if (sort) params.append('sort', sort)
    if (search) params.append('search', search)
    
    const queryString = params.toString()
    const url = `/api/transactions${queryString ? `?${queryString}` : ''}`
    
    // New API returns TransactionListResponse with { data, total, skip, limit }
    // Extract data array for backward compatibility
    const response = await this.request<{ data: any[]; total: number; skip: number; limit: number } | any[]>(url)
    
    // Handle both old format (array) and new format (object with data field)
    if (Array.isArray(response)) {
      return response
    }
    if (response && typeof response === 'object' && 'data' in response) {
      return (response as { data: any[] }).data || []
    }
    return []
  }
  
  // SpendSense Additional APIs
  
  async getTopCategories(limit: number = 3, period: string = 'month') {
    return this.request<{
      period: string
      categories: Array<{
        category: string
        total_spending: number
        transaction_count: number
      }>
    }>(`/api/spendsense/top-categories?limit=${limit}&period=${period}`)
  }
  
  async detectSpendingLeaks(threshold: number = 1000, period: string = 'month') {
    return this.request<{
      period: string
      total_leak_amount: number
      leaks_detected: number
      leaks: Array<{
        merchant: string
        transaction_count: number
        total_spent: number
        avg_transaction: number
        leak_score: number
      }>
    }>(`/api/spendsense/leaks?threshold=${threshold}&period=${period}`)
  }
  
  async comparePeriods() {
    return this.request<{
      comparison: {
        last_week: number
        this_week: number
        last_month: number
        this_month: number
      }
      week_change_percentage: number
      month_change_percentage: number
    }>('/api/spendsense/comparing-periods')
  }

  // Goals APIs
  async getGoalsCatalog() {
    type CatalogItem = {
      goal_category: string
      goal_name: string
      default_horizon: 'short_term' | 'medium_term' | 'long_term' | string
      policy_linked_txn_type: 'needs' | 'wants' | 'assets'
      auto_suggest?: string | null
      recommended?: boolean
      context_hint?: string | null
    }
    return this.request<{ short: CatalogItem[]; medium: CatalogItem[]; long: CatalogItem[] }>(`/api/goals/catalog`)
  }

  async getGoalsContext() {
    return this.request<{
      age_band: string
      dependents_spouse: boolean
      dependents_children_count: number
      dependents_parents_care: boolean
      housing: string
      employment: string
      income_regularity: string
      region_code: string
    } | null>(`/api/goals/context`)
  }

  async putGoalsContext(ctx: {
    age_band: string
    dependents_spouse?: boolean
    dependents_children_count?: number
    dependents_parents_care?: boolean
    housing: string
    employment: string
    income_regularity: string
    region_code: string
    emergency_opt_out?: boolean
  }) {
    return this.request<{ status: string }>(`/api/goals/context`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ctx)
    })
  }

  async submitGoals(payload: {
    context: Record<string, unknown>
    selected_goals: Array<{
      goal_category: string
      goal_name: string
      goal_type: string
      estimated_cost: number
      target_date?: string
      current_savings: number
      linked_txn_type?: string
      notes?: string
    }>
  }) {
    return this.request<{ created: Array<{ goal_id: string; priority_rank: number }> }>(`/api/goals/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  }

  async getGoalsSummary() {
    type PortfolioGoal = {
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
    return this.request<PortfolioGoal[] | { goals: PortfolioGoal[] }>(`/api/goals/summary`)
  }

  async updateGoal(goalId: string, updates: {
    estimated_cost?: number
    current_savings?: number
    target_date?: string
    notes?: string
  }) {
    return this.request<{ message: string; goal_id: string }>(`/api/goals/${goalId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    })
  }

  async getKPIs() {
    return this.request<{
      period: string
      total_spending: number
      total_income: number
      net_flow: number
      transaction_count: number
    }>(`/api/spendsense/kpis`)
  }

  // Upload APIs
  async uploadPDF(file: File, bank?: string, password?: string) {
    const formData = new FormData()
    formData.append('file', file)
    if (bank) formData.append('bank', bank)
    if (password) formData.append('password', password)

    const { supabase } = await import('./supabase')
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token || localStorage.getItem('supabase_token')
    const response = await fetch(`${this.baseUrl}/api/upload/pdf`, {
      method: 'POST',
      headers: {
        ...(token && { 'Authorization': `Bearer ${token}` }),
      },
      body: formData
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Upload failed' }))
      throw new Error(error.message || error.detail || 'Upload failed')
    }

    return response.json()
  }

  async uploadCSV(file: File) {
    const formData = new FormData()
    formData.append('file', file)

    const { supabase } = await import('./supabase')
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token || localStorage.getItem('supabase_token')
    const response = await fetch(`${this.baseUrl}/api/upload/csv`, {
      method: 'POST',
      headers: {
        ...(token && { 'Authorization': `Bearer ${token}` }),
      },
      body: formData
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Upload failed' }))
      throw new Error(error.message || error.detail || 'Upload failed')
    }

    return response.json()
  }

  // SpendSense ETL: Load staging -> fact + enrichment
  async loadStagingToFact() {
    return this.request<{ inserted: number }>(`/api/etl/spendsense/load/staging`, {
      method: 'POST'
    })
  }

  async uploadXLS(file: File) {
    const formData = new FormData()
    formData.append('file', file)

    const { supabase } = await import('./supabase')
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token || localStorage.getItem('supabase_token')
    const response = await fetch(`${this.baseUrl}/api/upload/xls`, {
      method: 'POST',
      headers: {
        ...(token && { 'Authorization': `Bearer ${token}` }),
      },
      body: formData
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Upload failed' }))
      throw new Error(error.message || error.detail || 'Upload failed')
    }

    return response.json()
  }

  async uploadCSVETL(file: File) {
    const formData = new FormData()
    formData.append('file', file)

    const { supabase } = await import('./supabase')
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token || localStorage.getItem('supabase_token')
    const response = await fetch(`${this.baseUrl}/api/etl/upload/csv`, {
      method: 'POST',
      headers: {
        ...(token && { 'Authorization': `Bearer ${token}` }),
      },
      body: formData
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Upload failed' }))
      throw new Error(error.message || error.detail || 'Upload failed')
    }

    return response.json()
  }

  async getUploadJobStatus(jobId: string) {
    return this.request<{
      job_id: string
      status: string
      progress?: number
      message?: string
      error?: string
    }>(`/api/upload/jobs/${jobId}`)
  }

  // Gmail/Email Integration APIs
  async connectGmail(accessToken?: string, email?: string, displayName?: string) {
    return this.request<{
      message: string
      status: string
      connection_id: string
      email: string
    }>('/api/gmail/connect', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        access_token: accessToken || null,
        email: email || null,
        display_name: displayName || null
      })
    })
  }

  async exchangeGmailCode(code: string) {
    return this.request<{
      message: string
      scope: string
      expires_in: number
      token_type: string
      has_refresh_token: boolean
    }>('/api/gmail/oauth/exchange', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ code })
    })
  }

  async listGmailConnections() {
    return this.request<{
      connections: Array<{
        id: string
        email: string | null
        display_name: string | null
        is_active: boolean
        sync_enabled: boolean
        last_sync_at: string | null
        total_emails_fetched: number
        total_transactions_extracted: number
        created_at: string
      }>
    }>('/api/gmail/connections')
  }

  async gmailStatus() {
    return this.request<{
      active: boolean
      connected: boolean
      connection_count: number
      sync_enabled: boolean
      last_sync_at: string | null
    }>('/api/gmail/status')
  }

  async syncGmail(connectionId?: string) {
    return this.request<{
      message: string
      connections: Array<{
        connection_id: string
        email: string
        display_name: string | null
        task_id: string
        job_id: string
      }>
      status: string
      transactions_extracted: number
    }>('/api/gmail/sync', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(connectionId ? { connection_id: connectionId } : {})
    })
  }

  async syncGmailConnection(connectionId: string) {
    return this.request<{
      message: string
      job_id: string
      task_id: string
      status: string
    }>(`/api/gmail/connections/${connectionId}/sync`, {
      method: 'POST'
    })
  }

  async deleteGmailConnection(connectionId: string) {
    return this.request<{
      message: string
    }>(`/api/gmail/connections/${connectionId}`, {
      method: 'DELETE'
    })
  }

  async getGmailBills() {
    return this.request<Array<{
      id: string
      merchant: string
      amount: number
      due_date: string
      status: string
    }>>('/api/gmail/bills')
  }

  // Transaction APIs
  async createTransaction(transaction: {
    amount: number
    currency?: string
    transaction_date: string
    description: string
    merchant?: string
    category?: string
    bank?: string
    transaction_type: string
  }) {
    return this.request<{ id: string; message?: string }>('/api/transactions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(transaction)
    })
  }

  async updateTransaction(id: string, updates: Partial<{
    amount: number
    currency: string
    transaction_date: string
    description: string
    merchant: string
    category: string
    transaction_type: string
  }>) {
    return this.request<{ id: string; message?: string }>(`/api/transactions/${id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates)
    })
  }

  async deleteTransaction(id: string) {
    return this.request<{ message: string }>(`/api/transactions/${id}`, {
      method: 'DELETE'
    })
  }

  async getTransactionStats(period: string = 'month') {
    return this.request<{
      total_debit: number
      total_credit: number
      net_amount: number
      transaction_count: number
      period: string
    }>(`/api/transactions/stats?period=${period}`)
  }

  // BudgetPilot APIs
  async generateBudgetRecommendations(month?: string) {
    const params = month ? `?month=${month}` : ''
    return this.request<{
      message: string
      month: string
      generated: boolean
    }>(`/api/budgetpilot/generate-recommendations${params}`, {
      method: 'POST'
    })
  }

  async getBudgetRecommendations(month?: string) {
    const params = month ? `?month=${month}` : ''
    return this.request<Array<{
      reco_id: string
      plan_code: string
      plan_name: string
      needs_budget_pct: number
      wants_budget_pct: number
      savings_budget_pct: number
      score: number
      recommendation_reason: string
    }>>(`/api/budgetpilot/recommendations${params}`)
  }

  async commitToPlan(month: string, planCode: string, notes?: string) {
    return this.request<{
      user_id: string
      month: string
      plan_code: string
      alloc_needs_pct: number
      alloc_wants_pct: number
      alloc_assets_pct: number
      notes?: string
    }>(`/api/budgetpilot/commit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ month, plan_code: planCode, notes })
    })
  }

  async getBudgetCommit(month?: string) {
    const params = month ? `?month=${month}` : ''
    return this.request<{
      user_id: string
      month: string
      plan_code: string
      alloc_needs_pct: number
      alloc_wants_pct: number
      alloc_assets_pct: number
      notes?: string
      committed_at: string
    } | null>(`/api/budgetpilot/commit${params}`)
  }

  async getMonthlyAggregate(month?: string) {
    const params = month ? `?month=${month}` : ''
    return this.request<{
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
    } | null>(`/api/budgetpilot/monthly-aggregate${params}`)
  }

  async getGoalAllocations(month?: string) {
    const params = month ? `?month=${month}` : ''
    return this.request<Array<{
      goal_id: string
      goal_name: string
      weight_pct: number
      planned_amount: number
    }>>(`/api/budgetpilot/goal-allocations${params}`)
  }

  // GoalCompass APIs
  async getGoalProgress(goalId?: string, month?: string) {
    const params = new URLSearchParams()
    if (goalId) params.append('goal_id', goalId)
    if (month) params.append('month', month)
    
    const query = params.toString()
    return this.request<{
      goals?: Array<{
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
      }>
    }>(`/api/goalcompass/progress${query ? `?${query}` : ''}`)
  }

  async getGoalDashboard(month?: string) {
    const params = month ? `?month=${month}` : ''
    return this.request<{
      month: string
      active_goals_count: number
      avg_progress_pct: number
      total_remaining_amount: number
      goals_on_track_count: number
      goals_high_risk_count: number
    }>(`/api/goalcompass/dashboard${params}`)
  }

  async getGoalInsights(month?: string) {
    const params = month ? `?month=${month}` : ''
    return this.request<{
      month: string
      goal_cards: Array<{
        goal_id: string
        name: string
        progress_pct: number
        remaining: number
        on_track: boolean
        risk: 'low' | 'medium' | 'high'
        suggested_monthly: number
      }>
    }>(`/api/goalcompass/insights${params}`)
  }

  async getGoalMilestones(goalId: string) {
    return this.request<{
      goal_id: string
      milestones: Array<{
        milestone_id: string
        threshold_pct: number
        label: string
        description: string | null
        achieved_flag: boolean
        achieved_at: string | null
        progress_pct_at_ach: number | null
      }>
    }>(`/api/goalcompass/milestones/${goalId}`)
  }

  async refreshGoalCompass(month: string, asOfDate?: string) {
    return this.request<{
      message: string
      month: string
      user_id: string
    }>(`/api/goalcompass/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ month, as_of_date: asOfDate })
    })
  }

  async getGoalContributions(goalId?: string, month?: string) {
    const params = new URLSearchParams()
    if (goalId) params.append('goal_id', goalId)
    if (month) params.append('month', month)
    
    const query = params.toString()
    return this.request<{
      contributions: Array<{
        gcf_id: string
        goal_id: string
        goal_name: string
        month: string
        source: string
        amount: number
        notes: string | null
        created_at: string
      }>
    }>(`/api/goalcompass/contributions${query ? `?${query}` : ''}`)
  }

  // MoneyMoments APIs
  async getMoneyMomentsTraits() {
    return this.request<{
      user_id: string
      age_band: string
      gender: string | null
      region_code: string
      lifestyle_tags: string[]
      created_at: string
      updated_at: string
    } | null>(`/api/moneymoments/traits`)
  }

  async putMoneyMomentsTraits(traits: {
    age_band: string
    gender?: string
    region_code: string
    lifestyle_tags?: string[]
  }) {
    return this.request<{ status: string; message: string }>(`/api/moneymoments/traits`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(traits)
    })
  }

  async getMoneyMomentsSignals(asOfDate?: string) {
    const params = asOfDate ? `?as_of_date=${asOfDate}` : ''
    return this.request<{
      user_id: string
      as_of_date: string
      dining_txn_7d: number
      dining_spend_7d: number
      shopping_txn_7d: number
      shopping_spend_7d: number
      travel_txn_30d: number
      travel_spend_30d: number
      wants_share_30d: number | null
      recurring_merchants_90d: number
      wants_vs_plan_pct: number | null
      assets_vs_plan_pct: number | null
      rank1_goal_underfund_amt: number
      rank1_goal_underfund_pct: number | null
      last_nudge_sent_at: string | null
      created_at: string
    } | null>(`/api/moneymoments/signals${params}`)
  }

  async deriveMoneyMomentsSignals(asOfDate: string) {
    return this.request<{ status: string; message: string; as_of_date: string }>(`/api/moneymoments/signals/derive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ as_of_date: asOfDate })
    })
  }

  async getPendingNudges() {
    return this.request<{
      nudges: Array<{
        candidate_id: string
        user_id: string
        as_of_date: string
        rule_id: string
        template_code: string
        score: number
        reason_json: Record<string, unknown>
        status: string
        created_at: string
        rule_name: string
        rule_description: string | null
        title_template: string
        body_template: string
        cta_text: string | null
        cta_deeplink: string | null
        humor_style: string | null
      }>
    }>(`/api/moneymoments/nudges/pending`)
  }

  async getDeliveredNudges(limit?: number) {
    const params = limit ? `?limit=${limit}` : ''
    return this.request<{
      nudges: Array<{
        delivery_id: string
        candidate_id: string
        user_id: string
        rule_id: string
        template_code: string
        channel: string
        sent_at: string
        send_status: string
        metadata_json: Record<string, unknown>
        rule_name: string
        title_template: string
        body_template: string
        cta_text: string | null
        cta_deeplink: string | null
        interaction_count: number
      }>
    }>(`/api/moneymoments/nudges/delivered${params}`)
  }

  async deriveNudgeCandidates(asOfDate: string) {
    return this.request<{ status: string; message: string; as_of_date: string }>(`/api/moneymoments/nudges/candidates/derive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ as_of_date: asOfDate })
    })
  }

  async queueNudgeDeliveries(asOfDate: string) {
    return this.request<{ status: string; message: string; as_of_date: string }>(`/api/moneymoments/nudges/queue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ as_of_date: asOfDate })
    })
  }

  async logNudgeInteraction(deliveryId: string, eventType: 'view' | 'click' | 'dismiss', metadata?: Record<string, unknown>) {
    return this.request<{ status: string; interaction_id: string; message: string }>(`/api/moneymoments/nudges/interactions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        delivery_id: deliveryId,
        event_type: eventType,
        metadata
      })
    })
  }

  async getMoneyMomentsSuppression() {
    return this.request<{
      settings: Array<{
        user_id: string
        channel: string
        muted_until: string | null
        daily_cap: number
      }>
    }>(`/api/moneymoments/suppression`)
  }

  async putMoneyMomentsSuppression(settings: {
    channel: string
    muted_until?: string
    daily_cap?: number
  }) {
    return this.request<{ status: string; message: string }>(`/api/moneymoments/suppression`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    })
  }

  async getMoneyMomentsCTR(days?: number) {
    const params = days ? `?days=${days}` : ''
    return this.request<{
      total_delivered: number
      total_viewed: number
      total_clicked: number
      view_rate: number
      ctr: number
    }>(`/api/moneymoments/analytics/ctr${params}`)
  }

  async getMoneyMomentsBehaviorShift(months?: number) {
    const params = months ? `?months=${months}` : ''
    return this.request<{
      signals: Array<{
        as_of_date: string
        wants_share_30d: number | null
        wants_vs_plan_pct: number | null
        assets_vs_plan_pct: number | null
        rank1_goal_underfund_pct: number | null
      }>
      wants_shift: number | null
      months_tracked: number
    }>(`/api/moneymoments/analytics/behavior-shift${params}`)
  }

  // Categories and Subcategories APIs
  async getCategories() {
    return this.request<Array<{
      category_code: string
      category_name: string
      txn_type?: string
    }>>('/api/categories')
  }

  async getSubcategories(categoryCode: string) {
    return this.request<Array<{
      subcategory_code: string
      subcategory_name: string
      category_code: string
    }>>(`/api/categories/${categoryCode}/subcategories`)
  }
}

export const apiClient = new ApiClient(API_BASE_URL)

