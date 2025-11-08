import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { User, Session } from '@supabase/supabase-js'
import { supabase } from '../lib/supabase'

interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  signInWithGoogle: () => Promise<void>
  signInWithEmail: (email: string, password: string) => Promise<{ error?: Error }>
  signUpWithEmail: (email: string, password: string) => Promise<{ error?: Error }>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signInWithGoogle = async () => {
    try {
      // Use environment variable if set, otherwise use current origin
      // IMPORTANT: Web frontend must use HTTP/HTTPS URLs, not custom URL schemes
      let redirectUrl = import.meta.env.VITE_OAUTH_REDIRECT_URL || `${window.location.origin}/callback`
      
      // Validate that redirect URL is HTTP/HTTPS (not a custom URL scheme)
      if (!redirectUrl.startsWith('http://') && !redirectUrl.startsWith('https://')) {
        console.warn('Invalid redirect URL (must be HTTP/HTTPS), using default:', redirectUrl)
        redirectUrl = `${window.location.origin}/callback`
      }
      
      console.log('Initiating Google OAuth with redirect URL:', redirectUrl)
      
      const { error, data } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: redirectUrl,
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          },
        },
      })
      
      if (error) {
        console.error('Error initiating Google OAuth:', error)
        throw error
      }
      
      // OAuth will redirect automatically, so we don't need to do anything here
    } catch (error) {
      console.error('Failed to initiate Google OAuth:', error)
      // Error will be handled by the callback page
    }
  }

  const signInWithEmail = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })
    if (error) {
      console.error('Error signing in:', error)
      return { error }
    }
    return {}
  }

  const signUpWithEmail = async (email: string, password: string) => {
    // Use environment variable if set, otherwise use current origin
    // IMPORTANT: Web frontend must use HTTP/HTTPS URLs, not custom URL schemes
    let redirectUrl = import.meta.env.VITE_OAUTH_REDIRECT_URL || `${window.location.origin}/callback`
    
    // Validate that redirect URL is HTTP/HTTPS (not a custom URL scheme)
    if (!redirectUrl.startsWith('http://') && !redirectUrl.startsWith('https://')) {
      console.warn('Invalid redirect URL (must be HTTP/HTTPS), using default:', redirectUrl)
      redirectUrl = `${window.location.origin}/callback`
    }
    
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: redirectUrl,
      },
    })
    if (error) {
      console.error('Error signing up:', error)
      return { error }
    }
    return {}
  }

  const signOut = async () => {
    const { error } = await supabase.auth.signOut()
    if (error) {
      console.error('Error signing out:', error)
      return
    }
    // Force navigation to login after sign-out
    window.location.assign('/login')
  }

  return (
    <AuthContext.Provider value={{ user, session, loading, signInWithGoogle, signInWithEmail, signUpWithEmail, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

