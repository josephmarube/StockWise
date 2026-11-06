import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import AuthShell, { Brand } from '../components/AuthShell'
import { Field, Spinner } from '../components/ui'

// Opened from an invite link: /join/<token>. Creates the member's account in that business.
export default function Join() {
  const { token } = useParams()
  const { user, acceptInvite, logout } = useAuth()
  const nav = useNavigate()
  const [invite, setInvite] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [f, setF] = useState({ name: '', email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))

  useEffect(() => {
    api.get(`/api/invites/preview/${encodeURIComponent(token)}`)
      .then((inv) => { setInvite(inv); if (inv.email) setF((x) => ({ ...x, email: inv.email })) })
      .catch((e) => setLoadError(e.message))
  }, [token])

  if (user && !busy) {
    return (
      <AuthShell tagline="Your shop's stock, in its own private space.">
        <div className="login-form">
          <Brand />
          <h1>You're already logged in</h1>
          <p className="login-sub">You are logged in as {user.email} ({user.business?.name}). To accept this invite with a different account, log out first.</p>
          <button className="btn btn-primary btn-block" onClick={() => logout()}>Log out and continue</button>
          <Link to="/" className="link">Go to my dashboard</Link>
        </div>
      </AuthShell>
    )
  }

  async function submit(e) {
    e.preventDefault()
    const errs = {}
    if (!f.name.trim()) errs.name = 'Enter your name.'
    if (!/^\S+@\S+\.\S+$/.test(f.email.trim())) errs.email = 'Enter a valid email address.'
    if (f.password.length < 8) errs.password = 'Use at least 8 characters.'
    setErrors(errs)
    if (Object.keys(errs).length) return
    setBusy(true)
    try {
      await acceptInvite({ token, name: f.name.trim(), email: f.email.trim(), password: f.password })
      nav('/', { replace: true })
    } catch (err) {
      setBusy(false)
      if (err.status === 409 || /email/i.test(err.message)) setErrors({ email: err.message })
      else setErrors({ form: err.message })
    }
  }

  if (!invite && !loadError) return <div className="center-screen"><Spinner /></div>
  if (loadError) {
    return (
      <AuthShell tagline="Your shop's stock, in its own private space.">
        <div className="login-form">
          <Brand />
          <h1>This invite can't be used</h1>
          <p className="form-error" role="alert">{loadError}</p>
          <p className="login-switch">Already have an account? <Link to="/login" className="link">Log in</Link></p>
        </div>
      </AuthShell>
    )
  }

  const roleLabel = invite.role === 'ADMIN' ? 'an admin' : 'staff'
  return (
    <AuthShell tagline={`Join ${invite.business_name} on StockWise.`}>
      <form className="login-form" onSubmit={submit} noValidate>
        <Brand />
        <div>
          <h1>Join {invite.business_name}</h1>
          <p className="login-sub">You've been invited as {roleLabel}. Set up your account to start.</p>
        </div>
        <Field label="Your name" id="j-name" error={errors.name}>
          <input id="j-name" value={f.name} onChange={set('name')} maxLength={120} autoComplete="name" />
        </Field>
        <Field label="Email" id="j-email" error={errors.email} hint={invite.email ? 'This invite is for this email address.' : undefined}>
          <input id="j-email" type="email" value={f.email} onChange={set('email')} autoComplete="email" readOnly={!!invite.email} inputMode="email" />
        </Field>
        <Field label="Password" id="j-pw" error={errors.password} hint="At least 8 characters.">
          <input id="j-pw" type="password" value={f.password} onChange={set('password')} autoComplete="new-password" />
        </Field>
        {errors.form && <p className="form-error" role="alert">{errors.form}</p>}
        <button className="btn btn-primary btn-block btn-lg" disabled={busy}>{busy ? 'Joining…' : `Join ${invite.business_name}`}</button>
      </form>
    </AuthShell>
  )
}
