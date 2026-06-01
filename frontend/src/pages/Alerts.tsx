import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAlertHistory } from '../api/client'
import type { AlertOut } from '../api/client'
import { useSessionId } from '../hooks/useSessionId'
import { formatDistanceToNow } from 'date-fns'

export default function AlertsPage() {
  const sessionId = useSessionId()
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState<AlertOut[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAlertHistory(sessionId)
      .then(setAlerts)
      .catch(() => setAlerts([]))
      .finally(() => setLoading(false))
  }, [sessionId])

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Alert history</h1>
        <p className="text-gray-500 text-sm mt-0.5">Every price drop we caught for you</p>
      </div>

      {loading && (
        <div className="text-gray-400 text-sm">Loading…</div>
      )}

      {!loading && alerts.length === 0 && (
        <div className="card p-10 text-center">
          <p className="text-3xl mb-3">🔔</p>
          <p className="font-medium text-gray-700 mb-1">No alerts yet</p>
          <p className="text-sm text-gray-400 mb-4">
            Track some routes — we'll fire an alert the first time we detect a deal.
          </p>
          <button onClick={() => navigate('/')} className="btn-primary">
            Search flights
          </button>
        </div>
      )}

      {!loading && alerts.length > 0 && (
        <div className="space-y-3">
          {alerts.map(alert => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </div>
      )}
    </div>
  )
}

function AlertCard({ alert }: { alert: AlertOut }) {
  const ago = formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })
  const isPriceDrop = alert.pct_change < 0

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              alert.alert_type === 'anomaly'
                ? 'bg-purple-50 text-purple-700'
                : 'bg-green-50 text-green-700'
            }`}>
              {alert.alert_type === 'anomaly' ? '🔍 Anomaly' : '💰 Price drop'}
            </span>
            {alert.email_sent && (
              <span className="badge-gray">📧 emailed</span>
            )}
          </div>
          <div className="text-sm text-gray-700">
            Price hit <span className="font-semibold">${alert.trigger_price.toFixed(0)}</span>
            {' '}(avg was ${alert.baseline_price.toFixed(0)})
          </div>
          <div className={`text-xs font-medium mt-0.5 ${isPriceDrop ? 'text-green-600' : 'text-red-500'}`}>
            {isPriceDrop ? '▼' : '▲'} {Math.abs(alert.pct_change).toFixed(0)}% vs baseline
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-xs text-gray-400">{ago}</div>
        </div>
      </div>
    </div>
  )
}
