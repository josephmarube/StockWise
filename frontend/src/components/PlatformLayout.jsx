import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { Icon } from './ui'

const NAV = [
  { to: '/platform', label: 'Businesses', icon: 'store', end: true },
  { to: '/platform/activity', label: 'Activity', icon: 'clock' },
]

// The System Admin area. Separate from the shop layout: a System Admin belongs to no business.
export default function PlatformLayout() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const out = () => { logout(); nav('/login') }
  return (
    <div className="shell">
      <a href="#main" className="skip">Skip to content</a>
      <aside className="sidebar">
        <div className="brand">
          <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="17" width="6" height="10" rx="1.5" fill="currentColor" opacity=".55"/><rect x="13" y="11" width="6" height="16" rx="1.5" fill="currentColor" opacity=".8"/><rect x="21" y="5" width="6" height="22" rx="1.5" fill="#D99A00"/></svg>
          <span>StockWise</span>
        </div>
        <div className="side-business side-platform" title="System Admin area"><Icon name="shield" size={16} /> System Admin</div>
        <nav className="side-nav" aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className="side-link"><Icon name={n.icon} /> <span>{n.label}</span></NavLink>
          ))}
        </nav>
        <div className="side-user">
          <div>
            <div className="side-user-name">{user.name}</div>
            <div className="side-user-role">System Admin</div>
          </div>
          <button className="icon-btn" onClick={out} aria-label="Log out" title="Log out"><Icon name="logout" /></button>
        </div>
      </aside>

      <header className="topbar">
        <div className="brand">
          <svg width="24" height="24" viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="17" width="6" height="10" rx="1.5" fill="currentColor" opacity=".55"/><rect x="13" y="11" width="6" height="16" rx="1.5" fill="currentColor" opacity=".8"/><rect x="21" y="5" width="6" height="22" rx="1.5" fill="#D99A00"/></svg>
          <span>StockWise</span>
          <span className="top-business">System Admin</span>
        </div>
        <button className="icon-btn" onClick={out} aria-label="Log out"><Icon name="logout" /></button>
      </header>

      <main id="main" className="main"><Outlet /></main>

      <nav className="tabbar" aria-label="Main">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className="tab">
            <span className="tab-icon"><Icon name={n.icon} size={22} /></span><span>{n.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
