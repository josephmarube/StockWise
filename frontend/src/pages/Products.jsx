import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useApi, useDebounced } from '../lib/hooks'
import { useAuth } from '../lib/auth'
import { fmtMoney, fmtNum } from '../lib/format'
import ProductForm from '../components/ProductForm'
import { Empty, ErrorNote, Icon, Pager, Spinner, StockBadge, StockBar } from '../components/ui'

const LIMIT = 25

export default function Products() {
  const { isAdmin } = useAuth()
  const nav = useNavigate()
  const [sp, setSp] = useSearchParams()
  const [q, setQ] = useState(sp.get('q') || '')
  const dq = useDebounced(q)
  const category = sp.get('cat') || ''
  const low = sp.get('low') === '1'
  const view = sp.get('view') || 'active' // active | archived
  const sort = sp.get('sort') || 'name'
  const offset = Number(sp.get('o') || 0)
  const [adding, setAdding] = useState(sp.get('new') === '1')
  const prefillBarcode = sp.get('barcode') || ''

  const cats = useApi('/api/categories')
  const { data, error, loading, reload } = useApi('/api/products', {
    q: dq, category_id: category, low_stock: low, archived_only: view === 'archived',
    sort, order: sort === 'stock' || sort === 'updated' ? (sort === 'updated' ? 'desc' : 'asc') : 'asc',
    limit: LIMIT, offset,
  })

  const setParam = (k, v) => {
    const n = new URLSearchParams(sp)
    if (v) n.set(k, v); else n.delete(k)
    if (k !== 'o') n.delete('o')
    setSp(n, { replace: true })
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1>Products</h1>
        {isAdmin && <button className="btn btn-primary" onClick={() => setAdding(true)}><Icon name="plus" size={18} /> Add product</button>}
      </header>

      <div className="toolbar">
        <div className="search-input grow">
          <Icon name="search" size={18} />
          <input type="search" placeholder="Search name, SKU or barcode" value={q} aria-label="Search products"
            onChange={(e) => { setQ(e.target.value); setParam('o', '') }} />
        </div>
        <select value={category} onChange={(e) => setParam('cat', e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select value={sort} onChange={(e) => setParam('sort', e.target.value === 'name' ? '' : e.target.value)} aria-label="Sort by">
          <option value="name">Sort: name</option>
          <option value="stock">Sort: lowest stock</option>
          <option value="sku">Sort: SKU</option>
          <option value="updated">Sort: recently changed</option>
        </select>
        <label className="toggle">
          <input type="checkbox" checked={low} onChange={(e) => setParam('low', e.target.checked ? '1' : '')} />
          Low stock only
        </label>
        {isAdmin && (
          <label className="toggle">
            <input type="checkbox" checked={view === 'archived'} onChange={(e) => setParam('view', e.target.checked ? 'archived' : '')} />
            Archived
          </label>
        )}
      </div>

      <ErrorNote error={error} onRetry={reload} />
      {loading && !data && <Spinner />}

      {data && data.items.length === 0 && (
        <Empty title={dq || category || low ? 'No products match these filters' : view === 'archived' ? 'No archived products' : 'No products yet'}
          action={isAdmin && !dq && !category && !low && view !== 'archived' && <button className="btn btn-primary" onClick={() => setAdding(true)}>Add your first product</button>}>
          {dq || category || low ? 'Try a different search or clear the filters.' : null}
        </Empty>
      )}

      {data && data.items.length > 0 && (
        <>
          <table className="table products-table">
            <thead>
              <tr>
                <th>Product</th>
                <th className="hide-sm">Category</th>
                <th className="num hide-sm">Price</th>
                <th className="num">In stock</th>
                <th className="bar-col hide-sm"><span className="sr-only">Level</span></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((p) => (
                <tr key={p.id} className={`row-link ${p.archived ? 'is-archived' : ''}`} onClick={() => nav(`/products/${p.id}`)}>
                  <td>
                    <Link to={`/products/${p.id}`} className="cell-title" onClick={(e) => e.stopPropagation()}>{p.name}</Link>
                    <span className="cell-sub">{p.sku}{p.archived ? ' · archived' : ''}</span>
                  </td>
                  <td className="hide-sm">{p.category.name}</td>
                  <td className="num hide-sm">{fmtMoney(p.unit_price)}</td>
                  <td className="num">
                    <span className="stock-num">{fmtNum(p.current_stock)}</span>
                    <StockBadge product={p} />
                  </td>
                  <td className="bar-col hide-sm"><StockBar product={p} compact /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager total={data.total} limit={LIMIT} offset={offset} onChange={(o) => setParam('o', o ? String(o) : '')} />
        </>
      )}

      {adding && isAdmin && (
        <ProductForm initialBarcode={prefillBarcode}
          onClose={() => {
            setAdding(false)
            const n = new URLSearchParams(sp); n.delete('new'); n.delete('barcode')
            setSp(n, { replace: true })
          }}
          onSaved={(p) => { setAdding(false); nav(`/products/${p.id}`) }} />
      )}
    </div>
  )
}
