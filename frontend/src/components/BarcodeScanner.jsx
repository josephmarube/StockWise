import { useEffect, useId, useRef, useState } from 'react'
import { Modal } from './ui'

// Starts and stops run one after another, so a quick close/reopen never leaves the camera on.
let cameraQueue = Promise.resolve()

async function stopSafely(scanner) {
  if (!scanner) return
  try { if (scanner.isScanning) await scanner.stop() } catch { /* already stopped */ }
  try { scanner.clear() } catch { /* nothing to clear */ }
}

function cameraError(e) {
  const msg = String(e?.name || '') + ' ' + String(e?.message || e)
  if (/Permission|NotAllowed/i.test(msg)) return 'Camera access was blocked. Allow the camera for this site in your browser settings, or type the barcode below.'
  if (/NotFound|no camera|device not found|Overconstrained/i.test(msg)) return 'No camera was found on this device. Type the barcode below instead.'
  if (/NotReadable|in use/i.test(msg)) return 'The camera is being used by another app. Close it and try again, or type the barcode below.'
  return 'The camera could not start. Type the barcode below instead.'
}

// Camera barcode scanning in the browser (FR2.5).
// Works on phones, tablets and laptops with a camera. Needs HTTPS, or localhost during development.
// onDetected(code, source): source is 'CAMERA' for a camera read, 'MANUAL' if the code was typed.
export default function BarcodeScanner({ onDetected, onClose, title = 'Scan a barcode' }) {
  const regionId = `scan-${useId().replace(/:/g, '')}`
  const cb = useRef(onDetected)
  cb.current = onDetected
  const [error, setError] = useState('')
  const [ready, setReady] = useState(false)
  const [manual, setManual] = useState('')

  useEffect(() => {
    let cancelled = false
    let scanner = null
    let done = false

    if (!window.isSecureContext) {
      setError('Camera scanning needs a secure (https) connection. Type the barcode below instead.')
      return undefined
    }

    cameraQueue = cameraQueue.then(async () => {
      if (cancelled) return
      try {
        // Loaded on demand so the scanner library is not in the main bundle.
        const { Html5Qrcode, Html5QrcodeSupportedFormats: F } = await import('html5-qrcode')
        if (cancelled) return
        scanner = new Html5Qrcode(regionId, {
          formatsToSupport: [F.EAN_13, F.EAN_8, F.UPC_A, F.UPC_E, F.CODE_128, F.CODE_39, F.ITF, F.QR_CODE],
          useBarCodeDetectorIfSupported: true,
          verbose: false,
        })
        await scanner.start(
          { facingMode: 'environment' },
          {
            fps: 12,
            // Wide, short box suits 1-D barcodes. The library rejects boxes under 50px.
            qrbox: (w, h) => ({
              width: Math.max(50, Math.floor(Math.min(w * 0.85, 360))),
              height: Math.max(50, Math.floor(Math.min(h * 0.5, 180))),
            }),
          },
          (text) => {
            if (done || cancelled) return
            done = true
            try { navigator.vibrate?.(80) } catch { /* no vibration support */ }
            cb.current(text.trim(), 'CAMERA')
          },
          () => {},
        )
        if (cancelled) await stopSafely(scanner)
        else setReady(true)
      } catch (e) {
        if (!cancelled) setError(cameraError(e))
      }
    }).catch(() => {})

    return () => {
      cancelled = true
      cameraQueue = cameraQueue.then(() => stopSafely(scanner))
    }
  }, [regionId])

  function submitTyped() {
    const code = manual.trim()
    if (code) cb.current(code, 'MANUAL')
  }

  return (
    // No auto-focus on the text box: on phones it would open the keyboard over the camera.
    <Modal title={title} onClose={onClose} size="sm" autoFocus={false}>
      <div className="scanner">
        {!error && <div id={regionId} className="scanner-view" aria-label="Camera preview" />}
        {!error && <p className="muted small">{ready ? 'Point the camera at the barcode. It is read automatically.' : 'Starting camera…'}</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
        {/* Not a <form>: React events from this dialog still bubble to the page's own form. */}
        <div className="inline-row">
          <input aria-label="Barcode" placeholder="Or type the barcode" value={manual}
            onChange={(e) => setManual(e.target.value)} autoFocus={!!error}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); submitTyped() } }} />
          <button type="button" className="btn btn-ghost" disabled={!manual.trim()} onClick={submitTyped}>Use</button>
        </div>
      </div>
    </Modal>
  )
}
