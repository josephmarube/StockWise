import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import AuthShell, { Brand } from '../components/AuthShell'
import { Field } from '../components/ui'

const TOO_SHORT = 'Use at least 8 characters.'

// Creates a new business with the person signing up as its admin.
export default function Signup() {
  const { user, signup } = useAuth()
  const nav = useNavigate()
  const [f, setF] = useState({ business_name: '', name: '', email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))

  if (user) return <Navigate to="/" replace />

  async function submit(e) {
    e.preventDefault()
    const errs = {}
    if (f.business_name.trim().length < 2) errs.business_name = 'Enter your shop or business name.'
    if (!f.name.trim()) errs.name = 'Enter your name.'
    if (!/^\S+@\S+\.\S+$/.test(f.email.trim())) errs.email = 'Enter a valid email address.'
    if (f.password.length < 8) errs.password = TOO_SHORT
    setErrors(errs)
    if (Object.keys(errs).length) return
    setBusy(true)
    try {
      await signup({ ...f, business_name: f.business_name.trim(), name: f.name.trim(), email: f.email.trim() })
      nav('/', { replace: true })
    } catch (err) {
      if (err.status === 409) setErrors({ email: err.message })
      else if (Object.keys(err.fields || {}).length) setErrors(err.fields)
      else setErrors({ form: err.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell tagline="Your shop's stock, in its own private space. Add your staff when you're ready.">
      <form className="login-form" onSubmit={submit} noValidate>
        <Brand />
        <div>
          <h1>Create your business</h1>
          <p className="login-sub">You'll be its admin. It takes under a minute.</p>
        </div>
        <Field label="Business name" id="s-biz" error={errors.business_name} hint="For example: Mama Njeri Duka">
          <input id="s-biz" value={f.business_name} onChange={set('business_name')} maxLength={120} autoComplete="organization" />
        </Field>
        <Field label="Your name" id="s-name" error={errors.name}>
          <input id="s-name" value={f.name} onChange={set('name')} maxLength={120} autoComplete="name" />
        </Field>
        <Field label="Email" id="s-email" error={errors.email}>
          <input id="s-email" type="email" value={f.email} onChange={set('email')} autoComplete="email" inputMode="email" />
        </Field>
        <Field label="Password" id="s-pw" error={errors.password} hint="At least 8 characters.">
          <input id="s-pw" type="password" value={f.password} onChange={set('password')} autoComplete="new-password" />
        </Field>
        {errors.form && <p className="form-error" role="alert">{errors.form}</p>}
        <button className="btn btn-primary btn-block btn-lg" disabled={busy}>{busy ? 'Creating…' : 'Create business'}</button>
        <p className="login-switch">Already have an account? <Link to="/login" className="link">Log in</Link></p>
        <p className="login-help">Joining an existing shop? Ask its admin for an invite link.</p>
      </form>
    </AuthShell>
  )
}
