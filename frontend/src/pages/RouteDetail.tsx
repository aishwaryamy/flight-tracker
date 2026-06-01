import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getPriceHistory, trackRoute } from '../api/client'
import type { PriceHistoryResponse } from '../api/client'
import { useSessionId } from '../hooks/useSessionId'
import PriceChart from '../components/PriceChart'

export default function RouteDetailPage() {
  const { origin = '', destination = '' } = useParams()
  const sessionId = useSessionId()
  const navigate = useNavigate()

  const [data, setData] = useState<PriceHistoryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [days, setDays] = useState(30)
  const [tracking, setTracking] = useState(false)

  useEffect(() => {
    setLoading(true)
    getPriceHistory(origin, destination, days)
      .then(setData)
      .catch(() => setError('No price history found for this route yet.'))
      .finally(() => setLoading(false))
  }, [origin, destination, days])

  async function handleTrack() {
    setTracking(true)
    try {
      await trackRoute({ origin, destination, session_id: sessionId })
      navigate('/dashboard')
    } finally {
      setTracking(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <button onClick={() => navigate(-1)} className="text-sm text-gray-400 hover:text-gray-600 mb-4">
        ← Back
      </button>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {origin} → {destination}
          </h1>
          <p className="text-gray-400 text-sm mt-0.5">Price history</p>
        </div>
        <button onClick={handleTrack} disabled={tracking} className="btn-primary">
          {tracking ? 'Tracking…' : 'Track prices'}
        </button>
      </div>

      {/* Day range selector */}
      <div className="flex gap-2 mb-5">
        {[7, 14, 30, 60].map(d => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              days === d
                ? 'bg-brand-500 text-white border-brand-500'
                : 'border-gray-200 text-gray-500 hover:border-gray-300'
            }`}
          >
            {d}d
          </button>
        ))}
      </div>

      {loading && (
        <div className="card p-8 text-center text-gray-400 text-sm">Loading price history…</div>
      )}

      {error && (
        <div className="card p-8 text-center">
          <p className="text-gray-500 text-sm">{error}</p>
          <p className="text-gray-400 text-xs mt-2">
            Price history builds up once you start tracking this route.
          </p>
          <button onClick={handleTrack} className="btn-primary mt-4">
            Start tracking now
          </button>
        </div>
      )}

      {data && !loading && (
        <div className="card p-5">
          <PriceChart data={data} />
        </div>
      )}
    </div>
  )
}
