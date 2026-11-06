import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, setUnauthorizedHandler, tokenStore } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)
  const [notice, setNotice] = useState('')

  const logout = useCallback((message = '') => {
    tokenStore.clear()
    setUser(null)
    setNotice(message)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => logout('Your session has ended. Log in again to continue.'))
    if (!tokenStore.get()) { setReady(true); return }
    api.get('/api/auth/me')
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setReady(true))
  }, [logout])

  // Login, signup and accepting an invite all return a token and the user (with their business).
  const startSession = useCallback((res) => {
    tokenStore.set(res.access_token)
    setNotice('')
    setUser(res.user)
    return res.user
  }, [])

  const login = useCallback(async (email, password) =>
    startSession(await api.post('/api/auth/login', { email, password })), [startSession])

  const signup = useCallback(async (body) =>
    startSession(await api.post('/api/auth/signup', body)), [startSession])

  const acceptInvite = useCallback(async (body) =>
    startSession(await api.post('/api/invites/accept', body)), [startSession])

  const setBusiness = useCallback((business) => setUser((u) => (u ? { ...u, business } : u)), [])

  const value = useMemo(() => ({
    user, ready, login, signup, acceptInvite, logout, notice, setBusiness,
    isAdmin: user?.role === 'ADMIN',
    business: user?.business,
  }), [user, ready, login, signup, acceptInvite, logout, notice, setBusiness])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
