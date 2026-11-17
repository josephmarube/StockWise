import { Link, useNavigate } from 'react-router-dom'
import { useApi } from '../lib/hooks'
import { useAuth } from '../lib/auth'
import { fmtAgo, fmtMoney, fmtNum, fmtQty } from '../lib/format'
import { Empty, ErrorNote, Icon, ProductAvatar, Skeleton, StockBar, StockBadge, TypeTag, sourceLabel } from '../components/ui'
import { BarList, TrendChart, money } from '../components/charts'

export default function Dashboard() {
  const { user, isManager, business } = useAuth()
  // Poll so changes recorded by other users show up without a manual refresh.
  const { data, error, loading, reload } = useApi('/api/dashboard', null, { poll: 10000 })
  const trends = useApi('/api/dashboard/trends', { days: 14 }, { poll: 60000 })
  const nav = useNavigate()
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
      {loading && !data && (
        <div className="figures" aria-label="Loading">
          {[0, 1, 2, 3].map((i) => <div className="figure" key={i}><Skeleton w="45%" h={26} /><Skeleton w="70%" h={12} style={{ marginTop: 8 }} /></div>)}
        </div>
      )}

      {data && data.active_products === 0 && data.recent_movements.length === 0 && (
        <section className="panel onboard" aria-labelledby="start-h">
          <h2 id="start-h">Get {business?.name || 'your shop'} started</h2>
          {isManager ? (
            <ol className="onboard-steps">
              <li className="onboard-step"><strong>Add your products</strong><p>Name, price, reorder level and what's on the shelf today. Scan barcodes as you go.</p><Link className="btn btn-primary btn-sm" to="/products?new=1">Add a product</Link></li>
              <li className="onboard-step"><strong>Invite your staff</strong><p>Send a link on WhatsApp. They set their own password and can record stock straight away.</p><Link className="btn btn-ghost btn-sm" to="/users?invite=1">Invite people</Link></li>
              <li className="onboard-step"><strong>Record sales and deliveries</strong><p>Stock levels, low-stock alerts and reports update from every entry.</p><Link className="btn btn-ghost btn-sm" to="/record">Record stock</Link></li>
            </ol>
          ) : (
            <p className="muted">Your manager hasn't added any products yet. Once they do, you can record sales and deliveries here.</p>
          )}
        </section>
      )}

      {data && (
        <>
          <section className="figures" aria-label="Stock summary">
            <div className="figure"><span className="figure-n">{fmtNum(data.active_products)}</span><span className="figure-l">products</span></div>
            <div className={`figure ${data.out_of_stock_count ? 'figure-warn' : ''}`}><span className="figure-n">{fmtNum(data.out_of_stock_count)}</span><span className="figure-l">out of stock</span></div>
            {isManager && <div className="figure"><span className="figure-n">{fmtMoney(data.stock_value)}</span><span className="figure-l">stock value</span></div>}
            <div className={`figure ${data.low_stock_count ? 'figure-warn' : ''}`}><span className="figure-n">{fmtNum(data.low_stock_count)}</span><span className="figure-l">at or below reorder level</span></div>
          </section>

          {trends.data && trends.data.days.some((d) => d.value_in || d.value_out) && (
            <section className="panel" aria-labelledby="trend-h">
              <div className="panel-head"><h2 id="trend-h">Last 14 days</h2><span className="muted small">value in Ksh, at selling price</span></div>
              <TrendChart days={trends.data.days} />
            </section>
          )}

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
                          <span className="with-avatar"><ProductAvatar name={p.name} categoryId={p.category.id} size={30} /><span className="low-name">{p.name}</span></span>
                          <StockBadge product={p} />
                        </div>
                        <StockBar product={p} compact />
                        <div className="low-nums">
                          <span><strong>{fmtQty(p.current_stock, p.unit)}</strong> left</span>
                          <span>reorder at {fmtQty(p.reorder_threshold, p.unit)}</span>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <div className="stack">
              <section className="panel" aria-labelledby="movers-h">
                <div className="panel-head"><h2 id="movers-h">Fastest moving</h2><span className="muted small">sales value, 14 days</span></div>
                {!trends.data ? <Skeleton h={120} /> : trends.data.top_movers.length === 0
                  ? <Empty title="No sales recorded yet" />
                  : <BarList items={trends.data.top_movers} value={(m) => m.value_out} format={money} label={(m) => m.name} sub={(m) => `${fmtQty(m.qty_out, m.unit)} sold`}
                      onSelect={(m) => nav(`/products/${m.product_id}`)} />}
              </section>
              {isManager && trends.data?.by_category.length > 0 && (
                <section className="panel" aria-labelledby="cat-h">
                  <div className="panel-head"><h2 id="cat-h">Stock value by category</h2></div>
                  <BarList items={trends.data.by_category} value={(c) => Number(c.value)} label={(c) => c.name}
                    sub={(c) => `${fmtNum(c.products)} ${c.products === 1 ? 'product' : 'products'}`} format={money} color="#16794A" />
                </section>
              )}
            </div>
          </div>

          <section className="panel" aria-labelledby="recent-h">
              <div className="panel-head">
                <h2 id="recent-h">Latest stock changes</h2>
                {isManager && <Link to="/reports?tab=audit" className="link">Audit log</Link>}
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
                      <span className={`feed-qty qty-${m.type.toLowerCase()}`}>{m.type === 'IN' ? '+' : '−'}{fmtQty(m.quantity, m.product.unit)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
        </>
      )}
    </div>
  )
}
