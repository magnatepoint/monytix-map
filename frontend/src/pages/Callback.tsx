import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import Loading from '../components/Loading'

export default function Callback() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Check for error in URL params
        const error = searchParams.get('error')
        const errorDescription = searchParams.get('error_description')
        
        if (error) {
          console.error('OAuth error:', error, errorDescription)
          navigate(`/login?error=${encodeURIComponent(errorDescription || error)}`)
          return
        }

        // Handle the OAuth callback - Supabase handles the hash automatically
        // We just need to wait for the session to be set
        const { data: { session }, error: sessionError } = await supabase.auth.getSession()
        
        if (sessionError) {
          console.error('Error getting session:', sessionError)
          navigate(`/login?error=${encodeURIComponent(sessionError.message)}`)
          return
        }

        if (session) {
          // Successfully authenticated
          navigate('/')
        } else {
          // Wait a bit for the session to be set (OAuth callback might still be processing)
          setTimeout(async () => {
            const { data: { session: retrySession } } = await supabase.auth.getSession()
            if (retrySession) {
              navigate('/')
            } else {
              navigate('/login?error=authentication_failed')
            }
          }, 1000)
        }
      } catch (error) {
        console.error('Error in callback:', error)
        navigate(`/login?error=${encodeURIComponent(error instanceof Error ? error.message : 'callback_error')}`)
      }
    }

    handleCallback()
  }, [navigate, searchParams])

  return <Loading />
}


