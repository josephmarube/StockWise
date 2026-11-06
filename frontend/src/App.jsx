import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './lib/auth'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Join from './pages/Join'
import Dashboard from './pages/Dashboard'
import RecordStock from './pages/RecordStock'
import Products from './pages/Products'
import ProductDetail from './pages/ProductDetail'
import Suppliers from './pages/Suppliers'
import Reports from './pages/Reports'
import Users from './pages/Users'
import More from './pages/More'

function RequireAuth({ children, admin }) {
  const { user, ready, isAdmin } = useAuth()
  const loc = useLocation()
  if (!ready) return <div className="center-screen"><Spinner /></div>
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname + loc.search }} replace />
  if (admin && !isAdmin) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/join/:token" element={<Join />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Dashboard />} />
        <Route path="record" element={<RecordStock />} />
        <Route path="products" element={<Products />} />
        <Route path="products/:id" element={<ProductDetail />} />
        <Route path="suppliers" element={<RequireAuth admin><Suppliers /></RequireAuth>} />
        <Route path="reports" element={<RequireAuth admin><Reports /></RequireAuth>} />
        <Route path="users" element={<RequireAuth admin><Users /></RequireAuth>} />
        <Route path="more" element={<RequireAuth admin><More /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
