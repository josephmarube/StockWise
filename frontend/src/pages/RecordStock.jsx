import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmtNum } from '../lib/format'
import ProductPicker from '../components/ProductPicker'
import { Confirm, Field, Icon, StockBar, useToast } from '../components/ui'

export default function RecordStock() {
  const [params] = useSearchParams()
  const { isAdmin } = useAuth()
  const toast = useToast()
  const [type, setType] = useState(params.get('type') === 'IN' ? 'IN' : 'OUT')
  const [product, setProduct] = useState(null)
  const [qty, setQty] = useState('1')
  const [note, setNote] = useState('')
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [shortfall, setShortfall] = useState(null) // 409 details
  const [last, setLast] = useState(null)

  useEffect(() => {
    const pid = params.get('product')
    if (pid) api.get(`/api/products/${pid}`).then(setProduct).catch(() => {})
  }, [params])

  const n = Number(qty)
  const qtyValid = Number.isInteger(n) && n > 0 && n <= 1000000
  const after = product && qtyValid ? product.current_stock + (type === 'IN' ? n : -n) : null

  function validate() {
    const e = {}
    if (!product) e.product = 'Choose a product.'
    if (!qtyValid) e.qty = 'Enter a whole number greater than 0.'
    setErrors(e)
    return !Object.keys(e).length
  }

  async function save(override = false) {
    setBusy(true)
    try {
      const res = await api.post('/api/stock/movements', {
        product_id: product.id, type, quantity: n, note: note.trim() || null, override,
      })
      setLast({ ...res, product })
      setProduct({ ...product, current_stock: res.current_stock })
      setQty('1'); setNote(''); setShortfall(null)
      toast(`${type === 'IN' ? 'Added' : 'Removed'} ${fmtNum(n)} × ${product.name}. ${fmtNum(res.current_stock)} now in stock.`)
      if (res.low_stock) toast(`${product.name} is at or below its reorder level.`, 'warn')
    } catch (err) {
      if (err.status === 409 && err.body.code === 'INSUFFICIENT_STOCK') setShortfall(err.body)
      else if (err.status === 422) setErrors({ form: err.message, ...mapFields(err.fields) })
      else setErrors({ form: err.message })
    } finally {
      setBusy(false)
    }
  }

  function submit(e) {
    e.preventDefault()
    if (validate()) save(false)
  }

  const step = (d) => setQty(String(Math.max(1, (Number.isInteger(n) ? n : 0) + d)))

  return (
    <div className="page page-narrow">
      <header className="page-head">
        <h1>Record stock</h1>
      </header>

      <form className={`recorder recorder-${type.toLowerCase()}`} onSubmit={submit} noValidate>
        <div className="switch" role="radiogroup" aria-label="Movement type">
          <button type="button" role="radio" aria-checked={type === 'OUT'} className={`switch-opt opt-out ${type === 'OUT' ? 'on' : ''}`} onClick={() => setType('OUT')}>
            <Icon name="arrowOut" size={22} /><span><strong>Stock out</strong><small>Sale, use or damage</small></span>
          </button>
          <button type="button" role="radio" aria-checked={type === 'IN'} className={`switch-opt opt-in ${type === 'IN' ? 'on' : ''}`} onClick={() => setType('IN')}>
            <Icon name="arrowIn" size={22} /><span><strong>Stock in</strong><small>Delivery or return</small></span>
          </button>
        </div>

        <Field label="Product" id="product" error={errors.product}>
          <ProductPicker value={product} onChange={(p) => { setProduct(p); setErrors({}) }} error={errors.product} autoFocus={!params.get('product')} />
        </Field>

        <Field label="Quantity" id="qty" error={errors.qty}>
          <div className="stepper">
            <button type="button" className="step-btn" onClick={() => step(-1)} aria-label="Decrease quantity"><Icon name="minus" size={26} /></button>
            <input id="qty" inputMode="numeric" pattern="[0-9]*" value={qty} aria-invalid={!!errors.qty}
              onChange={(e) => setQty(e.target.value.replace(/[^0-9]/g, ''))} onFocus={(e) => e.target.select()} />
            <button type="button" className="step-btn" onClick={() => step(1)} aria-label="Increase quantity"><Icon name="plus" size={26} /></button>
          </div>
        </Field>

        {product && after !== null && (
          <div className={`preview ${after < 0 ? 'preview-neg' : ''}`} aria-live="polite">
            <span>{fmtNum(product.current_stock)}</span>
            <Icon name={type === 'IN' ? 'arrowIn' : 'arrowOut'} size={16} />
            <strong>{fmtNum(after)}</strong>
            <span className="preview-l">
              {after < 0 ? 'not enough stock' : after <= product.reorder_threshold ? `at or below reorder level (${fmtNum(product.reorder_threshold)})` : 'after this'}
            </span>
          </div>
        )}

        <Field label="Note (optional)" id="note" hint="For example: invoice number, customer, or reason.">
          <input id="note" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>

        {errors.form && <p className="form-error" role="alert">{errors.form}</p>}

        <button className={`btn btn-lg btn-block ${type === 'IN' ? 'btn-in' : 'btn-out'}`} disabled={busy}>
          {busy ? 'Saving…' : type === 'IN' ? 'Record stock in' : 'Record stock out'}
        </button>
      </form>

      {last && (
        <div className="last-saved">
          <div>
            <strong>{last.product.name}</strong> now has {fmtNum(last.current_stock)} in stock.
            {' '}<Link to={`/products/${last.product.id}`} className="link">View history</Link>
          </div>
          <StockBar product={{ ...last.product, current_stock: last.current_stock }} />
        </div>
      )}

      {shortfall && (isAdmin ? (
        <Confirm title="Not enough stock" confirmLabel="Record anyway" busy={busy}
          onCancel={() => setShortfall(null)} onConfirm={() => save(true)}>
          <p>{product.name} has <strong>{fmtNum(shortfall.available)}</strong> in stock, but you are removing <strong>{fmtNum(shortfall.requested)}</strong>.
            Recording it will leave stock at <strong>{fmtNum(shortfall.available - shortfall.requested)}</strong>.</p>
          <p>Only do this if the physical count is higher than the system shows. The override is marked in the audit log.</p>
        </Confirm>
      ) : (
        <Confirm title="Not enough stock" confirmLabel="OK" tone="primary"
          onCancel={() => setShortfall(null)} onConfirm={() => setShortfall(null)}>
          <p>{product.name} has only <strong>{fmtNum(shortfall.available)}</strong> in stock, so {fmtNum(shortfall.requested)} cannot be removed. Nothing was saved.</p>
          <p>If the shelf count is different, ask an admin to record this stock out.</p>
        </Confirm>
      ))}
    </div>
  )
}

function mapFields(f = {}) {
  const out = {}
  if (f.quantity) out.qty = f.quantity
  if (f.product_id) out.product = f.product_id
  return out
}
