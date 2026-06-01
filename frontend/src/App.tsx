import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import SearchPage from './pages/Search'
import RouteDetailPage from './pages/RouteDetail'
import DashboardPage from './pages/Dashboard'
import AlertsPage from './pages/Alerts'

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <main>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/route/:origin/:destination" element={<RouteDetailPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
