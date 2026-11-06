import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useDebounced } from '../lib/hooks'
import { fmtNum, stockState } from '../lib/format'
import BarcodeScanner from './BarcodeScanner'
import { Icon } from './ui'

// USB/Bluetooth scanners "type" the barcode very fast and press Enter.
// Keys arriving faster than this (on average) are treated as a scanner.
const SCANNER_MS_PER_KEY = 35

// Searchable product picker: type a name/SKU, scan with a USB scanner, or scan with the camera (FR2.5).
// onChange(product, source) where source is MANUAL, SCANNER or CAMERA.
export default function ProductPicker({ value, onChange, error, autoFocus, inputRef, isAdmin }) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [results, setResults] = useState({ q: null, items: [] })
  const [active, setActive] = useState(0)
  const [camera, setCamera] = useState(false)
  const [notFound, setNotFound] = useState('')
  const [looking, setLooking] = useState(false)
  const dq = useDebounced(q, 200)
  const id = useId()
  const box = useRef(null)
  const keyTimes = useRef([])
  const ownRef = useRef(null)
  const searchRef = inputRef || ownRef

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

  function pick(p, source = 'MANUAL') {
    onChange(p, source)
    setOpen(false); setQ(''); setNotFound(''); keyTimes.current = []
  }

  async function lookup(code) {
    try {
      return await api.get(`/api/products/by-barcode/${encodeURIComponent(code)}`)
    } catch (e) {
      if (e.status === 404) return null
      throw e
    }
  }

  function typedByScanner() {
    const t = keyTimes.current
    if (t.length < 4) return false
    return (t[t.length - 1] - t[0]) / (t.length - 1) < SCANNER_MS_PER_KEY
  }

  async function onEnter() {
    const term = q.trim()
    if (!term) return
    const scanned = typedByScanner()
    setLooking(true)
    try {
      const p = /\s/.test(term) ? null : await lookup(term)
      if (p) return pick(p, scanned ? 'SCANNER' : 'MANUAL')
      if (scanned || /^\d{6,}$/.test(term)) { setNotFound(term); setOpen(false); return }
      if (items[active]) pick(items[active])
    } catch {
      /* network problems surface through the list */
    } finally {
      setLooking(false)
      keyTimes.current = []
    }
  }

  async function onCameraCode(code, source) {
    setCamera(false)
    const p = await lookup(code).catch(() => null)
    if (p) pick(p, source)
    else { setNotFound(code); setOpen(false) }
  }

  function onKey(e) {
    if (e.key.length === 1) keyTimes.current.push(performance.now())
    if (e.key === 'Enter') { e.preventDefault(); onEnter(); return }
    if (!open && e.key === 'ArrowDown') { setOpen(true); return }
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)) }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
    if (e.key === 'Escape') setOpen(false)
  }

  if (value && !open && !notFound) {
    return (
      <div className="picked">
        <div>
          <div className="picked-name">{value.name}</div>
          <div className="picked-meta">{value.sku} · {fmtNum(value.current_stock)} in stock</div>
        </div>
        <button type="button" className="btn btn-ghost btn-sm"
          onClick={() => { setOpen(true); setTimeout(() => searchRef.current?.focus(), 0) }}>Change</button>
      </div>
    )
  }

  return (
    <div className="picker" ref={box}>
      <div className="picker-row">
        <div className="search-input grow">
          <Icon name="search" size={18} />
          <input
            id="product" ref={searchRef} role="combobox" aria-expanded={open} aria-controls={`${id}-list`}
            aria-autocomplete="list" aria-invalid={!!error} placeholder="Name, SKU or scan a barcode"
            value={q} autoFocus={autoFocus} autoComplete="off"
            onChange={(e) => { setQ(e.target.value); setOpen(true); setNotFound(''); if (!e.target.value) keyTimes.current = [] }}
            onFocus={() => setOpen(true)} onKeyDown={onKey}
          />
        </div>
        <button type="button" className="btn btn-ghost scan-btn" onClick={() => setCamera(true)} aria-label="Scan barcode with camera">
          <Icon name="camera" size={20} /><span>Scan</span>
        </button>
      </div>

      {notFound && (
        <div className="not-found" role="alert">
          <span>No product has barcode <strong>{notFound}</strong>.</span>
          {isAdmin
            ? <Link className="link" to={`/products?new=1&barcode=${encodeURIComponent(notFound)}`}>Add it as a new product</Link>
            : <span className="muted">Ask an admin to add it.</span>}
        </div>
      )}

      {open && !notFound && (
        <ul className="picker-list" id={`${id}-list`} role="listbox">
          {(looking || !fresh) && <li className="picker-empty">Searching…</li>}
          {fresh && !looking && items.length === 0 && <li className="picker-empty">No matching products</li>}
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

      {camera && <BarcodeScanner onDetected={onCameraCode} onClose={() => setCamera(false)} />}
    </div>
  )
}
