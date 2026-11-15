import { fmtAgo, fmtDateFull } from '../lib/format'
import { Icon } from './ui'

const FIELD_LABELS = {
  sku: 'SKU', name: 'Name', category: 'Category', unit_price: 'Price', reorder_threshold: 'Reorder level',
  barcodes: 'Barcodes', suppliers: 'Suppliers', contact_person: 'Contact person', phone: 'Phone',
  email: 'Email', address: 'Address', role: 'Role', is_active: 'Status', password: 'Password',
}
const ROLE_LABELS = { SYSTEM_ADMIN: 'StockWise', MANAGER: 'Manager', STAFF: 'Staff' }
const ICONS = { product: 'box', supplier: 'truck', user: 'users', invite: 'users', category: 'box', business: 'store' }

function show(field, v) {
  if (v === null || v === undefined || v === '') return '—'
  if (Array.isArray(v)) return v.length ? v.join(', ') : 'none'
  if (field === 'is_active') return v ? 'Active' : 'Disabled'
  if (field === 'role') return ROLE_LABELS[v] || v
  if (field === 'unit_price') return `Ksh ${v}`
  return String(v)
}

// One row per change, with before/after values when the entry has them.
export default function ActivityList({ items, showBusiness = false }) {
  return (
    <ol className="activity">
      {items.map((a) => {
        const byStockWise = a.actor_role === 'SYSTEM_ADMIN'
        const changes = Object.entries(a.changes || {})
        return (
          <li key={a.id} className={byStockWise ? 'is-platform' : ''}>
            <span className="activity-icon"><Icon name={byStockWise ? 'shield' : ICONS[a.entity_type] || 'clock'} size={18} /></span>
            <div className="activity-body">
              <p className="activity-summary">{a.summary}</p>
              <p className="activity-meta">
                {byStockWise ? <span className="badge badge-platform">StockWise</span> : null}
                <span>{a.actor_name}{!byStockWise && <> · {ROLE_LABELS[a.actor_role] || a.actor_role}</>}</span>
                {showBusiness && a.business_name && <span> · {a.business_name}</span>}
                <span> · <time dateTime={a.created_at} title={fmtDateFull(a.created_at)}>{fmtAgo(a.created_at)}</time></span>
              </p>
              {changes.length > 0 && (
                <table className="changes">
                  <thead><tr><th>Field</th><th>Before</th><th>After</th></tr></thead>
                  <tbody>
                    {changes.map(([f, [before, after]]) => (
                      <tr key={f}>
                        <th scope="row">{FIELD_LABELS[f] || f}</th>
                        <td className="before">{show(f, before)}</td>
                        <td className="after">{show(f, after)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
