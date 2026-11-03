import { useState } from 'react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import { Field, Modal, useToast } from './ui'

const SKU_RE = /^[A-Za-z0-9._-]+$/

// Add (FR1.1) or edit (FR1.2) a product. Stock level is changed only through stock movements.
export default function ProductForm({ product, onClose, onSaved }) {
  const editing = !!product
  const toast = useToast()
  const cats = useApi('/api/categories')
  const sups = useApi('/api/suppliers', { include_inactive: false }, { skip: editing })
  const [f, setF] = useState(() => ({
    sku: product?.sku || '',
    name: product?.name || '',
    category_id: product?.category.id || '',
    unit_price: product ? String(product.unit_price) : '',
    reorder_threshold: product ? String(product.reorder_threshold) : '',
    initial_stock: '0',
    supplier_ids: [],
  }))
  const [newCat, setNewCat] = useState(null)
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))

  function validate() {
    const e = {}
    if (!f.sku.trim()) e.sku = 'Enter a SKU.'
    else if (!SKU_RE.test(f.sku.trim())) e.sku = 'Use letters, numbers, dots, dashes or underscores only.'
    if (!f.name.trim()) e.name = 'Enter a product name.'
    if (!f.category_id && !newCat?.trim()) e.category_id = 'Choose a category.'
    if (f.unit_price === '' || !/^\d+(\.\d{1,2})?$/.test(f.unit_price)) e.unit_price = 'Enter a price like 120 or 120.50.'
    if (!/^\d+$/.test(f.reorder_threshold)) e.reorder_threshold = 'Enter a whole number, 0 or more.'
    if (!editing && !/^\d+$/.test(f.initial_stock)) e.initial_stock = 'Enter a whole number, 0 or more.'
    setErrors(e)
    return !Object.keys(e).length
  }

  async function submit(e) {
    e.preventDefault()
    if (!validate()) return
    setBusy(true)
    try {
      let categoryId = Number(f.category_id)
      if (newCat?.trim()) {
        const c = await api.post('/api/categories', { name: newCat.trim() })
        categoryId = c.id
      }
      const body = {
        sku: f.sku.trim(), name: f.name.trim(), category_id: categoryId,
        unit_price: f.unit_price, reorder_threshold: Number(f.reorder_threshold),
      }
      const saved = editing
        ? await api.patch(`/api/products/${product.id}`, body)
        : await api.post('/api/products', { ...body, initial_stock: Number(f.initial_stock), supplier_ids: f.supplier_ids })
      toast(editing ? 'Product saved' : 'Product added')
      onSaved(saved)
    } catch (err) {
      const fe = {}
      Object.entries(err.fields || {}).forEach(([k, v]) => { fe[k] = v })
      if (err.status === 409 && /SKU/i.test(err.message)) fe.sku = err.message
      else if (err.status === 409 && /Category/i.test(err.message)) fe.category_id = err.message
      else fe.form = err.message
      setErrors(fe)
    } finally {
      setBusy(false)
    }
  }

  const toggleSup = (id) => setF((x) => ({
    ...x, supplier_ids: x.supplier_ids.includes(id) ? x.supplier_ids.filter((s) => s !== id) : [...x.supplier_ids, id],
  }))

  return (
    <Modal title={editing ? `Edit ${product.name}` : 'Add product'} onClose={onClose} size="lg"
      footer={<>
        <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" form="product-form" className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : editing ? 'Save changes' : 'Add product'}</button>
      </>}>
      <form id="product-form" className="form-grid" onSubmit={submit} noValidate>
        <Field label="Product name" id="p-name" error={errors.name}>
          <input id="p-name" value={f.name} onChange={set('name')} maxLength={200} />
        </Field>
        <Field label="SKU" id="p-sku" error={errors.sku} hint="A unique code for this product, e.g. BEV-001">
          <input id="p-sku" value={f.sku} onChange={set('sku')} maxLength={64} autoCapitalize="characters" style={{ textTransform: 'uppercase' }} />
        </Field>
        <Field label="Category" id="p-cat" error={errors.category_id}>
          {newCat === null ? (
            <div className="inline-row">
              <select id="p-cat" value={f.category_id} onChange={set('category_id')}>
                <option value="">Choose…</option>
                {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setNewCat('')}>New</button>
            </div>
          ) : (
            <div className="inline-row">
              <input id="p-cat" placeholder="New category name" value={newCat} onChange={(e) => setNewCat(e.target.value)} maxLength={100} autoFocus />
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setNewCat(null)}>Cancel</button>
            </div>
          )}
        </Field>
        <Field label="Unit price (KES)" id="p-price" error={errors.unit_price}>
          <input id="p-price" inputMode="decimal" value={f.unit_price} onChange={set('unit_price')} />
        </Field>
        <Field label="Reorder level" id="p-thr" error={errors.reorder_threshold} hint="Flag as low stock at or below this quantity.">
          <input id="p-thr" inputMode="numeric" value={f.reorder_threshold} onChange={set('reorder_threshold')} />
        </Field>
        {!editing && (
          <Field label="Opening stock" id="p-init" error={errors.initial_stock} hint="Count on the shelf today. Recorded as a stock in.">
            <input id="p-init" inputMode="numeric" value={f.initial_stock} onChange={set('initial_stock')} />
          </Field>
        )}
        {!editing && sups.data?.length > 0 && (
          <fieldset className="span-2 checks">
            <legend>Suppliers (optional)</legend>
            {sups.data.map((s) => (
              <label key={s.id} className="check">
                <input type="checkbox" checked={f.supplier_ids.includes(s.id)} onChange={() => toggleSup(s.id)} /> {s.name}
              </label>
            ))}
          </fieldset>
        )}
        {errors.form && <p className="form-error span-2" role="alert">{errors.form}</p>}
      </form>
    </Modal>
  )
}
