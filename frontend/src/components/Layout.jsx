import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { Icon } from './ui'

const NAV = [
  { to: '/', label: 'Dashboard', icon: 'home', end: true },
  { to: '/record', label: 'Record stock', icon: 'swap' },
  { to: '/products', label: 'Products', icon: 'box' },
  { to: '/suppliers', label: 'Suppliers', icon: 'truck', admin: true },
  { to: '/reports', label: 'Reports', icon: 'chart', admin: true },
  { to: '/users', label: 'Users', icon: 'users', admin: true },
]

// Mobile bottom bar: Record sits in the middle, within thumb reach.
const TABS = [
  { to: '/', label: 'Home', icon: 'home', end: true },
  { to: '/products', label: 'Products', icon: 'box' },
  { to: '/record', label: 'Record', icon: 'swap', primary: true },
  { to: '/reports', label: 'Reports', icon: 'chart', admin: true },
  { to: '/more', label: 'More', icon: 'more', admin: true },
]

export default function Layout() {
  const { user, isAdmin, logout } = useAuth()
  const nav = useNavigate()
  const items = NAV.filter((n) => !n.admin || isAdmin)

  return (
    <div className="shell">
      <a href="#main" className="skip">Skip to content</a>
      <aside className="sidebar">
        <div className="brand">
          <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="17" width="6" height="10" rx="1.5" fill="currentColor" opacity=".55"/><rect x="13" y="11" width="6" height="16" rx="1.5" fill="currentColor" opacity=".8"/><rect x="21" y="5" width="6" height="22" rx="1.5" fill="#D99A00"/></svg>
          <span>StockWise</span>
        </div>
        <nav className="side-nav" aria-label="Main">
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className="side-link">
              <Icon name={n.icon} /> <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-user">
          <div>
            <div className="side-user-name">{user.name}</div>
            <div className="side-user-role">{isAdmin ? 'Admin' : 'Staff'}</div>
          </div>
          <button className="icon-btn" onClick={() => { logout(); nav('/login') }} aria-label="Log out" title="Log out">
            <Icon name="logout" />
          </button>
        </div>
      </aside>

      <header className="topbar">
        <div className="brand">
          <svg width="24" height="24" viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="17" width="6" height="10" rx="1.5" fill="currentColor" opacity=".55"/><rect x="13" y="11" width="6" height="16" rx="1.5" fill="currentColor" opacity=".8"/><rect x="21" y="5" width="6" height="22" rx="1.5" fill="#D99A00"/></svg>
          <span>StockWise</span>
        </div>
        <button className="icon-btn" onClick={() => { logout(); nav('/login') }} aria-label="Log out"><Icon name="logout" /></button>
      </header>

      <main id="main" className="main">
        <Outlet />
      </main>

      <nav className="tabbar" aria-label="Main">
        {TABS.filter((n) => !n.admin || isAdmin).map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className={`tab ${n.primary ? 'tab-primary' : ''}`}>
            <span className="tab-icon"><Icon name={n.icon} size={22} /></span>
            <span>{n.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
