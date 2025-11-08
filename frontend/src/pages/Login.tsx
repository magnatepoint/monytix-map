import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Loading from '../components/Loading'
import { CreditCard, Mail, Lock, Eye, EyeOff } from 'lucide-react'

export default function Login() {
  const { user, loading, signInWithGoogle, signInWithEmail, signUpWithEmail } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [isSignUp, setIsSignUp] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadingAuth, setLoadingAuth] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // Check for error in URL params (from OAuth callback)
  useEffect(() => {
    const errorParam = searchParams.get('error')
    if (errorParam) {
      setError(decodeURIComponent(errorParam))
      // Clean up URL
      navigate('/login', { replace: true })
    }
  }, [searchParams, navigate])

  useEffect(() => {
    // If user is logged in, redirect to home
    if (user) {
      navigate('/')
    }
  }, [user, navigate])

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccessMessage(null)
    setLoadingAuth(true)

    try {
      if (isSignUp) {
        const result = await signUpWithEmail(email, password)
        if (result.error) {
          setError(result.error.message || 'Failed to sign up')
        } else {
          setSuccessMessage('Check your email to confirm your account!')
          // Reset form
          setEmail('')
          setPassword('')
        }
      } else {
        const result = await signInWithEmail(email, password)
        if (result.error) {
          setError(result.error.message || 'Failed to sign in')
        }
        // Success will be handled by auth state change
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setLoadingAuth(false)
    }
  }

  if (loading) return <Loading />
  if (user) return <Loading /> // Will redirect automatically

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-secondary/20 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-pulse-slow"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '1s' }}></div>
      </div>

      <div className="max-w-md w-full space-y-8 relative z-10">
        <div className="bg-card/80 backdrop-blur-xl border border-border rounded-2xl shadow-2xl p-10 glass">
          <div className="text-center space-y-6">
            <div className="flex justify-center mb-6">
              <div className="relative">
                <div className="h-20 w-20 bg-gradient-to-br from-[#F4D03F] via-[#D4AF37] to-[#F4D03F] rounded-2xl flex items-center justify-center shadow-lg shadow-primary/30">
                  <CreditCard className="h-10 w-10 text-background" />
                </div>
                <div className="absolute -top-1 -right-1 h-6 w-6 bg-success rounded-full border-4 border-card animate-pulse"></div>
              </div>
            </div>
            <div>
              <h2 className="text-4xl font-bold text-foreground mb-2 tracking-tight">
                Welcome to <span className="brand-gold-text">Monytix</span>
              </h2>
              <p className="text-muted-foreground text-lg">
                Your AI-powered financial command center
              </p>
            </div>
          </div>

          <div className="mt-8 space-y-6">
            {/* Email/Password Form */}
            <form onSubmit={handleEmailAuth} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="email" className="text-sm font-medium text-foreground">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    placeholder="you@example.com"
                    className="w-full pl-10 pr-4 py-3 bg-background border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="text-sm font-medium text-foreground">
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                    placeholder="••••••••"
                    className="w-full pl-10 pr-12 py-3 bg-background border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>

              {error && (
                <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-xl text-sm text-destructive">
                  {error}
                </div>
              )}

              {successMessage && (
                <div className="p-3 bg-success/10 border border-success/20 rounded-xl text-sm text-success">
                  {successMessage}
                </div>
              )}

              <button
                type="submit"
                disabled={loadingAuth}
                className="w-full bg-primary text-primary-foreground rounded-xl px-6 py-3 font-semibold hover:bg-primary/90 transition-all duration-200 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loadingAuth ? 'Please wait...' : isSignUp ? 'Sign Up' : 'Sign In'}
              </button>
            </form>

            {/* Toggle between Sign In and Sign Up */}
            <div className="text-center">
              <button
                type="button"
                onClick={() => {
                  setIsSignUp(!isSignUp)
                  setError(null)
                  setSuccessMessage(null)
                }}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {isSignUp ? (
                  <>Already have an account? <span className="font-semibold text-primary">Sign In</span></>
                ) : (
                  <>Don't have an account? <span className="font-semibold text-primary">Sign Up</span></>
                )}
              </button>
            </div>

            {/* Divider */}
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-4 bg-card text-muted-foreground">Or continue with</span>
              </div>
            </div>

            {/* Google OAuth Button */}
            <button
              onClick={signInWithGoogle}
              className="w-full flex items-center justify-center gap-3 bg-card border-2 border-border rounded-xl px-6 py-4 font-semibold text-foreground hover:bg-secondary hover:border-primary/50 transition-all duration-200 shadow-lg hover:shadow-xl hover:shadow-primary/10 group"
            >
              <svg className="w-6 h-6 transition-transform group-hover:scale-110" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              <span>Continue with Google</span>
            </button>

            <div className="text-center">
              <p className="text-sm text-muted-foreground">
                Secure authentication powered by Supabase
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4 pt-8 mt-8 border-t border-border">
            <div className="text-center group">
              <div className="text-2xl font-bold gradient-text-primary group-hover:scale-110 transition-transform">Console</div>
              <div className="text-xs text-muted-foreground mt-1">Dashboard</div>
            </div>
            <div className="text-center group">
              <div className="text-2xl font-bold gradient-text-accent group-hover:scale-110 transition-transform">SpendSense</div>
              <div className="text-xs text-muted-foreground mt-1">Insights</div>
            </div>
            <div className="text-center group">
              <div className="text-2xl font-bold text-success group-hover:scale-110 transition-transform">Budget</div>
              <div className="text-xs text-muted-foreground mt-1">Track</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

