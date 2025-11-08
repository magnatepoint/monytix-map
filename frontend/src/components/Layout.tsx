import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { LayoutDashboard, TrendingUp, Target, Clock, LogOut } from 'lucide-react'

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth()
  const location = useLocation()

  const navigation = [
    { name: 'Monytix Console', href: '/', icon: LayoutDashboard },
    { name: 'SpendSense', href: '/spendsense', icon: TrendingUp },
    { name: 'BudgetPilot', href: '/budgetpilot', icon: Target },
    { name: 'MoneyMoments', href: '/moneymoments', icon: Clock },
    { name: 'GoalCompass', href: '/goalcompass', icon: Target },
  ]

  const isActive = (href: string) => location.pathname === href

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div className="w-64 bg-card border-r border-border flex flex-col transition-all duration-300 relative">
        {/* Gradient accent */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary via-accent to-success opacity-60"></div>
        
        <div className="flex-1 flex flex-col pt-6 pb-4 overflow-y-auto">
          <div className="flex items-center flex-shrink-0 px-6 mb-8">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-[#F4D03F] to-[#D4AF37] flex items-center justify-center shadow-lg shadow-primary/30">
                <span className="text-background font-bold text-sm">M</span>
              </div>
              <h1 className="text-2xl font-bold brand-gold-text tracking-tight">Monytix</h1>
            </div>
          </div>
          <nav className="flex-1 px-3 space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon
              const active = isActive(item.href)
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`${
                    active
                      ? 'text-primary bg-secondary/80 border-l-4 border-primary shadow-sm'
                      : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
                  } group flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-all duration-200 relative`}
                >
                  <Icon className={`mr-3 h-5 w-5 transition-transform ${active ? 'scale-110' : ''}`} />
                  <span className="font-medium">{item.name}</span>
                  {active && (
                    <div className="absolute right-2 h-2 w-2 rounded-full bg-primary animate-pulse-slow"></div>
                  )}
                </Link>
              )
            })}
          </nav>
        </div>
        <div className="flex-shrink-0 flex border-t border-border p-4 bg-secondary/30">
          <div className="flex items-center w-full">
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center min-w-0">
                <div className="flex-shrink-0">
                  <div className="h-10 w-10 rounded-full bg-gradient-to-br from-[#F4D03F] via-[#D4AF37] to-[#F4D03F] flex items-center justify-center text-background font-semibold text-sm shadow-lg ring-2 ring-primary/20">
                    {user?.email?.[0].toUpperCase() || 'U'}
                  </div>
                </div>
                <div className="ml-3 min-w-0 max-w-[140px]">
                  <p className="text-xs font-medium text-foreground break-all leading-snug truncate">{user?.email}</p>
                </div>
              </div>
              <button
                onClick={signOut}
                className="p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-all duration-200"
                title="Sign Out"
              >
                <LogOut className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <main className="flex-1 relative overflow-y-auto focus:outline-none">
          <div className="py-8">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8">
              {children}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

