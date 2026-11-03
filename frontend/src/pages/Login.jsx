import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
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
    <div className="login">
      <div className="login-side" aria-hidden="true">
        <div className="login-shelves">
          {[62, 35, 88, 18, 70, 46, 95, 28].map((h, i) => (
            <div key={i} className={`shelf-bar ${h < 30 ? 'is-low' : ''}`} style={{ '--h': `${h}%`, '--d': `${i * 70}ms` }} />
          ))}
        </div>
        <p className="login-tag">Know what is on your shelves before a customer asks.</p>
      </div>

      <form className="login-form" onSubmit={submit} noValidate>
        <div className="brand brand-dark">
          <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="17" width="6" height="10" rx="1.5" fill="#1F2A5C" opacity=".55"/><rect x="13" y="11" width="6" height="16" rx="1.5" fill="#1F2A5C" opacity=".8"/><rect x="21" y="5" width="6" height="22" rx="1.5" fill="#D99A00"/></svg>
          <span>StockWise</span>
        </div>
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
        <p className="login-help">Forgot your password? Ask the shop admin to reset it.</p>
      </form>
    </div>
  )
}
