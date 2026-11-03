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

  const login = useCallback(async (email, password) => {
    const res = await api.post('/api/auth/login', { email, password })
    tokenStore.set(res.access_token)
    setNotice('')
    setUser(res.user)
    return res.user
  }, [])

  const value = useMemo(() => ({
    user, ready, login, logout, notice,
    isAdmin: user?.role === 'ADMIN',
  }), [user, ready, login, logout, notice])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
