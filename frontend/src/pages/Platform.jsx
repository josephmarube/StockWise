import { useState } from 'react'
import { api } from '../lib/api'
import { useApi, useDebounced } from '../lib/hooks'
import { fmtAgo, fmtDate, fmtNum } from '../lib/format'
import ActivityList from '../components/ActivityList'
import { Empty, ErrorNote, Field, Icon, Modal, Pager, SkeletonRows, useToast } from '../components/ui'

// System Admin: metadata about every business (names, dates, counts), never their products or stock.
export default function Platform({ tab = 'businesses' }) {
  return tab === 'activity' ? <PlatformActivity /> : <Businesses />
}

function Businesses() {
  const [q, setQ] = useState('')
  const dq = useDebounced(q, 250)
  const summary = useApi('/api/platform/summary')
  const { data, error, loading, reload } = useApi('/api/platform/businesses', { q: dq.trim() || undefined })
  const [editing, setEditing] = useState(null) // { biz, mode: 'rename' | 'status' }

  const done = () => { setEditing(null); reload(true); summary.reload(true) }
  const s = summary.data

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Businesses</h1>
          <p className="muted">You see names, dates, counts and last login only. Every change you make here is shown in that business's activity log.</p>
        </div>
      </header>

      <div className="figures">
        {[
          ['businesses', s?.businesses],
          ['active', s?.active_businesses],
          ['shop accounts', s?.users],
          ['new in 30 days', s?.new_businesses_30d],
        ].map(([label, v]) => (
          <div className="figure" key={label}>
            <span className="figure-n">{v === undefined ? '…' : fmtNum(v)}</span>
            <span className="figure-l">{label}</span>
          </div>
        ))}
      </div>

      <div className="search-input toolbar-search">
        <Icon name="search" size={18} />
        <input type="search" placeholder="Search businesses" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search businesses" />
      </div>

      <ErrorNote error={error} onRetry={reload} />
      {loading && !data && <SkeletonRows rows={5} cols={5} />}
      {data && data.length === 0 && <Empty title="No businesses found" />}
      {data && data.length > 0 && (
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Business</th><th className="num">Managers</th><th className="num">Staff</th>
                <th className="num">Products</th>
                <th className="hide-sm">Last active</th><th>Status</th><th><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {data.map((b) => (
                <tr key={b.id} className={b.is_active ? '' : 'is-archived'}>
                  <td><span className="cell-title">{b.name}</span><span className="cell-sub">Joined {fmtDate(b.created_at)}</span></td>
                  <td className="num">{b.managers}</td>
                  <td className="num">{b.staff}</td>
                  <td className="num">{fmtNum(b.products)}</td>
                  <td className="hide-sm" title="Most recent login by anyone in the business">{b.last_active ? fmtAgo(b.last_active) : 'Never'}</td>
                  <td><span className={`badge ${b.is_active ? 'badge-ok' : 'badge-muted'}`}>{b.is_active ? 'Active' : 'Deactivated'}</span></td>
                  <td className="row-actions">
                    <button className="btn btn-ghost btn-sm" onClick={() => setEditing({ biz: b, mode: 'rename' })}>Rename</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setEditing({ biz: b, mode: 'status' })}>{b.is_active ? 'Deactivate' : 'Reactivate'}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && <ChangeBusiness {...editing} onClose={() => setEditing(null)} onDone={done} />}
    </div>
  )
}

function ChangeBusiness({ biz, mode, onClose, onDone }) {
  const toast = useToast()
  const [name, setName] = useState(biz.name)
  const [reason, setReason] = useState('')
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const rename = mode === 'rename'
  const deactivating = !rename && biz.is_active

  async function save(e) {
    e.preventDefault()
    const errs = {}
    if (rename && name.trim().length < 2) errs.name = 'Enter at least 2 characters.'
    if (rename && name.trim() === biz.name) errs.name = 'Enter a different name.'
    if (deactivating && !reason.trim()) errs.reason = 'Give a reason. The business will see it.'
    setErrors(errs)
    if (Object.keys(errs).length) return
    setBusy(true)
    try {
      const body = rename ? { name: name.trim() } : { is_active: !biz.is_active }
      if (reason.trim()) body.reason = reason.trim()
      await api.patch(`/api/platform/businesses/${biz.id}`, body)
      toast(rename ? `Renamed to ${name.trim()}` : deactivating ? `${biz.name} deactivated` : `${biz.name} reactivated`)
      onDone()
    } catch (err) { setErrors({ name: err.message }) } finally { setBusy(false) }
  }

  const title = rename ? `Rename ${biz.name}` : deactivating ? `Deactivate ${biz.name}?` : `Reactivate ${biz.name}?`
  return (
    <Modal title={title} onClose={onClose} size="sm"
      footer={<>
        <button className="btn btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
        <button className={`btn ${deactivating ? 'btn-danger' : 'btn-primary'}`} form="biz-form" disabled={busy}>
          {busy ? 'Saving…' : rename ? 'Rename' : deactivating ? 'Deactivate' : 'Reactivate'}
        </button>
      </>}>
      <form id="biz-form" onSubmit={save} className="stack-form" noValidate>
        {rename && (
          <Field label="New name" id="biz-new-name" error={errors.name}>
            <input id="biz-new-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
          </Field>
        )}
        {deactivating && <p className="confirm-text">Its {biz.managers + biz.staff} people will be logged out and unable to log in until you reactivate it. Nothing is deleted.</p>}
        <Field label={deactivating ? 'Reason' : 'Reason (optional)'} id="biz-reason" error={errors.reason}
          hint="Shown to the business's managers in their activity log.">
          <input id="biz-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} />
        </Field>
      </form>
    </Modal>
  )
}

function PlatformActivity() {
  const [offset, setOffset] = useState(0)
  const { data, error, loading, reload } = useApi('/api/platform/activity', { limit: 30, offset })
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Activity</h1>
          <p className="muted">New businesses and every change made by System Admins.</p>
        </div>
      </header>
      <ErrorNote error={error} onRetry={reload} />
      {loading && !data && <SkeletonRows rows={5} cols={2} />}
      {data && data.items.length === 0 && <Empty title="No activity yet" />}
      {data && data.items.length > 0 && <ActivityList items={data.items} showBusiness />}
      {data && <Pager total={data.total} limit={30} offset={offset} onChange={setOffset} />}
    </div>
  )
}
