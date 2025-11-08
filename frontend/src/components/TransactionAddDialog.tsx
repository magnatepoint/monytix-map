import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { apiClient } from '../lib/api'

interface TransactionAddDialogProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

interface CategoryOption {
  category_code: string
  category_name: string
  subcategories?: SubcategoryOption[]
}

interface SubcategoryOption {
  subcategory_code: string
  subcategory_name: string
}

export default function TransactionAddDialog({
  isOpen,
  onClose,
  onSuccess
}: TransactionAddDialogProps) {
  const [formData, setFormData] = useState({
    description: '',
    merchant: '',
    amount: '',
    direction: 'debit' as 'credit' | 'debit' | 'credit_card',
    transaction_type: 'debit' as 'credit' | 'debit',
    category: '',
    subcategory: '',
    transaction_date: new Date().toISOString().split('T')[0],
    currency: 'INR',
    payment_method: undefined as string | undefined
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [categories, setCategories] = useState<CategoryOption[]>([])
  const [subcategories, setSubcategories] = useState<SubcategoryOption[]>([])
  const [loadingCategories, setLoadingCategories] = useState(false)

  // Load categories when modal opens
  useEffect(() => {
    if (isOpen) {
      loadCategories()
      // Reset form when opening
      setFormData({
        description: '',
        merchant: '',
        amount: '',
        direction: 'debit',
        transaction_type: 'debit',
        category: '',
        subcategory: '',
        transaction_date: new Date().toISOString().split('T')[0],
        currency: 'INR',
        payment_method: undefined
      })
      setError('')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  // Load subcategories when category changes
  useEffect(() => {
    if (isOpen && formData.category) {
      loadSubcategories(formData.category)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, formData.category])

  const loadCategories = async () => {
    setLoadingCategories(true)
    try {
      const apiCategories = await apiClient.getCategories()
      const formatted = apiCategories.map((cat: { category_code: string; category_name: string }) => ({
        category_code: cat.category_code,
        category_name: cat.category_name
      }))
      setCategories(formatted)
    } catch {
      // Fallback to common categories if API fails
      const commonCategories: CategoryOption[] = [
        { category_code: 'nightlife', category_name: 'Nightlife & Eating Out' },
        { category_code: 'home_needs', category_name: 'Home & Daily Needs' },
        { category_code: 'transport', category_name: 'Transport & Travel' },
        { category_code: 'shopping', category_name: 'Shopping & Lifestyle' },
        { category_code: 'bills', category_name: 'Bills & Recharges' },
        { category_code: 'health', category_name: 'Health & Wellness' },
        { category_code: 'loans', category_name: 'Loans & EMI' },
        { category_code: 'insurance', category_name: 'Insurance' },
        { category_code: 'banks', category_name: 'Banking & Savings' },
        { category_code: 'govt_tax', category_name: 'Government & Taxes' },
        { category_code: 'transfers', category_name: 'Transfers' },
        { category_code: 'credit_cards', category_name: 'Credit Cards' },
        { category_code: 'income', category_name: 'Income' },
        { category_code: 'others', category_name: 'Others' }
      ]
      setCategories(commonCategories)
    } finally {
      setLoadingCategories(false)
    }
  }

  const loadSubcategories = async (categoryCode: string) => {
    if (!categoryCode) {
      setSubcategories([])
      return
    }
    
    try {
      const apiSubcategories = await apiClient.getSubcategories(categoryCode)
      const formatted = apiSubcategories.map((sub: { subcategory_code: string; subcategory_name: string }) => ({
        subcategory_code: sub.subcategory_code,
        subcategory_name: sub.subcategory_name
      }))
      setSubcategories(formatted)
    } catch (err) {
      console.error('Failed to load subcategories from API:', err)
      // Fallback to common subcategories if API fails
      const subcategoryMap: Record<string, SubcategoryOption[]> = {
        nightlife: [
          { subcategory_code: 'food_delivery', subcategory_name: 'Food Delivery (Swiggy/Zomato)' },
          { subcategory_code: 'restaurant_dineout', subcategory_name: 'Restaurant / Dine-out' },
          { subcategory_code: 'coffee_cafe', subcategory_name: 'Cafe / Coffee Shops' },
          { subcategory_code: 'pub_bar', subcategory_name: 'Pubs / Bars / Clubs' }
        ],
        home_needs: [
          { subcategory_code: 'groceries', subcategory_name: 'Groceries / Supermarket' },
          { subcategory_code: 'electricity_home', subcategory_name: 'Electricity Bill' },
          { subcategory_code: 'waterbill_home', subcategory_name: 'Water Bill' },
          { subcategory_code: 'gas_lpg', subcategory_name: 'LPG / Gas Cylinder' }
        ],
        transport: [
          { subcategory_code: 'cab_ride', subcategory_name: 'Cab / Taxi' },
          { subcategory_code: 'fuel_petrol', subcategory_name: 'Fuel' },
          { subcategory_code: 'flight', subcategory_name: 'Flights' },
          { subcategory_code: 'hotel_stay', subcategory_name: 'Hotels' }
        ],
        shopping: [
          { subcategory_code: 'online_shopping', subcategory_name: 'Online Shopping' },
          { subcategory_code: 'apparel', subcategory_name: 'Apparel / Clothing' },
          { subcategory_code: 'electronics', subcategory_name: 'Electronics' }
        ],
        bills: [
          { subcategory_code: 'mobile_recharge', subcategory_name: 'Mobile Recharge' },
          { subcategory_code: 'credit_card_due', subcategory_name: 'Credit Card Payment' }
        ]
      }
      setSubcategories(subcategoryMap[categoryCode] || [])
    }
  }

  const handleCategoryChange = (categoryCode: string) => {
    setFormData({ ...formData, category: categoryCode, subcategory: '' })
    loadSubcategories(categoryCode)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    // Validate required fields
    if (!formData.description.trim()) {
      setError('Description is required')
      return
    }
    
    const amount = parseFloat(formData.amount)
    if (!formData.amount || isNaN(amount) || amount <= 0) {
      setError('Please enter a valid amount (greater than 0)')
      return
    }

    setLoading(true)
    try {
      // Determine transaction type based on direction
      let transaction_type = formData.direction
      let payment_method = formData.payment_method
      
      if (formData.direction === 'credit_card') {
        transaction_type = 'debit'
        payment_method = 'credit_card'
      }

      await apiClient.createTransaction({
        amount: amount,
        currency: formData.currency,
        transaction_date: formData.transaction_date,
        description: formData.description.trim(),
        merchant: formData.merchant.trim() || undefined,
        category: formData.category || undefined,
        transaction_type: transaction_type,
        payment_method: payment_method
      })
      
      onSuccess()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create transaction')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-card rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto border border-border">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border sticky top-0 bg-card z-10">
          <h2 className="text-xl font-semibold text-foreground">
            Add Transaction
          </h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Description <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              value={formData.description}
              onChange={e => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-primary focus:border-primary"
              placeholder="Transaction description"
              required
            />
          </div>

          {/* Merchant */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Merchant Name
            </label>
            <input
              type="text"
              value={formData.merchant}
              onChange={e => setFormData({ ...formData, merchant: e.target.value })}
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-primary focus:border-primary"
              placeholder="Merchant name (optional)"
            />
          </div>

          {/* Amount and Direction */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Amount (₹) <span className="text-destructive">*</span>
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={formData.amount}
                onChange={e => setFormData({ ...formData, amount: e.target.value })}
                className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
                placeholder="0.00"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Type <span className="text-destructive">*</span>
              </label>
              <select
                value={formData.direction}
                onChange={e => {
                  const dir = e.target.value as 'credit' | 'debit' | 'credit_card'
                  if (dir === 'credit_card') {
                    setFormData({ ...formData, direction: dir, transaction_type: 'debit', payment_method: 'credit_card' })
                  } else {
                    setFormData({ ...formData, direction: dir, transaction_type: dir, payment_method: undefined })
                  }
                }}
                className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
                required
              >
                <option value="debit">Debit (Expense)</option>
                <option value="credit">Credit (Income)</option>
                <option value="credit_card">Credit Card</option>
              </select>
            </div>
          </div>

          {/* Date */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Transaction Date <span className="text-destructive">*</span>
            </label>
            <input
              type="date"
              value={formData.transaction_date}
              onChange={e => setFormData({ ...formData, transaction_date: e.target.value })}
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
              required
            />
          </div>

          {/* Category and Subcategory */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Category
              </label>
              <select
                value={formData.category}
                onChange={e => handleCategoryChange(e.target.value)}
                className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary focus:border-primary disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={loadingCategories}
              >
                <option value="">Select category...</option>
                {categories.map(cat => (
                  <option key={cat.category_code} value={cat.category_code}>
                    {cat.category_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Subcategory
              </label>
              <select
                value={formData.subcategory}
                onChange={e => setFormData({ ...formData, subcategory: e.target.value })}
                className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary focus:border-primary disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!formData.category || subcategories.length === 0}
              >
                <option value="">Select subcategory...</option>
                {subcategories.map(sub => (
                  <option key={sub.subcategory_code} value={sub.subcategory_code}>
                    {sub.subcategory_name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Currency */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Currency
            </label>
            <select
              value={formData.currency}
              onChange={e => setFormData({ ...formData, currency: e.target.value })}
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
            >
              <option value="INR">INR (₹)</option>
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
            </select>
          </div>

          {/* Error message */}
          {error && (
            <div className="bg-destructive/10 border border-destructive/20 text-destructive px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-border rounded-lg text-foreground hover:bg-secondary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-primary text-background rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={loading}
            >
              {loading ? 'Creating...' : 'Create Transaction'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

