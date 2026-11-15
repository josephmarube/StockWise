import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
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
  camera: 'M14.5 4h-5L7.5 6.5H4A1.5 1.5 0 0 0 2.5 8v10A1.5 1.5 0 0 0 4 19.5h16a1.5 1.5 0 0 0 1.5-1.5V8A1.5 1.5 0 0 0 20 6.5h-3.5ZM12 16a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z',
  barcode: 'M3 5v14M7 5v14M10 5v14M14 5v14M17 5v14M21 5v14M5 5v14',
  eye: 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
  eyeOff: 'M3 3l18 18M10.6 5.1A10.6 10.6 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4.2M6.6 6.6C3.9 8.4 2 12 2 12s3.6 7 10 7a9.7 9.7 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2',
  check: 'M20 6 9 17l-5-5',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v4l3 2',
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z',
  store: 'M3 9l1.5-5h15L21 9M3 9v11h18V9M3 9h18M9 20v-6h6v6',
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
// Open modals, newest last: only the top one reacts to Escape/Tab.
const modalStack = []

export function Modal({ title, onClose, children, footer, size = 'md', autoFocus = true }) {
  const ref = useRef(null)
  useEffect(() => {
    const prev = document.activeElement
    const el = ref.current
    modalStack.push(el)
    if (autoFocus) el?.querySelector('input, select, textarea, button:not(.modal-x)')?.focus()
    else el?.focus()
    const onKey = (e) => {
      if (modalStack[modalStack.length - 1] !== el) return
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
    return () => {
      document.removeEventListener('keydown', onKey)
      modalStack.splice(modalStack.indexOf(el), 1)
      if (!modalStack.length) document.body.style.overflow = ''
      prev?.focus?.()
    }
  }, [onClose])
  // Rendered at the end of <body> so a dialog opened inside a form is not nested in that form.
  return createPortal(
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal modal-${size}`} role="dialog" aria-modal="true" aria-labelledby="modal-title" ref={ref} tabIndex={-1}>
        <header className="modal-head">
          <h2 id="modal-title">{title}</h2>
          <button className="icon-btn modal-x" onClick={onClose} aria-label="Close"><Icon name="x" /></button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>,
    document.body,
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

const SOURCE_LABEL = { MANUAL: 'Typed', SCANNER: 'Scanner', CAMERA: 'Camera', IMPORT: 'Import', TILL: 'Till', API: 'API' }
export const sourceLabel = (s) => SOURCE_LABEL[s] || s

// How a movement was entered. Manual entries stay quiet; scanned ones get a small marker.
export function SourceTag({ source, always = false }) {
  if (!source || (source === 'MANUAL' && !always)) return null
  return (
    <span className={`source-tag source-${source.toLowerCase()}`}>
      <Icon name={source === 'CAMERA' ? 'camera' : source === 'SCANNER' ? 'barcode' : 'edit'} size={12} />
      {sourceLabel(source)}
    </span>
  )
}

export function TypeTag({ type, override }) {
  return (
    <span className={`type-tag type-${type.toLowerCase()}`}>
      <Icon name={type === 'IN' ? 'arrowIn' : 'arrowOut'} size={14} />
      {type === 'IN' ? 'In' : 'Out'}{override ? ' · override' : ''}
    </span>
  )
}

export function Empty({ title, children, action, art = false }) {
  return (
    <div className="empty">
      {art && <EmptyShelf />}
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


/* ---------- Password input with show/hide (masked by default) ---------- */
export function PasswordInput({ id, value, onChange, autoComplete = 'current-password', invalid, describedBy, ...rest }) {
  const [shown, setShown] = useState(false)
  return (
    <div className="pw-input">
      <input id={id} type={shown ? 'text' : 'password'} value={value} onChange={onChange}
        autoComplete={autoComplete} aria-invalid={invalid || undefined} aria-describedby={describedBy}
        autoCapitalize="none" autoCorrect="off" spellCheck={false} {...rest} />
      <button type="button" className="pw-toggle" onClick={() => setShown((v) => !v)}
        aria-label={shown ? 'Hide password' : 'Show password'} aria-pressed={shown} aria-controls={id}
        title={shown ? 'Hide password' : 'Show password'}>
        <Icon name={shown ? 'eyeOff' : 'eye'} size={19} />
      </button>
    </div>
  )
}

// "New password" + "Confirm password" pair with live checks. Valid when both rules pass.
export function NewPasswordFields({ value, confirm, onChange, onConfirmChange, errors = {}, idPrefix = 'pw', label = 'Password', optional = false }) {
  const longEnough = value.length >= 8
  const matches = value.length > 0 && value === confirm
  const touched = value.length > 0
  return (
    <>
      <Field label={label} id={`${idPrefix}-new`} error={errors.password}>
        <PasswordInput id={`${idPrefix}-new`} value={value} onChange={onChange} autoComplete="new-password" invalid={!!errors.password} />
      </Field>
      <Field label="Confirm password" id={`${idPrefix}-confirm`} error={errors.confirm}>
        <PasswordInput id={`${idPrefix}-confirm`} value={confirm} onChange={onConfirmChange} autoComplete="new-password" invalid={!!errors.confirm} />
      </Field>
      {(touched || !optional) && (
        <ul className="pw-rules span-2" aria-live="polite">
          <li className={longEnough ? 'ok' : ''}><Icon name={longEnough ? 'check' : 'minus'} size={14} /> At least 8 characters</li>
          <li className={matches ? 'ok' : ''}><Icon name={matches ? 'check' : 'minus'} size={14} /> Both passwords match</li>
        </ul>
      )}
    </>
  )
}

export function checkNewPassword(value, confirm, { optional = false } = {}) {
  const e = {}
  if (optional && !value && !confirm) return e
  if (value.length < 8) e.password = 'Use at least 8 characters.'
  if (!confirm) e.confirm = 'Type the password again.'
  else if (value !== confirm) e.confirm = "The passwords don't match."
  return e
}

/* ---------- Loading skeletons ---------- */
export function Skeleton({ w = '100%', h = 14, r = 6, style }) {
  return <span className="skeleton" style={{ width: w, height: h, borderRadius: r, ...style }} aria-hidden="true" />
}

export function SkeletonRows({ rows = 6, cols = 4 }) {
  return (
    <div className="skeleton-table" role="progressbar" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div className="skeleton-row" key={i}>
          <Skeleton w={36} h={36} r={10} />
          <div className="skeleton-cell"><Skeleton w={`${55 + ((i * 17) % 35)}%`} /><Skeleton w="30%" h={11} /></div>
          {Array.from({ length: cols - 2 }, (_, j) => <Skeleton key={j} w={60} />)}
        </div>
      ))}
    </div>
  )
}

/* ---------- Product initials avatar, tinted by category ---------- */
const TINTS = [
  ['#E7EAF6', '#2B3874'], ['#E3F3EA', '#16794A'], ['#FFF1CC', '#8A5F00'], ['#FCE7DA', '#9A3D12'],
  ['#E6F0FA', '#1D5C96'], ['#F2E6F6', '#6B2C80'], ['#E5F4F4', '#1E6B6B'], ['#F1EEE6', '#5E5440'],
]
export function ProductAvatar({ name, categoryId = 0, size = 36 }) {
  // Initials from words that start with a letter: "Yoghurt 250ml" -> "Y", "Bar Soap 800g" -> "BS"
  const words = (name || '?').replace(/[^A-Za-z0-9 ]/g, ' ').split(/\s+/).filter((w) => /^[A-Za-z]/.test(w))
  const initials = (words[0]?.[0] || '?') + (words[1]?.[0] || '')
  const [bg, fg] = TINTS[Math.abs(categoryId) % TINTS.length]
  return (
    <span className="avatar" style={{ width: size, height: size, background: bg, color: fg, fontSize: size * 0.38 }} aria-hidden="true">
      {initials.toUpperCase()}
    </span>
  )
}

/* ---------- Empty-shelf illustration for empty states ---------- */
export function EmptyShelf() {
  return (
    <svg className="empty-art" width="120" height="78" viewBox="0 0 120 78" aria-hidden="true">
      <rect x="8" y="6" width="104" height="66" rx="6" fill="#F6F7FA" stroke="#CDD2E1" />
      <path d="M8 30h104M8 52h104" stroke="#CDD2E1" />
      <rect x="18" y="16" width="10" height="14" rx="2" fill="#E7EAF6" />
      <rect x="31" y="20" width="8" height="10" rx="2" fill="#E7EAF6" />
      <rect x="86" y="40" width="14" height="12" rx="2" fill="#FFF4D6" />
      <circle cx="60" cy="63" r="2" fill="#CDD2E1" /><circle cx="68" cy="63" r="2" fill="#CDD2E1" /><circle cx="52" cy="63" r="2" fill="#CDD2E1" />
    </svg>
  )
}
