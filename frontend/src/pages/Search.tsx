import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchFlights, trackRoute } from '../api/client'
import type { FlightSearchResponse } from '../api/client'
import { useSessionId } from '../hooks/useSessionId'
import FlightCard from '../components/FlightCard'
import TrackPromptBanner from '../components/TrackPromptBanner'

const today = new Date().toISOString().slice(0, 10)
const in14 = new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10)

export default function SearchPage() {
  const sessionId = useSessionId()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    origin: 'JFK', destination: 'LHR',
    departure_date: in14, return_date: '', passengers: 1,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState<FlightSearchResponse | null>(null)
  const [tracked, setTracked] = useState(false)

  function set(field: string, value: string | number) {
    setForm(f => ({ ...f, [field]: value }))
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    setResults(null)
    setTracked(false)

    try {
      const res = await searchFlights({
        ...form,
        return_date: form.return_date || undefined,
        session_id: sessionId,
      })
      setResults(res)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not fetch flights. Check your API keys.')
    } finally {
      setLoading(false)
    }
  }

  async function handleTrack() {
    await trackRoute({
      origin: form.origin,
      destination: form.destination,
      session_id: sessionId,
    })
    setTracked(true)
    navigate('/dashboard')
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Find cheap flights</h1>
        <p className="text-gray-500 text-sm mt-1">
          Powered by ML — we flag deals the moment prices drop
        </p>
      </div>

      {/* Search form */}
      <form onSubmit={handleSearch} className="card p-5 mb-6">
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">From</label>
            <input className="input" value={form.origin}
              onChange={e => set('origin', e.target.value.toUpperCase())}
              placeholder="JFK" maxLength={3} required />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">To</label>
            <input className="input" value={form.destination}
              onChange={e => set('destination', e.target.value.toUpperCase())}
              placeholder="LHR" maxLength={3} required />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Depart</label>
            <input className="input" type="date" value={form.departure_date} min={today}
              onChange={e => set('departure_date', e.target.value)} required />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Return (optional)</label>
            <input className="input" type="date" value={form.return_date} min={form.departure_date}
              onChange={e => set('return_date', e.target.value)} />
          </div>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-gray-500">Passengers</label>
            <select className="input w-20"
              value={form.passengers} onChange={e => set('passengers', Number(e.target.value))}>
              {[1, 2, 3, 4, 5].map(n => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Searching…' : 'Search flights'}
          </button>
        </div>
      </form>

      {error && (
        <div className="bg-red-50 text-red-700 text-sm p-3 rounded-lg mb-4">{error}</div>
      )}

      {results && (
        <>
          {/* Smart tracking prompt */}
          {results.show_track_prompt && !tracked && (
            <TrackPromptBanner
              origin={form.origin}
              destination={form.destination}
              sessionId={sessionId}
              searchCount={results.search_count}
              onTracked={() => setTracked(true)}
            />
          )}

          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-900">
              {results.offers.length} flights found
            </h2>
            <button
              onClick={() => navigate(`/route/${form.origin}/${form.destination}`)}
              className="text-xs text-brand-500 hover:underline"
            >
              View price history →
            </button>
          </div>

          <div className="space-y-3">
            {results.offers.map(offer => (
              <FlightCard key={offer.id} offer={offer} onTrack={handleTrack} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
