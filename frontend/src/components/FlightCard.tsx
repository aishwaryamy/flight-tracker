import type { FlightOffer } from '../api/client'

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${h}h ${m}m`
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

interface Props {
  offer: FlightOffer
  onTrack: () => void
}

export default function FlightCard({ offer, onTrack }: Props) {
  const vsAvg = offer.price_vs_avg

  return (
    <div className="card p-4 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between gap-4">
        {/* Airline + route */}
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-sm">{offer.airline_name}</span>
            {offer.is_good_deal && (
              <span className="badge-green">🔥 Great deal</span>
            )}
            {offer.stops === 0 ? (
              <span className="badge-gray">Nonstop</span>
            ) : (
              <span className="badge-amber">{offer.stops} stop{offer.stops > 1 ? 's' : ''}</span>
            )}
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>{formatTime(offer.departure_at)}</span>
            <span>→</span>
            <span>{formatTime(offer.arrival_at)}</span>
            <span className="text-gray-400">·</span>
            <span>{formatDuration(offer.duration_minutes)}</span>
          </div>
        </div>

        {/* Price */}
        <div className="text-right shrink-0">
          <div className="text-2xl font-bold text-gray-900">
            ${offer.price.toFixed(0)}
          </div>
          {vsAvg !== null && (
            <div className={`text-xs font-medium ${vsAvg < 0 ? 'text-green-600' : 'text-red-500'}`}>
              {vsAvg < 0 ? '▼' : '▲'} {Math.abs(vsAvg).toFixed(0)}% vs avg
            </div>
          )}
          {offer.predicted_low && (
            <div className="text-xs text-gray-400 mt-0.5">
              Range: ${offer.predicted_low}–${offer.predicted_high}
            </div>
          )}
        </div>
      </div>

      {/* Track button */}
      <div className="mt-3 pt-3 border-t border-gray-50 flex justify-end">
        <button onClick={onTrack} className="btn-secondary text-xs py-1.5 px-3">
          Track this route
        </button>
      </div>
    </div>
  )
}
