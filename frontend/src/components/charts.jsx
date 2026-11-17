import { useEffect, useMemo, useRef, useState } from 'react'
import { fmtMoney, fmtNum } from '../lib/format'

// Series colours (validated: colour-blind safe, 3:1 contrast on white).
export const IN_COLOR = '#16794A'
export const OUT_COLOR = '#4F5FA8'

const dayFmt = new Intl.DateTimeFormat('en-KE', { day: 'numeric', month: 'short', timeZone: 'UTC' })
const wkFmt = new Intl.DateTimeFormat('en-KE', { weekday: 'short', timeZone: 'UTC' })

function niceMax(v) {
  if (v <= 0) return 10
  const p = 10 ** Math.floor(Math.log10(v))
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p
  return 10 * p
}

function useWidth() {
  const ref = useRef(null)
  const [w, setW] = useState(640)
  useEffect(() => {
    if (!ref.current) return undefined
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, Math.floor(e.contentRect.width))))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

// Grouped columns: value (Ksh, at selling price) in vs out per day. One y-axis, hover tooltip, legend, table view.
export function TrendChart({ days }) {
  const [ref, width] = useWidth()
  const [hover, setHover] = useState(null)
  const [asTable, setAsTable] = useState(false)
  const H = 220, M = { t: 12, r: 8, b: 26, l: 44 }
  const iw = width - M.l - M.r, ih = H - M.t - M.b
  const max = useMemo(() => niceMax(Math.max(1, ...days.flatMap((d) => [d.value_in, d.value_out]))), [days])
  const ticks = [0, max / 4, max / 2, (3 * max) / 4, max]
  const band = iw / days.length
  const bar = Math.min(12, Math.max(4, (band - 10) / 2))
  const y = (v) => M.t + ih - (v / max) * ih
  const totalIn = days.reduce((a, d) => a + d.value_in, 0)
  const totalOut = days.reduce((a, d) => a + d.value_out, 0)
  const labelEvery = band < 34 ? 2 : 1

  const col = (x, v, color) => {
    if (!v) return null
    const h = Math.max(2, (v / max) * ih), top = M.t + ih - h, r = Math.min(4, bar / 2, h)
    // rounded data-end, square at the baseline
    return <path d={`M${x},${M.t + ih} V${top + r} Q${x},${top} ${x + r},${top} H${x + bar - r} Q${x + bar},${top} ${x + bar},${top + r} V${M.t + ih} Z`} fill={color} />
  }

  return (
    <div className="chart" ref={ref}>
      <div className="chart-head">
        <ul className="legend" aria-label="Legend">
          <li><i style={{ background: IN_COLOR }} />Stock in <b>{money(totalIn)}</b></li>
          <li><i style={{ background: OUT_COLOR }} />Stock out <b>{money(totalOut)}</b></li>
        </ul>
        <button className="link-btn" onClick={() => setAsTable((v) => !v)}>{asTable ? 'View as chart' : 'View as table'}</button>
      </div>

      {asTable ? (
        <div className="table-scroll">
          <table className="table"><thead><tr><th>Day</th><th className="num">In (Ksh)</th><th className="num">Out (Ksh)</th></tr></thead>
            <tbody>{days.map((d) => (
              <tr key={d.date}><td>{wkFmt.format(new Date(d.date))} {dayFmt.format(new Date(d.date))}</td><td className="num">{money(d.value_in)}</td><td className="num">{money(d.value_out)}</td></tr>
            ))}</tbody>
          </table>
        </div>
      ) : (
        <div className="chart-plot" onMouseLeave={() => setHover(null)}>
          <svg width={width} height={H} role="img" aria-label={`Value of stock in and out per day for the last ${days.length} days, in Kenya shillings`}>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={M.l} x2={width - M.r} y1={y(t)} y2={y(t)} className="grid" />
                <text x={M.l - 8} y={y(t) + 4} className="tick" textAnchor="end">{fmtCompact(t)}</text>
              </g>
            ))}
            {days.map((d, i) => {
              const cx = M.l + band * i + band / 2
              return (
                <g key={d.date}>
                  {hover === i && <rect x={cx - band / 2 + 2} y={M.t} width={band - 4} height={ih} rx="6" className="hover-band" />}
                  {col(cx - bar - 1, d.value_in, IN_COLOR)}
                  {col(cx + 1, d.value_out, OUT_COLOR)}
                  {i % labelEvery === (days.length - 1) % labelEvery && (
                    <text x={cx} y={H - 8} className="tick" textAnchor="middle">{dayFmt.format(new Date(d.date)).split(' ')[0]}</text>
                  )}
                  <rect x={cx - band / 2} y={M.t} width={band} height={ih + M.b} fill="transparent"
                    onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} tabIndex={-1} />
                </g>
              )
            })}
          </svg>
          {hover !== null && (
            <div className="tooltip" style={{ left: Math.min(Math.max(M.l + band * hover + band / 2, 80), width - 80) }}>
              <div className="tooltip-title">{wkFmt.format(new Date(days[hover].date))} {dayFmt.format(new Date(days[hover].date))}</div>
              <div><i style={{ background: IN_COLOR }} />In <b>{money(days[hover].value_in)}</b></div>
              <div><i style={{ background: OUT_COLOR }} />Out <b>{money(days[hover].value_out)}</b></div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Horizontal bars, one series: magnitude only, value at the bar's end.
export function BarList({ items, value, label, sub, format = fmtNum, color = OUT_COLOR, onSelect }) {
  const max = Math.max(1, ...items.map(value))
  return (
    <ul className="barlist">
      {items.map((it, i) => (
        <li key={i} className={onSelect ? 'clickable' : ''} onClick={onSelect ? () => onSelect(it) : undefined}>
          <div className="barlist-top">
            <span className="barlist-label">{label(it)}{sub && <small>{sub(it)}</small>}</span>
            <b>{format(value(it))}</b>
          </div>
          <span className="barlist-track"><span style={{ width: `${(value(it) / max) * 100}%`, background: color }} /></span>
        </li>
      ))}
    </ul>
  )
}

export const money = (v) => fmtMoney(v).replace(/\.00$/, '')
// Axis labels: 1,500 -> "1.5K", 2,000,000 -> "2M"
const compact = new Intl.NumberFormat('en-KE', { notation: 'compact', maximumFractionDigits: 1 })
const fmtCompact = (v) => compact.format(v)
