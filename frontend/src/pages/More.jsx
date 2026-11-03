import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { Icon } from '../components/ui'

// Mobile-only overflow menu for admin pages that don't fit in the bottom bar.
export default function More() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  return (
    <div className="page page-narrow">
      <header className="page-head"><h1>More</h1></header>
      <ul className="more-list">
        <li><Link to="/suppliers"><Icon name="truck" /> Suppliers</Link></li>
        <li><Link to="/users"><Icon name="users" /> Users</Link></li>
        <li><Link to="/reports?tab=audit"><Icon name="chart" /> Audit log</Link></li>
        <li><button onClick={() => { logout(); nav('/login') }}><Icon name="logout" /> Log out {user.name}</button></li>
      </ul>
    </div>
  )
}
