import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { useAuth } from '../lib/auth'
import { fmtDate } from '../lib/format'
import { Confirm, ErrorNote, Field, Icon, Modal, Spinner, useToast } from '../components/ui'

const TOO_SHORT = 'Use at least 8 characters.'

export default function Users() {
  const { user: me } = useAuth()
  const toast = useToast()
  const [sp, setSp] = useSearchParams()
  const { data, error, loading, reload } = useApi('/api/users')
  const invites = useApi('/api/invites')
  const [form, setForm] = useState(null) // 'new' | user
  const [inviting, setInviting] = useState(sp.get('invite') === '1')
  const [revoking, setRevoking] = useState(null)

  async function revoke(inv) {
    setBusy(true)
    try { await api.del(`/api/invites/${inv.id}`); toast('Invite link cancelled'); setRevoking(null); invites.reload(true) }
    catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }
  const [toggling, setToggling] = useState(null)
  const [busy, setBusy] = useState(false)

  async function toggle(u) {
    setBusy(true)
    try {
      await api.patch(`/api/users/${u.id}`, { is_active: !u.is_active })
      toast(u.is_active ? `${u.name} can no longer log in` : `${u.name} can log in again`)
      setToggling(null); reload(true)
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1>Users</h1>
        <div className="head-actions">
          <button className="btn btn-ghost" onClick={() => setForm('new')}><Icon name="plus" size={18} /> Add user</button>
          <button className="btn btn-primary" onClick={() => setInviting(true)}><Icon name="users" size={18} /> Invite people</button>
        </div>
      </header>
      <BusinessCard />
      <ErrorNote error={error} onRetry={reload} />
      {loading && !data && <Spinner />}
      {data && (
        <table className="table">
          <thead><tr><th>Name</th><th>Role</th><th className="hide-sm">Status</th><th><span className="sr-only">Actions</span></th></tr></thead>
          <tbody>
            {data.map((u) => (
              <tr key={u.id} className={u.is_active ? '' : 'is-archived'}>
                <td><span className="cell-title">{u.name}{u.id === me.id && ' (you)'}</span><span className="cell-sub">{u.email}</span></td>
                <td><span className={`badge ${u.role === 'ADMIN' ? 'badge-admin' : 'badge-muted'}`}>{u.role === 'ADMIN' ? 'Admin' : 'Staff'}</span></td>
                <td className="hide-sm">{u.is_active ? 'Active' : 'Disabled'}</td>
                <td className="row-actions">
                  <button className="btn btn-ghost btn-sm" onClick={() => setForm(u)}>Edit</button>
                  {u.id !== me.id && <button className="btn btn-ghost btn-sm" onClick={() => setToggling(u)}>{u.is_active ? 'Disable' : 'Enable'}</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {invites.data?.length > 0 && (
        <section className="panel" aria-labelledby="inv-h">
          <div className="panel-head"><h2 id="inv-h">Pending invite links</h2></div>
          <table className="table">
            <thead><tr><th>For</th><th>Role</th><th className="hide-sm">Expires</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {invites.data.map((i) => (
                <tr key={i.id}>
                  <td><span className="cell-title">{i.email || 'Anyone with the link'}</span><span className="cell-sub">Created by {i.created_by.name}</span></td>
                  <td><span className={`badge ${i.role === 'ADMIN' ? 'badge-admin' : 'badge-muted'}`}>{i.role === 'ADMIN' ? 'Admin' : 'Staff'}</span></td>
                  <td className="hide-sm">{fmtDate(i.expires_at)}</td>
                  <td className="row-actions"><button className="btn btn-ghost btn-sm" onClick={() => setRevoking(i)}>Cancel link</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {inviting && <InviteModal onClose={() => { setInviting(false); if (sp.get('invite')) setSp({}, { replace: true }) }} onCreated={() => invites.reload(true)} />}
      {revoking && (
        <Confirm title="Cancel this invite link?" confirmLabel="Cancel link" busy={busy}
          onCancel={() => setRevoking(null)} onConfirm={() => revoke(revoking)}>
          <p>Anyone who has the link will no longer be able to join. You can create a new link at any time.</p>
        </Confirm>
      )}
      {form && <UserForm user={form === 'new' ? null : form} isSelf={form?.id === me.id} onClose={() => setForm(null)} onSaved={() => { setForm(null); reload(true) }} />}
      {toggling && (
        <Confirm title={toggling.is_active ? `Disable ${toggling.name}?` : `Enable ${toggling.name}?`}
          confirmLabel={toggling.is_active ? 'Disable account' : 'Enable account'} tone={toggling.is_active ? 'danger' : 'primary'}
          busy={busy} onCancel={() => setToggling(null)} onConfirm={() => toggle(toggling)}>
          <p>{toggling.is_active
            ? 'They will be logged out and cannot log in until re-enabled. Their past stock records are kept.'
            : 'They will be able to log in again with their existing password.'}</p>
        </Confirm>
      )}
    </div>
  )
}

function UserForm({ user, isSelf, onClose, onSaved }) {
  const toast = useToast()
  const [f, setF] = useState({ name: user?.name || '', email: user?.email || '', role: user?.role || 'STAFF', password: '' })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    const errs = {}
    if (!f.name.trim()) errs.name = 'Enter a name.'
    if (!user && !/^\S+@\S+\.\S+$/.test(f.email.trim())) errs.email = 'Enter a valid email address.'
    if ((!user || f.password) && f.password.length < 8) errs.password = TOO_SHORT
    setErrors(errs)
    if (Object.keys(errs).length) return
    setBusy(true)
    try {
      if (user) {
        const body = { name: f.name.trim() }
        if (!isSelf) body.role = f.role
        if (f.password) body.password = f.password
        await api.patch(`/api/users/${user.id}`, body)
        toast('User saved')
      } else {
        await api.post('/api/users', { name: f.name.trim(), email: f.email.trim(), role: f.role, password: f.password })
        toast('User added')
      }
      onSaved()
    } catch (err) {
      setErrors({ ...err.fields, form: err.status === 409 && /email/i.test(err.message) ? null : err.message, ...(err.status === 409 && /email/i.test(err.message) ? { email: err.message } : {}) })
    } finally { setBusy(false) }
  }

  return (
    <Modal title={user ? `Edit ${user.name}` : 'Add user'} onClose={onClose}
      footer={<><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button type="submit" form="user-form" className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : user ? 'Save changes' : 'Add user'}</button></>}>
      <form id="user-form" className="form-grid" onSubmit={submit} noValidate>
        <Field label="Full name" id="u-name" error={errors.name}><input id="u-name" value={f.name} onChange={set('name')} maxLength={120} /></Field>
        <Field label="Email" id="u-email" error={errors.email}><input id="u-email" type="email" value={f.email} onChange={set('email')} disabled={!!user} /></Field>
        <Field label="Role" id="u-role" hint={isSelf ? 'You cannot change your own role.' : f.role === 'ADMIN' ? 'Full access, including suppliers, reports and users.' : 'Can view products and record stock in and out.'}>
          <select id="u-role" value={f.role} onChange={set('role')} disabled={isSelf}>
            <option value="STAFF">Staff</option><option value="ADMIN">Admin</option>
          </select>
        </Field>
        <Field label={user ? 'New password' : 'Password'} id="u-pw" error={errors.password} hint={user ? 'Leave blank to keep the current password.' : 'At least 8 characters.'}>
          <input id="u-pw" type="password" autoComplete="new-password" value={f.password} onChange={set('password')} />
        </Field>
        {errors.form && <p className="form-error span-2" role="alert">{errors.form}</p>}
      </form>
    </Modal>
  )
}


function BusinessCard() {
  const { business, setBusiness } = useAuth()
  const toast = useToast()
  const [name, setName] = useState(business?.name || '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const changed = name.trim() && name.trim() !== business?.name

  async function save(e) {
    e.preventDefault()
    if (name.trim().length < 2) return setError('Enter at least 2 characters.')
    setBusy(true)
    try { setBusiness(await api.patch('/api/business', { name: name.trim() })); setError(''); toast('Business name saved') }
    catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <form className="panel business-card" onSubmit={save}>
      <Field label="Business name" id="biz-name" error={error} hint="Shown to everyone in your business.">
        <input id="biz-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
      </Field>
      <button className="btn btn-ghost" disabled={!changed || busy}>{busy ? 'Saving…' : 'Save name'}</button>
    </form>
  )
}

// Create a one-time link the admin shares (WhatsApp, SMS, email) so someone can join this business.
function InviteModal({ onClose, onCreated }) {
  const { business } = useAuth()
  const toast = useToast()
  const [role, setRole] = useState('STAFF')
  const [email, setEmail] = useState('')
  const [days, setDays] = useState('7')
  const [link, setLink] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function create(e) {
    e.preventDefault()
    if (email && !/^\S+@\S+\.\S+$/.test(email.trim())) return setError('Enter a valid email or leave it blank.')
    setBusy(true)
    try {
      const inv = await api.post('/api/invites', { role, email: email.trim() || null, days_valid: Number(days) })
      setLink(`${window.location.origin}/join/${inv.token}`)
      onCreated()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  async function copy() {
    try { await navigator.clipboard.writeText(link); toast('Link copied') }
    catch { document.getElementById('invite-url')?.select(); toast('Select the link and copy it', 'warn') }
  }

  const share = `You've been invited to ${business?.name} on StockWise: ${link}`
  return (
    <Modal title={link ? 'Share this invite link' : 'Invite people'} onClose={onClose}
      footer={link
        ? <button className="btn btn-primary" onClick={onClose}>Done</button>
        : <><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button type="submit" form="invite-form" className="btn btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Create invite link'}</button></>}>
      {link ? (
        <div className="onboard">
          <p>Send this link to the person joining <strong>{business?.name}</strong> as {role === 'ADMIN' ? 'an admin' : 'staff'}. It works once and expires in {days} day{days === '1' ? '' : 's'}.</p>
          <div className="invite-link">
            <input id="invite-url" readOnly value={link} onFocus={(e) => e.target.select()} aria-label="Invite link" />
            <button type="button" className="btn btn-primary" onClick={copy}>Copy link</button>
          </div>
          <a className="btn btn-ghost" href={`https://wa.me/?text=${encodeURIComponent(share)}`} target="_blank" rel="noreferrer">Share on WhatsApp</a>
          <p className="invite-note">The link is shown only now. If you lose it, cancel it and create a new one.</p>
        </div>
      ) : (
        <form id="invite-form" className="form-grid" onSubmit={create} noValidate>
          <Field label="Role" id="inv-role" hint={role === 'ADMIN' ? 'Full access, including suppliers, reports and users.' : 'Can view products and record stock in and out.'}>
            <select id="inv-role" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="STAFF">Staff</option><option value="ADMIN">Admin</option>
            </select>
          </Field>
          <Field label="Link expires in" id="inv-days">
            <select id="inv-days" value={days} onChange={(e) => setDays(e.target.value)}>
              <option value="1">1 day</option><option value="7">7 days</option><option value="30">30 days</option>
            </select>
          </Field>
          <div className="span-2">
            <Field label="Their email (optional)" id="inv-email" hint="If you fill this in, only this email can use the link.">
              <input id="inv-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
          </div>
          {error && <p className="form-error span-2" role="alert">{error}</p>}
        </form>
      )}
    </Modal>
  )
}
