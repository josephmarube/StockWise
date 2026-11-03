const TZ = import.meta.env.VITE_BUSINESS_TZ || 'Africa/Nairobi'

const money = new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 2 })
const num = new Intl.NumberFormat('en-KE')
const dt = new Intl.DateTimeFormat('en-KE', { timeZone: TZ, day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false })
const dtFull = new Intl.DateTimeFormat('en-KE', { timeZone: TZ, day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
const rel = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

export const fmtMoney = (v) => money.format(Number(v || 0))
export const fmtNum = (v) => num.format(Number(v || 0))
export const fmtDate = (iso) => (iso ? dt.format(new Date(iso)) : '')
export const fmtDateFull = (iso) => (iso ? dtFull.format(new Date(iso)) : '')

export function fmtAgo(iso) {
  const s = (new Date(iso).getTime() - Date.now()) / 1000
  const a = Math.abs(s)
  if (a < 45) return 'just now'
  if (a < 3600) return rel.format(Math.round(s / 60), 'minute')
  if (a < 86400) return rel.format(Math.round(s / 3600), 'hour')
  if (a < 86400 * 7) return rel.format(Math.round(s / 86400), 'day')
  return fmtDate(iso)
}

// Today's date in the business timezone as YYYY-MM-DD.
export function todayLocal(offsetDays = 0) {
  const d = new Date(Date.now() + offsetDays * 86400000)
  return new Intl.DateTimeFormat('en-CA', { timeZone: TZ }).format(d)
}

export function stockState(p) {
  if (p.current_stock <= 0) return 'out'
  if (p.current_stock <= p.reorder_threshold) return 'low'
  return 'ok'
}
