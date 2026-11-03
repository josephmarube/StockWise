import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useApi, useDebounced } from '../lib/hooks'
import { fmtDateFull, fmtMoney, fmtNum, todayLocal } from '../lib/format'
import { Empty, ErrorNote, Icon, Pager, Spinner, TypeTag, useToast } from '../components/ui'

const PRESETS = [
  { label: 'Today', days: 0 },
  { label: '7 days', days: 6 },
  { label: '30 days', days: 29 },
  { label: '90 days', days: 89 },
]

export default function Reports() {
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('tab') === 'audit' ? 'audit' : 'stock'
  const [start, setStart] = useState(todayLocal(-29))
  const [end, setEnd] = useState(todayLocal())
  const rangeError = start && end && start > end ? 'Start date must be on or before the end date.' : ''

  return (
    <div className="page">
      <header className="page-head"><h1>Reports</h1></header>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'stock'} className={`tab-btn ${tab === 'stock' ? 'on' : ''}`} onClick={() => setSp({}, { replace: true })}>Stock report</button>
        <button role="tab" aria-selected={tab === 'audit'} className={`tab-btn ${tab === 'audit' ? 'on' : ''}`} onClick={() => setSp({ tab: 'audit' }, { replace: true })}>Audit log</button>
      </div>

      <div className="range">
        <div className="presets">
          {PRESETS.map((p) => {
            const s = todayLocal(-p.days)
            const on = start === s && end === todayLocal()
            return <button key={p.label} className={`chip-btn ${on ? 'on' : ''}`} onClick={() => { setStart(s); setEnd(todayLocal()) }}>{p.label}</button>
          })}
        </div>
        <label>From <input type="date" value={start} max={end} onChange={(e) => setStart(e.target.value)} /></label>
        <label>To <input type="date" value={end} min={start} max={todayLocal()} onChange={(e) => setEnd(e.target.value)} /></label>
      </div>
      {rangeError && <p className="form-error">{rangeError}</p>}

      {!rangeError && (tab === 'stock' ? <StockReport start={start} end={end} /> : <AuditLog start={start} end={end} />)}
    </div>
  )
}

function StockReport({ start, end }) {
  const toast = useToast()
  const [includeArchived, setIncludeArchived] = useState(false)
  const { data, error, loading, reload } = useApi('/api/reports/stock', { start, end, include_archived: includeArchived })
  const [dl, setDl] = useState('')

  async function exportCsv(kind) {
    setDl(kind)
    try {
      if (kind === 'stock') await api.download('/api/reports/stock.csv', { start, end, include_archived: includeArchived }, 'stock.csv')
      else await api.download('/api/reports/movements.csv', { start, end }, 'movements.csv')
      toast('CSV downloaded')
    } catch (e) { toast(e.message, 'error') } finally { setDl('') }
  }

  return (
    <section>
      <div className="report-actions">
        <label className="toggle"><input type="checkbox" checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} /> Include archived products</label>
        <div className="spacer" />
        <button className="btn btn-ghost" onClick={() => exportCsv('stock')} disabled={!!dl}><Icon name="down" size={18} /> {dl === 'stock' ? 'Exporting…' : 'Export stock CSV'}</button>
        <button className="btn btn-ghost" onClick={() => exportCsv('movements')} disabled={!!dl}><Icon name="down" size={18} /> {dl === 'movements' ? 'Exporting…' : 'Export movements CSV'}</button>
      </div>
      <ErrorNote error={error} onRetry={reload} />
      {loading && !data && <Spinner />}
      {data && (
        <>
          <div className="figures figures-sm">
            <div className="figure"><span className="figure-n">{fmtNum(data.totals.qty_in)}</span><span className="figure-l">units in</span></div>
            <div className="figure"><span className="figure-n">{fmtNum(data.totals.qty_out)}</span><span className="figure-l">units out</span></div>
            <div className="figure"><span className="figure-n">{fmtNum(data.totals.units_on_hand)}</span><span className="figure-l">on hand now</span></div>
            <div className="figure"><span className="figure-n">{fmtMoney(data.totals.stock_value)}</span><span className="figure-l">stock value now</span></div>
          </div>
          {data.rows.length === 0 ? <Empty title="No products to report on" /> : (
            <div className="table-scroll">
              <table className="table report-table">
                <thead><tr><th>Product</th><th className="num">In</th><th className="num">Out</th><th className="num">On hand</th><th className="num">Reorder at</th><th className="num">Value</th></tr></thead>
                <tbody>
                  {data.rows.map((r) => (
                    <tr key={r.product_id} className={r.archived ? 'is-archived' : ''}>
                      <td><span className="cell-title">{r.name}</span><span className="cell-sub">{r.sku} · {r.category}{r.archived ? ' · archived' : ''}</span></td>
                      <td className="num qty-in">{r.qty_in ? `+${fmtNum(r.qty_in)}` : '—'}</td>
                      <td className="num qty-out">{r.qty_out ? `−${fmtNum(r.qty_out)}` : '—'}</td>
                      <td className={`num ${r.low_stock && !r.archived ? 'stock-txt-low strong' : ''}`}>{fmtNum(r.current_stock)}</td>
                      <td className="num muted">{fmtNum(r.reorder_threshold)}</td>
                      <td className="num">{fmtMoney(r.stock_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="muted small">Generated {fmtDateFull(data.generated_at)}. “On hand” and “value” are current levels; “in” and “out” cover the selected dates.</p>
        </>
      )}
    </section>
  )
}

const LIMIT = 25

function AuditLog({ start, end }) {
  const toast = useToast()
  const [userId, setUserId] = useState('')
  const [type, setType] = useState('')
  const [q, setQ] = useState('')
  const dq = useDebounced(q)
  const [offset, setOffset] = useState(0)
  const users = useApi('/api/users')
  const { data, error, loading, reload } = useApi('/api/reports/audit', { start, end, user_id: userId, type, q: dq, limit: LIMIT, offset })

  const reset = (fn) => (e) => { fn(e.target.value); setOffset(0) }

  return (
    <section>
      <div className="toolbar">
        <div className="search-input grow"><Icon name="search" size={18} /><input type="search" placeholder="Product name or SKU" value={q} onChange={reset(setQ)} aria-label="Search product" /></div>
        <select value={userId} onChange={reset(setUserId)} aria-label="User">
          <option value="">All users</option>
          {users.data?.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </select>
        <select value={type} onChange={reset(setType)} aria-label="Type">
          <option value="">In and out</option><option value="IN">Stock in</option><option value="OUT">Stock out</option>
        </select>
        <button className="btn btn-ghost" onClick={() => api.download('/api/reports/movements.csv', { start, end, user_id: userId, type }, 'audit.csv').then(() => toast('CSV downloaded')).catch((e) => toast(e.message, 'error'))}>
          <Icon name="down" size={18} /> Export CSV
        </button>
      </div>
      <ErrorNote error={error} onRetry={reload} />
      {loading && !data && <Spinner />}
      {data?.items.length === 0 && <Empty title="No stock actions in this period" />}
      {data?.items.length > 0 && (
        <>
          <div className="table-scroll">
            <table className="table">
              <thead><tr><th>When</th><th>User</th><th>Product</th><th>Type</th><th className="num">Qty</th><th className="num">Stock after</th><th>Note</th></tr></thead>
              <tbody>
                {data.items.map((m) => (
                  <tr key={m.id}>
                    <td className="nowrap">{fmtDateFull(m.created_at)}</td>
                    <td className="nowrap">{m.user.name}<span className="cell-sub">{m.user.role === 'ADMIN' ? 'Admin' : 'Staff'}</span></td>
                    <td><span className="cell-title">{m.product.name}</span><span className="cell-sub">{m.product.sku}</span></td>
                    <td><TypeTag type={m.type} override={m.override} /></td>
                    <td className={`num qty-${m.type.toLowerCase()}`}>{m.type === 'IN' ? '+' : '−'}{fmtNum(m.quantity)}</td>
                    <td className="num">{fmtNum(m.stock_after)}</td>
                    <td className="muted">{m.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}
    </section>
  )
}
