import { useState } from 'react'
import { useApi } from '../lib/hooks'
import ActivityList from '../components/ActivityList'
import { Empty, ErrorNote, Pager, SkeletonRows } from '../components/ui'

const FILTERS = [
  { key: '', label: 'Everything' },
  { key: 'product', label: 'Products' },
  { key: 'supplier', label: 'Suppliers' },
  { key: 'user', label: 'People' },
  { key: 'business', label: 'Business' },
  { key: 'stockwise', label: 'By StockWise' },
]
const LIMIT = 30

// Managers: who changed what in this business, with before/after values.
// Stock in/out has its own audit log under Reports.
export default function Activity() {
  const [filter, setFilter] = useState('')
  const [offset, setOffset] = useState(0)
  const params = { limit: LIMIT, offset }
  if (filter === 'stockwise') params.system_admin_only = true
  else if (filter) params.entity_type = filter
  const { data, error, loading, reload } = useApi('/api/activity', params)

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Activity</h1>
          <p className="muted">Changes to products, suppliers, people and your business. Stock in and out is in Reports › Audit log.</p>
        </div>
      </header>
      <div className="chips" role="group" aria-label="Show">
        {FILTERS.map((f) => (
          <button key={f.key} className={`chip-btn ${filter === f.key ? 'on' : ''}`} aria-pressed={filter === f.key}
            onClick={() => { setFilter(f.key); setOffset(0) }}>{f.label}</button>
        ))}
      </div>
      <ErrorNote error={error} onRetry={reload} />
      {loading && !data && <SkeletonRows rows={6} cols={2} />}
      {data && data.items.length === 0 && (
        <Empty title={filter === 'stockwise' ? 'StockWise has made no changes to your business' : 'Nothing here yet'}>
          {filter === 'stockwise' ? 'If StockWise ever renames or deactivates your business, it will show here.' : 'Changes appear here as your team works.'}
        </Empty>
      )}
      {data && data.items.length > 0 && <ActivityList items={data.items} />}
      {data && <Pager total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
    </div>
  )
}
