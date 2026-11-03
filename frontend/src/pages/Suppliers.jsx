import { useState } from 'react'
import { api } from '../lib/api'
import { useApi, useDebounced } from '../lib/hooks'
import { Confirm, Empty, ErrorNote, Field, Icon, Modal, Spinner, useToast } from '../components/ui'

export default function Suppliers() {
  const toast = useToast()
  const [q, setQ] = useState('')
  const dq = useDebounced(q)
  const { data, error, loading, reload } = useApi('/api/suppliers', { q: dq })
  const [editing, setEditing] = useState(null) // supplier | 'new'
  const [removing, setRemoving] = useState(null)
  const [busy, setBusy] = useState(false)

  async function remove(s) {
    setBusy(true)
    try {
      const r = await api.del(`/api/suppliers/${s.id}`)
      toast(r.action === 'deleted' ? 'Supplier deleted' : 'Supplier deactivated')
      setRemoving(null); reload(true)
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  async function activate(s) {
    try { await api.post(`/api/suppliers/${s.id}/activate`); toast('Supplier reactivated'); reload(true) }
    catch (e) { toast(e.message, 'error') }
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1>Suppliers</h1>
        <button className="btn btn-primary" onClick={() => setEditing('new')}><Icon name="plus" size={18} /> Add supplier</button>
      </header>
      <div className="toolbar">
        <div className="search-input grow">
          <Icon name="search" size={18} />
          <input type="search" placeholder="Search suppliers" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search suppliers" />
        </div>
      </div>
      <ErrorNote error={error} onRetry={reload} />
      {loading && !data && <Spinner />}
      {data?.length === 0 && (
        <Empty title={dq ? 'No suppliers match your search' : 'No suppliers yet'}
          action={!dq && <button className="btn btn-primary" onClick={() => setEditing('new')}>Add a supplier</button>}>
          {!dq && 'Add the businesses you buy stock from, then link them to products.'}
        </Empty>
      )}
      {data?.length > 0 && (
        <table className="table">
          <thead><tr><th>Supplier</th><th className="hide-sm">Phone</th><th className="hide-sm">Email</th><th className="num">Products</th><th><span className="sr-only">Actions</span></th></tr></thead>
          <tbody>
            {data.map((s) => (
              <tr key={s.id} className={s.is_active ? '' : 'is-archived'}>
                <td>
                  <span className="cell-title">{s.name}</span>
                  <span className="cell-sub">{[s.contact_person, s.address].filter(Boolean).join(', ') || ' '}{!s.is_active && ' · inactive'}</span>
                </td>
                <td className="hide-sm nowrap">{s.phone ? <a href={`tel:${s.phone.replace(/\s/g, '')}`} className="link">{s.phone}</a> : '—'}</td>
                <td className="hide-sm">{s.email ? <a href={`mailto:${s.email}`} className="link">{s.email}</a> : '—'}</td>
                <td className="num">{s.product_count}</td>
                <td className="row-actions">
                  <button className="btn btn-ghost btn-sm" onClick={() => setEditing(s)}>Edit</button>
                  {s.is_active
                    ? <button className="btn btn-ghost btn-sm" onClick={() => setRemoving(s)}>{s.product_count ? 'Deactivate' : 'Delete'}</button>
                    : <button className="btn btn-ghost btn-sm" onClick={() => activate(s)}>Reactivate</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && <SupplierForm supplier={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload(true) }} />}
      {removing && (
        <Confirm
          title={removing.product_count ? `Deactivate ${removing.name}?` : `Delete ${removing.name}?`}
          confirmLabel={removing.product_count ? 'Deactivate supplier' : 'Delete supplier'}
          busy={busy} onCancel={() => setRemoving(null)} onConfirm={() => remove(removing)}>
          {removing.product_count
            ? <p>This supplier is linked to {removing.product_count} product{removing.product_count > 1 ? 's' : ''}, so it will be deactivated rather than deleted. Existing links stay; it can no longer be linked to new products.</p>
            : <p>This supplier is not linked to any products and will be permanently deleted.</p>}
        </Confirm>
      )}
    </div>
  )
}

function SupplierForm({ supplier, onClose, onSaved }) {
  const toast = useToast()
  const [f, setF] = useState({
    name: supplier?.name || '', contact_person: supplier?.contact_person || '',
    phone: supplier?.phone || '', email: supplier?.email || '', address: supplier?.address || '',
  })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    const errs = {}
    if (!f.name.trim()) errs.name = 'Enter the supplier name.'
    if (f.email && !/^\S+@\S+\.\S+$/.test(f.email.trim())) errs.email = 'Enter a valid email address or leave it blank.'
    if (f.phone && !/^[+0-9 ()-]{6,40}$/.test(f.phone.trim())) errs.phone = 'Use digits, spaces, +, - or brackets.'
    setErrors(errs)
    if (Object.keys(errs).length) return
    setBusy(true)
    const body = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v.trim() || null]))
    body.name = f.name.trim()
    try {
      if (supplier) await api.patch(`/api/suppliers/${supplier.id}`, body)
      else await api.post('/api/suppliers', body)
      toast(supplier ? 'Supplier saved' : 'Supplier added')
      onSaved()
    } catch (err) {
      setErrors({ ...err.fields, form: Object.keys(err.fields || {}).length ? null : err.message })
    } finally { setBusy(false) }
  }

  return (
    <Modal title={supplier ? `Edit ${supplier.name}` : 'Add supplier'} onClose={onClose}
      footer={<><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button type="submit" form="sup-form" className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : supplier ? 'Save changes' : 'Add supplier'}</button></>}>
      <form id="sup-form" className="form-grid" onSubmit={submit} noValidate>
        <Field label="Supplier name" id="s-name" error={errors.name}><input id="s-name" value={f.name} onChange={set('name')} maxLength={200} /></Field>
        <Field label="Contact person" id="s-contact"><input id="s-contact" value={f.contact_person} onChange={set('contact_person')} maxLength={120} /></Field>
        <Field label="Phone" id="s-phone" error={errors.phone}><input id="s-phone" type="tel" value={f.phone} onChange={set('phone')} maxLength={40} /></Field>
        <Field label="Email" id="s-email" error={errors.email}><input id="s-email" type="email" value={f.email} onChange={set('email')} /></Field>
        <div className="span-2"><Field label="Address" id="s-addr"><input id="s-addr" value={f.address} onChange={set('address')} maxLength={255} /></Field></div>
        {errors.form && <p className="form-error span-2" role="alert">{errors.form}</p>}
      </form>
    </Modal>
  )
}
