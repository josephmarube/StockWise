import { useEffect, useId, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useDebounced } from '../lib/hooks'
import { fmtNum, stockState } from '../lib/format'
import { Icon } from './ui'

// Searchable product combobox (name or SKU).
export default function ProductPicker({ value, onChange, error, autoFocus }) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [results, setResults] = useState({ q: null, items: [] })
  const [active, setActive] = useState(0)
  const dq = useDebounced(q, 200)
  const id = useId()
  const box = useRef(null)

  useEffect(() => {
    if (!open) return
    let live = true
    api.get('/api/products', { q: dq.trim(), limit: 20 }).then((r) => { if (live) { setResults({ q: dq, items: r.items }); setActive(0) } }).catch(() => {})
    return () => { live = false }
  }, [dq, open])

  useEffect(() => {
    const close = (e) => { if (!box.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  // Never show results for an older query: a fast tap could pick the wrong product.
  const fresh = results.q === q
  const items = fresh ? results.items : []

  function pick(p) { onChange(p); setOpen(false); setQ('') }

  function onKey(e) {
    if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) { setOpen(true); return }
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)) }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
    if (e.key === 'Enter' && items[active]) { e.preventDefault(); pick(items[active]) }
    if (e.key === 'Escape') setOpen(false)
  }

  if (value && !open) {
    return (
      <div className="picked">
        <div>
          <div className="picked-name">{value.name}</div>
          <div className="picked-meta">{value.sku} · {fmtNum(value.current_stock)} in stock</div>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setOpen(true) }}>Change</button>
      </div>
    )
  }

  return (
    <div className="picker" ref={box}>
      <div className="search-input">
        <Icon name="search" size={18} />
        <input
          id="product" role="combobox" aria-expanded={open} aria-controls={`${id}-list`} aria-autocomplete="list"
          aria-invalid={!!error} placeholder="Search by product name or SKU" value={q} autoFocus={autoFocus}
          onChange={(e) => { setQ(e.target.value); setOpen(true) }} onFocus={() => setOpen(true)} onKeyDown={onKey}
          autoComplete="off"
        />
      </div>
      {open && (
        <ul className="picker-list" id={`${id}-list`} role="listbox">
          {!fresh && <li className="picker-empty">Searching…</li>}
          {fresh && items.length === 0 && <li className="picker-empty">No matching products</li>}
          {items.map((p, i) => (
            <li key={p.id} role="option" aria-selected={i === active}
              className={`picker-opt ${i === active ? 'is-active' : ''}`}
              onMouseDown={(e) => { e.preventDefault(); pick(p) }} onMouseEnter={() => setActive(i)}>
              <span className="picker-name">{p.name}<small>{p.sku}</small></span>
              <span className={`picker-stock stock-txt-${stockState(p)}`}>{fmtNum(p.current_stock)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
