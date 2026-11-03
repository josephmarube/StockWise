import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { stockState, fmtNum } from '../lib/format'

/* ---------- Icons (inline, stroke-based) ---------- */
const paths = {
  home: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
  box: 'M21 8 12 3 3 8m18 0v8l-9 5m9-13-9 5m0 8-9-5V8m9 13v-8M3 8l9 5',
  swap: 'M7 4v16m0 0-3-3m3 3 3-3M17 20V4m0 0-3 3m3-3 3 3',
  truck: 'M3 6h11v10H3zM14 9h4l3 3v4h-7M7.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm10 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z',
  chart: 'M4 20V10m6 10V4m6 16v-7m4 7H2',
  users: 'M16 19v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1m20 0v-1a4 4 0 0 0-3-3.87M15 3.13a4 4 0 0 1 0 7.75M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  search: 'm21 21-4.3-4.3M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z',
  x: 'M18 6 6 18M6 6l12 12',
  logout: 'M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3',
  down: 'M12 3v14m0 0 6-6m-6 6-6-6M4 21h16',
  arrowIn: 'M12 4v12m0 0-5-5m5 5 5-5M5 20h14',
  arrowOut: 'M12 20V8m0 0-5 5m5-5 5 5M5 4h14',
  alert: 'M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  back: 'M15 18l-6-6 6-6',
  edit: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z',
  archive: 'M21 8v13H3V8M1 3h22v5H1zM10 12h4',
  more: 'M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2Zm7 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2ZM5 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z',
}
export function Icon({ name, size = 20, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
      <path d={paths[name]} />
    </svg>
  )
}

/* ---------- Toasts ---------- */
const ToastCtx = createContext(() => {})
export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((message, tone = 'ok') => {
    const id = Math.random().toString(36).slice(2)
    setItems((xs) => [...xs, { id, message, tone }])
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 4200)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`toast toast-${t.tone}`}>{t.message}</div>)}
      </div>
    </ToastCtx.Provider>
  )
}
export const useToast = () => useContext(ToastCtx)

/* ---------- Modal ---------- */
export function Modal({ title, onClose, children, footer, size = 'md' }) {
  const ref = useRef(null)
  useEffect(() => {
    const prev = document.activeElement
    const el = ref.current
    const first = el?.querySelector('input, select, textarea, button:not(.modal-x)')
    first?.focus()
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'Tab' && el) {
        const f = el.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
        if (!f.length) return
        const a = f[0], z = f[f.length - 1]
        if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus() }
        else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus() }
      }
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = ''; prev?.focus?.() }
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal modal-${size}`} role="dialog" aria-modal="true" aria-labelledby="modal-title" ref={ref}>
        <header className="modal-head">
          <h2 id="modal-title">{title}</h2>
          <button className="icon-btn modal-x" onClick={onClose} aria-label="Close"><Icon name="x" /></button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>
  )
}

/* ---------- Confirm (SRS 3.1 / 5.2: destructive actions need confirmation) ---------- */
export function Confirm({ title, children, confirmLabel, tone = 'danger', busy, onConfirm, onCancel }) {
  return (
    <Modal title={title} onClose={onCancel} size="sm"
      footer={<>
        <button className="btn btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
        <button className={`btn btn-${tone}`} onClick={onConfirm} disabled={busy}>{busy ? 'Working…' : confirmLabel}</button>
      </>}>
      <div className="confirm-text">{children}</div>
    </Modal>
  )
}

/* ---------- Form field ---------- */
export function Field({ label, error, hint, children, id }) {
  return (
    <div className={`field ${error ? 'has-error' : ''}`}>
      <label htmlFor={id}>{label}</label>
      {children}
      {error ? <p className="field-error" id={`${id}-err`}>{error}</p> : hint ? <p className="field-hint">{hint}</p> : null}
    </div>
  )
}

/* ---------- Stock bar: current stock vs reorder line ---------- */
export function StockBar({ product, compact = false }) {
  const { current_stock: s, reorder_threshold: t } = product
  const state = stockState(product)
  const scale = Math.max(t * 3, s, 1)
  const fill = Math.max(0, Math.min(100, (s / scale) * 100))
  const mark = Math.min(100, (t / scale) * 100)
  return (
    <div className={`stockbar stock-${state} ${compact ? 'compact' : ''}`}
      title={`${fmtNum(s)} in stock, reorder at ${fmtNum(t)}`}>
      <div className="stockbar-track">
        <div className="stockbar-fill" style={{ width: `${fill}%` }} />
        {t > 0 && <div className="stockbar-mark" style={{ left: `${mark}%` }} />}
      </div>
    </div>
  )
}

export function StockBadge({ product }) {
  const state = stockState(product)
  if (state === 'ok') return null
  return <span className={`badge badge-${state}`}>{state === 'out' ? 'Out of stock' : 'Low stock'}</span>
}

export function TypeTag({ type, override }) {
  return (
    <span className={`type-tag type-${type.toLowerCase()}`}>
      <Icon name={type === 'IN' ? 'arrowIn' : 'arrowOut'} size={14} />
      {type === 'IN' ? 'In' : 'Out'}{override ? ' · override' : ''}
    </span>
  )
}

export function Empty({ title, children, action }) {
  return (
    <div className="empty">
      <p className="empty-title">{title}</p>
      {children && <p className="empty-text">{children}</p>}
      {action}
    </div>
  )
}

export function ErrorNote({ error, onRetry }) {
  if (!error) return null
  return (
    <div className="error-note" role="alert">
      <Icon name="alert" size={18} />
      <span>{error.message}</span>
      {onRetry && <button className="btn btn-ghost btn-sm" onClick={() => onRetry()}>Try again</button>}
    </div>
  )
}

export function Pager({ total, limit, offset, onChange }) {
  if (total <= limit) return null
  const page = Math.floor(offset / limit) + 1
  const pages = Math.ceil(total / limit)
  return (
    <nav className="pager" aria-label="Pagination">
      <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => onChange(offset - limit)}>Previous</button>
      <span>Page {page} of {pages}</span>
      <button className="btn btn-ghost btn-sm" disabled={page >= pages} onClick={() => onChange(offset + limit)}>Next</button>
    </nav>
  )
}

export function Spinner() {
  return <div className="spinner" role="progressbar" aria-label="Loading" />
}
