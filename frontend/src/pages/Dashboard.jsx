import { Link } from 'react-router-dom'
import { useApi } from '../lib/hooks'
import { useAuth } from '../lib/auth'
import { fmtAgo, fmtMoney, fmtNum } from '../lib/format'
import { Empty, ErrorNote, Icon, Spinner, StockBar, StockBadge, TypeTag, sourceLabel } from '../components/ui'

export default function Dashboard() {
  const { user, isAdmin, business } = useAuth()
  // Poll so changes recorded by other users show up without a manual refresh.
  const { data, error, loading, reload } = useApi('/api/dashboard', null, { poll: 10000 })
  const first = user.name.split(' ')[0]

  return (
    <div className="page">
      <header className="page-head dash-head">
        <div>
          <h1>Hello, {first}</h1>
          {data && (
            <p className="lede">
              {data.active_products === 0
                ? 'No products yet.'
                : data.low_stock_count === 0
                ? 'Everything is above its reorder level.'
                : `${data.low_stock_count} ${data.low_stock_count === 1 ? 'product needs' : 'products need'} restocking${data.out_of_stock_count ? `, ${data.out_of_stock_count} already out` : ''}.`}
            </p>
          )}
        </div>
        <div className="quick-actions">
          <Link to="/record?type=OUT" className="btn btn-out btn-lg"><Icon name="arrowOut" /> Record sale / stock out</Link>
          <Link to="/record?type=IN" className="btn btn-in btn-lg"><Icon name="arrowIn" /> Record delivery / stock in</Link>
        </div>
      </header>

      <ErrorNote error={error} onRetry={reload} />
      {loading && !data && <Spinner />}

      {data && data.active_products === 0 && data.recent_movements.length === 0 && (
        <section className="panel onboard" aria-labelledby="start-h">
          <h2 id="start-h">Get {business?.name || 'your shop'} started</h2>
          {isAdmin ? (
            <ol className="onboard-steps">
              <li className="onboard-step"><strong>Add your products</strong><p>Name, price, reorder level and what's on the shelf today. Scan barcodes as you go.</p><Link className="btn btn-primary btn-sm" to="/products?new=1">Add a product</Link></li>
              <li className="onboard-step"><strong>Invite your staff</strong><p>Send a link on WhatsApp. They set their own password and can record stock straight away.</p><Link className="btn btn-ghost btn-sm" to="/users?invite=1">Invite people</Link></li>
              <li className="onboard-step"><strong>Record sales and deliveries</strong><p>Stock levels, low-stock alerts and reports update from every entry.</p><Link className="btn btn-ghost btn-sm" to="/record">Record stock</Link></li>
            </ol>
          ) : (
            <p className="muted">Your admin hasn't added any products yet. Once they do, you can record sales and deliveries here.</p>
          )}
        </section>
      )}

      {data && (
        <>
          <section className="figures" aria-label="Stock summary">
            <div className="figure"><span className="figure-n">{fmtNum(data.active_products)}</span><span className="figure-l">products</span></div>
            <div className="figure"><span className="figure-n">{fmtNum(data.total_units)}</span><span className="figure-l">units on hand</span></div>
            {isAdmin && <div className="figure"><span className="figure-n">{fmtMoney(data.stock_value)}</span><span className="figure-l">stock value</span></div>}
            <div className={`figure ${data.low_stock_count ? 'figure-warn' : ''}`}><span className="figure-n">{fmtNum(data.low_stock_count)}</span><span className="figure-l">at or below reorder level</span></div>
          </section>

          <div className="dash-grid">
            <section className="panel" aria-labelledby="low-h">
              <div className="panel-head">
                <h2 id="low-h">Reorder soon</h2>
                {data.low_stock_count > 0 && <Link to="/products?low=1" className="link">See all</Link>}
              </div>
              {data.low_stock.length === 0 ? (
                <Empty title="Nothing to reorder">Products appear here when stock falls to their reorder level.</Empty>
              ) : (
                <ul className="low-list">
                  {data.low_stock.slice(0, 8).map((p) => (
                    <li key={p.id}>
                      <Link to={`/products/${p.id}`} className="low-item">
                        <div className="low-main">
                          <span className="low-name">{p.name}</span>
                          <StockBadge product={p} />
                        </div>
                        <StockBar product={p} compact />
                        <div className="low-nums">
                          <span><strong>{fmtNum(p.current_stock)}</strong> left</span>
                          <span>reorder at {fmtNum(p.reorder_threshold)}</span>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="panel" aria-labelledby="recent-h">
              <div className="panel-head">
                <h2 id="recent-h">Latest stock changes</h2>
                {isAdmin && <Link to="/reports?tab=audit" className="link">Audit log</Link>}
              </div>
              {data.recent_movements.length === 0 ? (
                <Empty title="No stock recorded yet" action={<Link className="btn btn-primary" to="/record">Record stock</Link>} />
              ) : (
                <ul className="feed">
                  {data.recent_movements.map((m) => (
                    <li key={m.id} className="feed-item">
                      <TypeTag type={m.type} override={m.override} />
                      <div className="feed-main">
                        <Link to={`/products/${m.product.id}`} className="feed-name">{m.product.name}</Link>
                        <span className="feed-meta">{m.user.name}, {fmtAgo(m.created_at)}{m.source !== 'MANUAL' ? `, ${sourceLabel(m.source).toLowerCase()}` : ''}{m.note ? ` - ${m.note}` : ''}</span>
                      </div>
                      <span className={`feed-qty qty-${m.type.toLowerCase()}`}>{m.type === 'IN' ? '+' : '−'}{fmtNum(m.quantity)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  )
}
