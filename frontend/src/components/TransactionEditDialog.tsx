import { useState, useEffect } from 'react'
import { X } from 'lucide-react'

interface TransactionEditDialogProps {
  isOpen: boolean
  onClose: () => void
  onSave: (updates: TransactionUpdates) => Promise<void>
  transaction: TransactionData | null
}

export interface TransactionData {
  id?: string
  txn_id?: string
  merchant?: string
  merchant_name_norm?: string
  amount?: number | string
  direction?: 'credit' | 'debit' | 'credit_card'
  transaction_type?: 'credit' | 'debit'
  category?: string
  category_code?: string
  subcategory?: string
  subcategory_code?: string
  description?: string
  transaction_date?: string | Date
  txn_date?: string | Date
  currency?: string
  payment_method?: string
}

export interface TransactionUpdates {
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

export default function TransactionEditDialog({
  isOpen,
  onClose,
  onSave,
  transaction
}: TransactionEditDialogProps) {
  const [formData, setFormData] = useState<TransactionUpdates>({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [categories, setCategories] = useState<CategoryOption[]>([])
  const [subcategories, setSubcategories] = useState<SubcategoryOption[]>([])
  const [loadingCategories, setLoadingCategories] = useState(false)

  // Initialize form data when transaction changes
  useEffect(() => {
    if (transaction) {
      // Format date for input (YYYY-MM-DD)
      const txnDate = transaction.transaction_date || transaction.txn_date
      const dateStr = txnDate 
        ? (txnDate instanceof Date 
            ? txnDate.toISOString().split('T')[0] 
            : typeof txnDate === 'string' 
              ? txnDate.split('T')[0] 
              : '')
        : ''

      // Check if it's a credit card transaction (by payment_method or category)
      const isCreditCard = (transaction as any).payment_method === 'credit_card' || 
                           transaction.category_code === 'credit_cards'
      // Use 'debit' for credit_card type in form state (UI shows it as "Credit Card")
      const direction = isCreditCard ? 'debit' : 
                       (transaction.direction || transaction.transaction_type || 'debit')
      
      setFormData({
        description: transaction.description || '',
        merchant: transaction.merchant || transaction.merchant_name_norm || '',
        amount: Number(transaction.amount) || 0,
        direction: direction as 'credit' | 'debit',
        transaction_type: transaction.transaction_type || transaction.direction || 'debit',
        category: transaction.category || transaction.category_code || '',
        subcategory: transaction.subcategory || transaction.subcategory_code || '',
        transaction_date: dateStr,
        currency: transaction.currency || 'INR',
        payment_method: isCreditCard ? 'credit_card' : undefined
      })
      setError('')
    }
  }, [transaction])

  // Load categories when modal opens
  useEffect(() => {
    if (isOpen && transaction) {
      loadCategories()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, transaction])

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
      // Try to fetch categories from API
      try {
        const { apiClient } = await import('../lib/api')
        const apiCategories = await apiClient.getCategories()
        const formatted = apiCategories.map((cat: { category_code: string; category_name: string }) => ({
          category_code: cat.category_code,
          category_name: cat.category_name
        }))
        setCategories(formatted)
      } catch {
        // Fallback to common categories if API fails
        const commonCategories: CategoryOption[] = [
          { category_code: 'dining', category_name: 'Dining & Food' },
          { category_code: 'groceries', category_name: 'Groceries' },
          { category_code: 'shopping', category_name: 'Shopping' },
          { category_code: 'utilities', category_name: 'Utilities' },
          { category_code: 'auto_taxi', category_name: 'Transport & Taxi' },
          { category_code: 'flight', category_name: 'Flights' },
          { category_code: 'train', category_name: 'Trains' },
          { category_code: 'rent', category_name: 'Rent & Housing' },
          { category_code: 'investments', category_name: 'Investments' },
          { category_code: 'loans', category_name: 'Loans & EMI' },
          { category_code: 'credit_cards', category_name: 'Credit Cards' },
          { category_code: 'income', category_name: 'Income' },
          { category_code: 'others', category_name: 'Others' }
        ]
        setCategories(commonCategories)
      }
    } catch (err) {
      console.error('Failed to load categories:', err)
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
      // Try to fetch subcategories from API
      const { apiClient } = await import('../lib/api')
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
        // Nightlife & Eating Out
        nightlife: [
          { subcategory_code: 'food_delivery', subcategory_name: 'Food Delivery (Swiggy/Zomato)' },
          { subcategory_code: 'restaurant_dineout', subcategory_name: 'Restaurant / Dine-out' },
          { subcategory_code: 'coffee_cafe', subcategory_name: 'Cafe / Coffee Shops' },
          { subcategory_code: 'pub_bar', subcategory_name: 'Pubs / Bars / Clubs' },
          { subcategory_code: 'pan_shop', subcategory_name: 'Paan / Cigarette / Pan Shop' },
          { subcategory_code: 'party_event', subcategory_name: 'Party / Event / Lounge' }
        ],
        // Home & Daily Needs
        home_needs: [
          { subcategory_code: 'groceries', subcategory_name: 'Groceries / Supermarket' },
          { subcategory_code: 'vegetables_fruits', subcategory_name: 'Vegetables / Fruits' },
          { subcategory_code: 'electricity_home', subcategory_name: 'Electricity Bill (Home)' },
          { subcategory_code: 'waterbill_home', subcategory_name: 'Water Bill (Home)' },
          { subcategory_code: 'gas_lpg', subcategory_name: 'LPG / Gas Cylinder' },
          { subcategory_code: 'rent_home', subcategory_name: 'House Rent' },
          { subcategory_code: 'maintenance_society', subcategory_name: 'Maintenance / Society Charges' },
          { subcategory_code: 'household_items', subcategory_name: 'Household Items / Essentials' }
        ],
        // Shopping & Lifestyle
        shopping: [
          { subcategory_code: 'online_shopping', subcategory_name: 'Online Shopping (Amazon/Flipkart)' },
          { subcategory_code: 'apparel', subcategory_name: 'Apparel / Clothing / Footwear' },
          { subcategory_code: 'electronics', subcategory_name: 'Electronics / Gadgets' },
          { subcategory_code: 'app_amazon', subcategory_name: 'Amazon' },
          { subcategory_code: 'app_flipkart', subcategory_name: 'Flipkart' },
          { subcategory_code: 'app_myntra', subcategory_name: 'Myntra' },
          { subcategory_code: 'home_appliances', subcategory_name: 'Home Appliances / Furniture' },
          { subcategory_code: 'beauty_personalcare', subcategory_name: 'Beauty / Personal Care' },
          { subcategory_code: 'jewellery', subcategory_name: 'Jewellery / Gold' }
        ],
        // Transport & Travel
        transport: [
          { subcategory_code: 'fuel_petrol', subcategory_name: 'Fuel (Petrol/Diesel)' },
          { subcategory_code: 'toll_fastag', subcategory_name: 'Toll / FASTag' },
          { subcategory_code: 'cab_ride', subcategory_name: 'Cab / Taxi / Ride-hailing (Uber/Ola)' },
          { subcategory_code: 'auto_rickshaw', subcategory_name: 'Auto / Rickshaw' },
          { subcategory_code: 'bus_train', subcategory_name: 'Bus / Train / Metro' },
          { subcategory_code: 'flight', subcategory_name: 'Flights' },
          { subcategory_code: 'hotel_stay', subcategory_name: 'Hotels / Stays' },
          { subcategory_code: 'parking', subcategory_name: 'Parking' }
        ],
        // Old category codes for backward compatibility
        dining: [
          { subcategory_code: 'food_swiggy', subcategory_name: 'Swiggy' },
          { subcategory_code: 'food_zomato', subcategory_name: 'Zomato' },
          { subcategory_code: 'food_restaurant', subcategory_name: 'Restaurant' },
          { subcategory_code: 'food_cafe', subcategory_name: 'Cafe' }
        ],
        groceries: [
          { subcategory_code: 'groc_bigbasket', subcategory_name: 'BigBasket' },
          { subcategory_code: 'groc_blinkit', subcategory_name: 'Blinkit' },
          { subcategory_code: 'groc_zepto', subcategory_name: 'Zepto' },
          { subcategory_code: 'groc_dmart', subcategory_name: 'DMart' }
        ],
        auto_taxi: [
          { subcategory_code: 'ride_ola', subcategory_name: 'Ola' },
          { subcategory_code: 'ride_uber', subcategory_name: 'Uber' },
          { subcategory_code: 'ride_rapido', subcategory_name: 'Rapido' }
        ],
        investments: [
          { subcategory_code: 'mf_sip', subcategory_name: 'Mutual Fund SIP' },
          { subcategory_code: 'mf_lumpsum', subcategory_name: 'Mutual Fund Lump Sum' },
          { subcategory_code: 'stocks_direct', subcategory_name: 'Stocks (Direct)' },
          { subcategory_code: 'stocks_etf', subcategory_name: 'ETFs / Index Funds' },
          { subcategory_code: 'bonds_government', subcategory_name: 'Government Bonds' },
          { subcategory_code: 'sgb_gold', subcategory_name: 'Sovereign Gold Bonds' },
          { subcategory_code: 'crypto', subcategory_name: 'Cryptocurrency' }
        ],
        loans: [
          { subcategory_code: 'loan_personal', subcategory_name: 'Personal Loan EMI' },
          { subcategory_code: 'loan_home', subcategory_name: 'Home Loan EMI' },
          { subcategory_code: 'loan_car', subcategory_name: 'Car Loan EMI' },
          { subcategory_code: 'loan_bike', subcategory_name: 'Bike Loan EMI' },
          { subcategory_code: 'loan_education', subcategory_name: 'Education Loan EMI' },
          { subcategory_code: 'loan_gold', subcategory_name: 'Gold Loan EMI' },
          { subcategory_code: 'loan_overdraft', subcategory_name: 'Overdraft / Cash Credit' }
        ],
        credit_cards: [
          { subcategory_code: 'cc_bill_payment', subcategory_name: 'Credit Card Bill Payment' },
          { subcategory_code: 'cc_interest', subcategory_name: 'Credit Card Interest' },
          { subcategory_code: 'cc_fees', subcategory_name: 'Credit Card Fees' },
          { subcategory_code: 'cc_cashback', subcategory_name: 'Credit Card Cashback' },
          { subcategory_code: 'cc_emi', subcategory_name: 'Credit Card EMI' }
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
    
    if (!transaction) return

    // Build updates object (only include changed fields)
    const updates: TransactionUpdates = {}
    
    if (formData.description !== undefined && formData.description !== transaction.description) {
      updates.description = formData.description
    }
    if (formData.merchant !== undefined && formData.merchant !== (transaction.merchant || transaction.merchant_name_norm)) {
      updates.merchant = formData.merchant
    }
    if (formData.amount !== undefined && formData.amount !== Number(transaction.amount)) {
      updates.amount = formData.amount
    }
    if (formData.direction !== undefined && formData.direction !== (transaction.direction || transaction.transaction_type)) {
      // Handle credit_card type - store as debit with payment_method
      if (formData.direction === 'credit_card') {
        updates.direction = 'debit'
        updates.transaction_type = 'debit'
        updates.payment_method = 'credit_card'
      } else {
        updates.direction = formData.direction
        updates.transaction_type = formData.direction
        updates.payment_method = undefined
      }
    }
    if (formData.category !== undefined && formData.category !== (transaction.category || transaction.category_code)) {
      updates.category = formData.category
      updates.category_code = formData.category
    }
    if (formData.subcategory !== undefined && formData.subcategory !== (transaction.subcategory || transaction.subcategory_code)) {
      updates.subcategory = formData.subcategory
      updates.subcategory_code = formData.subcategory
    }
    if (formData.transaction_date !== undefined && formData.transaction_date !== (transaction.transaction_date || transaction.txn_date)) {
      updates.transaction_date = formData.transaction_date
    }
    if (formData.currency !== undefined && formData.currency !== transaction.currency) {
      updates.currency = formData.currency
    }

    if (Object.keys(updates).length === 0) {
      onClose()
      return
    }

    setLoading(true)
    try {
      await onSave(updates)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save transaction')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen || !transaction) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-card rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto border border-border">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border sticky top-0 bg-card z-10">
          <h2 className="text-xl font-semibold text-foreground">
            Edit Transaction
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
              Description
            </label>
            <input
              type="text"
              value={formData.description || ''}
              onChange={e => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-primary focus:border-primary"
              placeholder="Transaction description"
            />
          </div>

          {/* Merchant */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Merchant Name
            </label>
            <input
              type="text"
              value={formData.merchant || ''}
              onChange={e => setFormData({ ...formData, merchant: e.target.value })}
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-primary focus:border-primary"
              placeholder="Merchant name"
            />
          </div>

          {/* Amount and Direction */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Amount (₹)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={formData.amount || 0}
                onChange={e => setFormData({ ...formData, amount: Number(e.target.value) || 0 })}
                className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Type
              </label>
              <select
                value={formData.direction || 'debit'}
                onChange={e => {
                  const dir = e.target.value as 'credit' | 'debit' | 'credit_card'
                  // For credit_card, set direction as debit but mark payment_method
                  if (dir === 'credit_card') {
                    setFormData({ ...formData, direction: 'debit', transaction_type: 'debit', payment_method: 'credit_card' })
                  } else {
                    setFormData({ ...formData, direction: dir, transaction_type: dir, payment_method: undefined })
                  }
                }}
                className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
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
              Transaction Date
            </label>
            <input
              type="date"
              value={formData.transaction_date || ''}
              onChange={e => setFormData({ ...formData, transaction_date: e.target.value })}
              className="w-full px-4 py-2 bg-secondary border border-border rounded-lg text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
            />
          </div>

          {/* Category and Subcategory */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Category
              </label>
              <select
                value={formData.category || ''}
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
                value={formData.subcategory || ''}
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
              value={formData.currency || 'INR'}
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
              {loading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

