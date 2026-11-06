import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import AuthShell, { Brand } from '../components/AuthShell'
import { Field } from '../components/ui'

export default function Login() {
  const { user, login, notice } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={loc.state?.from || '/'} replace />

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError('Enter the email address for your account.')
    if (!password) return setError('Enter your password.')
    setBusy(true)
    try {
      await login(email.trim(), password)
      nav(loc.state?.from || '/', { replace: true })
    } catch (err) {
      setError(err.status === 401 ? 'That email and password do not match an account.' : err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell tagline="Know what is on your shelves before a customer asks.">
      <form className="login-form" onSubmit={submit} noValidate>
        <Brand />
        <h1>Log in</h1>
        {notice && <p className="login-notice">{notice}</p>}
        <Field label="Email" id="email">
          <input id="email" type="email" autoComplete="username" value={email}
            onChange={(e) => setEmail(e.target.value)} inputMode="email" />
        </Field>
        <Field label="Password" id="password">
          <input id="password" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} />
        </Field>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="btn btn-primary btn-block btn-lg" disabled={busy}>{busy ? 'Logging in…' : 'Log in'}</button>
        <p className="login-help">Forgot your password? Ask your shop admin to reset it.</p>
        <p className="login-switch">New to StockWise? <Link to="/signup" className="link">Create an account for your business</Link></p>
      </form>
    </AuthShell>
  )
}
