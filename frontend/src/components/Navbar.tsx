import { Link, useLocation } from 'react-router-dom'

export default function Navbar() {
  const { pathname } = useLocation()
  const link = (to: string, label: string) => (
    <Link
      to={to}
      className={`text-sm font-medium transition-colors ${
        pathname === to ? 'text-brand-500' : 'text-gray-500 hover:text-gray-900'
      }`}
    >
      {label}
    </Link>
  )

  return (
    <header className="bg-white border-b border-gray-100 sticky top-0 z-10">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link to="/" className="font-semibold text-gray-900 flex items-center gap-2">
          ✈ FlightTracker
        </Link>
        <nav className="flex items-center gap-6">
          {link('/', 'Search')}
          {link('/dashboard', 'Dashboard')}
          {link('/alerts', 'Alerts')}
        </nav>
      </div>
    </header>
  )
}
