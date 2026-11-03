import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { useAuth } from '../lib/auth'
import { fmtDateFull, fmtMoney, fmtNum } from '../lib/format'
import ProductForm from '../components/ProductForm'
import { Confirm, Empty, ErrorNote, Icon, Modal, Pager, Spinner, StockBadge, StockBar, TypeTag, useToast } from '../components/ui'

const LIMIT = 20

export default function ProductDetail() {
  const { id } = useParams()
  const { isAdmin } = useAuth()
  const nav = useNavigate()
  const toast = useToast()
  const [offset, setOffset] = useState(0)
  const prod = useApi(`/api/products/${id}`)
  const hist = useApi('/api/stock/movements', { product_id: id, limit: LIMIT, offset })
  const [editing, setEditing] = useState(false)
  const [linking, setLinking] = useState(false)
  const [confirm, setConfirm] = useState(null) // 'archive' | 'delete'
  const [busy, setBusy] = useState(false)

  if (prod.error) return <div className="page"><ErrorNote error={prod.error} /><Link to="/products" className="link">Back to products</Link></div>
  if (!prod.data) return <div className="page"><Spinner /></div>
  const p = prod.data
  const hasHistory = (hist.data?.total || 0) > 0

  async function act(kind) {
    setBusy(true)
    try {
      if (kind === 'archive') { prod.setData(await api.post(`/api/products/${p.id}/archive`)); toast('Product archived') }
      if (kind === 'restore') { prod.setData(await api.post(`/api/products/${p.id}/restore`)); toast('Product restored') }
      if (kind === 'delete') { await api.del(`/api/products/${p.id}`); toast('Product deleted'); nav('/products') }
      setConfirm(null)
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <Link to="/products" className="back"><Icon name="back" size={18} /> Products</Link>
      <header className="page-head">
        <div>
          <h1>{p.name}</h1>
          <p className="lede">{p.sku} · {p.category.name}{p.archived && <span className="badge badge-muted">Archived</span>}</p>
        </div>
        <div className="head-actions">
          {!p.archived && <>
            <Link to={`/record?product=${p.id}&type=OUT`} className="btn btn-out"><Icon name="arrowOut" size={18} /> Stock out</Link>
            <Link to={`/record?product=${p.id}&type=IN`} className="btn btn-in"><Icon name="arrowIn" size={18} /> Stock in</Link>
          </>}
        </div>
      </header>

      <section className="detail-grid">
        <div className="panel stock-panel">
          <div className="stock-big">
            <span className="stock-big-n">{fmtNum(p.current_stock)}</span>
            <span className="stock-big-l">in stock <StockBadge product={p} /></span>
          </div>
          <StockBar product={p} />
          <dl className="facts">
            <div><dt>Reorder level</dt><dd>{fmtNum(p.reorder_threshold)}</dd></div>
            <div><dt>Unit price</dt><dd>{fmtMoney(p.unit_price)}</dd></div>
            <div><dt>Stock value</dt><dd>{fmtMoney(p.current_stock * Number(p.unit_price))}</dd></div>
          </dl>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>Suppliers</h2>
            {isAdmin && <button className="btn btn-ghost btn-sm" onClick={() => setLinking(true)}>Change</button>}
          </div>
          {p.suppliers.length === 0
            ? <p className="muted">No suppliers linked.</p>
            : <ul className="chips">{p.suppliers.map((s) => <li key={s.id} className={`chip ${s.is_active ? '' : 'chip-muted'}`}>{s.name}{!s.is_active && ' (inactive)'}</li>)}</ul>}
          {isAdmin && (
            <div className="admin-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}><Icon name="edit" size={16} /> Edit details</button>
              {p.archived
                ? <button className="btn btn-ghost btn-sm" onClick={() => act('restore')} disabled={busy}>Restore</button>
                : <button className="btn btn-ghost btn-sm" onClick={() => setConfirm('archive')}><Icon name="archive" size={16} /> Archive</button>}
              {!hasHistory && hist.data && <button className="btn btn-ghost btn-sm danger-text" onClick={() => setConfirm('delete')}>Delete</button>}
            </div>
          )}
        </div>
      </section>

      <section className="panel" aria-labelledby="hist-h">
        <div className="panel-head"><h2 id="hist-h">Stock history</h2></div>
        <ErrorNote error={hist.error} onRetry={hist.reload} />
        {hist.data && hist.data.items.length === 0 && <Empty title="No stock recorded for this product yet" />}
        {hist.data && hist.data.items.length > 0 && (
          <>
            <table className="table">
              <thead><tr><th>When</th><th>Type</th><th className="num">Qty</th><th className="num">Stock after</th><th className="hide-sm">By</th><th className="hide-sm">Note</th></tr></thead>
              <tbody>
                {hist.data.items.map((m) => (
                  <tr key={m.id}>
                    <td className="nowrap">{fmtDateFull(m.created_at)}</td>
                    <td><TypeTag type={m.type} override={m.override} /></td>
                    <td className={`num qty-${m.type.toLowerCase()}`}>{m.type === 'IN' ? '+' : '−'}{fmtNum(m.quantity)}</td>
                    <td className="num">{fmtNum(m.stock_after)}</td>
                    <td className="hide-sm">{m.user.name}</td>
                    <td className="hide-sm muted">{m.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager total={hist.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </section>

      {editing && <ProductForm product={p} onClose={() => setEditing(false)} onSaved={(np) => { prod.setData(np); setEditing(false) }} />}
      {linking && <SupplierLinker product={p} onClose={() => setLinking(false)} onSaved={(np) => { prod.setData(np); setLinking(false) }} />}
      {confirm === 'archive' && (
        <Confirm title={`Archive ${p.name}?`} confirmLabel="Archive product" busy={busy} onCancel={() => setConfirm(null)} onConfirm={() => act('archive')}>
          <p>It will be hidden from staff and from the catalogue. Its stock history is kept, and you can restore it at any time.</p>
        </Confirm>
      )}
      {confirm === 'delete' && (
        <Confirm title={`Delete ${p.name}?`} confirmLabel="Delete permanently" busy={busy} onCancel={() => setConfirm(null)} onConfirm={() => act('delete')}>
          <p>This product has no stock history, so it can be deleted. This cannot be undone.</p>
        </Confirm>
      )}
    </div>
  )
}

function SupplierLinker({ product, onClose, onSaved }) {
  const all = useApi('/api/suppliers')
  const toast = useToast()
  const [sel, setSel] = useState(product.suppliers.map((s) => s.id))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const options = (all.data || []).filter((s) => s.is_active || sel.includes(s.id))

  async function save() {
    setBusy(true)
    try {
      onSaved(await api.put(`/api/products/${product.id}/suppliers`, { supplier_ids: sel }))
      toast('Suppliers updated')
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <Modal title="Suppliers for this product" onClose={onClose}
      footer={<><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save suppliers'}</button></>}>
      {all.loading && <Spinner />}
      {all.data && options.length === 0 && <p className="muted">No active suppliers. Add one on the Suppliers page first.</p>}
      <div className="checks">
        {options.map((s) => (
          <label key={s.id} className="check">
            <input type="checkbox" checked={sel.includes(s.id)} onChange={() => setSel((x) => x.includes(s.id) ? x.filter((i) => i !== s.id) : [...x, s.id])} />
            {s.name}{!s.is_active && <span className="muted"> (inactive)</span>}
          </label>
        ))}
      </div>
      {error && <p className="form-error">{error}</p>}
    </Modal>
  )
}
