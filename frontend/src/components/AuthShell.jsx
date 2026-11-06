// Shared frame for the signed-out pages: login, signup and joining by invite.
export function Brand() {
  return (
    <div className="brand brand-dark">
      <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="17" width="6" height="10" rx="1.5" fill="#1F2A5C" opacity=".55"/><rect x="13" y="11" width="6" height="16" rx="1.5" fill="#1F2A5C" opacity=".8"/><rect x="21" y="5" width="6" height="22" rx="1.5" fill="#D99A00"/></svg>
      <span>StockWise</span>
    </div>
  )
}

export default function AuthShell({ tagline, children }) {
  return (
    <div className="login">
      <div className="login-side" aria-hidden="true">
        <div className="login-shelves">
          {[62, 35, 88, 18, 70, 46, 95, 28].map((h, i) => (
            <div key={i} className={`shelf-bar ${h < 30 ? 'is-low' : ''}`} style={{ '--h': `${h}%`, '--d': `${i * 70}ms` }} />
          ))}
        </div>
        <p className="login-tag">{tagline}</p>
      </div>
      {children}
    </div>
  )
}
