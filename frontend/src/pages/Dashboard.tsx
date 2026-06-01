import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getTrackedRoutes, getPriceHistory, untrackRoute } from '../api/client'
import type { TrackedRoute, PriceHistoryResponse } from '../api/client'
import { useSessionId } from '../hooks/useSessionId'

interface RouteWithStats extends TrackedRoute {
  stats?: PriceHistoryResponse
  loading?: boolean
}

export default function DashboardPage() {
  const sessionId = useSessionId()
  const navigate = useNavigate()
  const [routes, setRoutes] = useState<RouteWithStats[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const tracked = await getTrackedRoutes(sessionId).catch(() => [])
      setRoutes(tracked.map(r => ({ ...r, loading: true })))
      setLoading(false)

      // Fetch stats for each route in parallel
      for (const r of tracked) {
        getPriceHistory(r.origin, r.destination)
          .then(stats => {
            setRoutes(prev =>
              prev.map(p => p.route_id === r.route_id ? { ...p, stats, loading: false } : p)
            )
          })
          .catch(() => {
            setRoutes(prev =>
              prev.map(p => p.route_id === r.route_id ? { ...p, loading: false } : p)
            )
          })
      }
    }
    load()
  }, [sessionId])

  async function handleUntrack(routeId: number) {
    await untrackRoute(routeId)
    setRoutes(prev => prev.filter(r => r.route_id !== routeId))
  }

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="text-gray-400 text-sm">Loading tracked routes…</div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-0.5">Your tracked routes</p>
        </div>
        <button onClick={() => navigate('/')} className="btn-primary">
          + Search flights
        </button>
      </div>

      {routes.length === 0 ? (
        <div className="card p-10 text-center">
          <p className="text-3xl mb-3">✈</p>
          <p className="font-medium text-gray-700 mb-1">No routes tracked yet</p>
          <p className="text-sm text-gray-400 mb-4">
            Search for flights and track routes to monitor price drops.
          </p>
          <button onClick={() => navigate('/')} className="btn-primary">
            Search flights
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {routes.map(route => (
            <RouteCard
              key={route.route_id}
              route={route}
              onDetail={() => navigate(`/route/${route.origin}/${route.destination}`)}
              onUntrack={() => handleUntrack(route.route_id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function RouteCard({
  route,
  onDetail,
  onUntrack,
}: {
  route: RouteWithStats
  onDetail: () => void
  onUntrack: () => void
}) {
  const { stats, loading } = route
  const current = stats?.current_price
  const avg = stats?.avg_30d
  const delta = current && avg ? ((current - avg) / avg) * 100 : null

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between mb-3">
        <button onClick={onDetail} className="text-left group">
          <div className="font-bold text-lg group-hover:text-brand-500 transition-colors">
            {route.origin} → {route.destination}
          </div>
        </button>
        <button
          onClick={onUntrack}
          className="text-gray-300 hover:text-red-400 text-sm transition-colors"
          title="Stop tracking"
        >
          ×
        </button>
      </div>

      {loading ? (
        <div className="h-12 flex items-center">
          <div className="text-xs text-gray-400">Loading…</div>
        </div>
      ) : stats ? (
        <>
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-2xl font-bold">${current?.toFixed(0) ?? '—'}</span>
            {delta !== null && (
              <span className={`text-xs font-medium ${delta < 0 ? 'text-green-600' : 'text-red-500'}`}>
                {delta < 0 ? '▼' : '▲'} {Math.abs(delta).toFixed(0)}% vs avg
              </span>
            )}
          </div>
          <div className="text-xs text-gray-400">
            30d avg: ${avg?.toFixed(0)} · Low: ${stats.min_30d} · High: ${stats.max_30d}
          </div>
        </>
      ) : (
        <div className="text-xs text-gray-400">No data yet — polling in progress</div>
      )}

      <button onClick={onDetail} className="btn-secondary w-full mt-3 text-xs py-1.5">
        View history →
      </button>
    </div>
  )
}
