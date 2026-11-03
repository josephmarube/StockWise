import { useState } from 'react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { useAuth } from '../lib/auth'
import { Confirm, ErrorNote, Field, Icon, Modal, Spinner, useToast } from '../components/ui'

export default function Users() {
  const { user: me } = useAuth()
  const toast = useToast()
  const { data, error, loading, reload } = useApi('/api/users')
  const [form, setForm] = useState(null) // 'new' | user
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
        <button className="btn btn-primary" onClick={() => setForm('new')}><Icon name="plus" size={18} /> Add user</button>
      </header>
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
    if ((!user || f.password) && f.password.length < 8) errs.password = 'Use at least 8 characters.'
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
