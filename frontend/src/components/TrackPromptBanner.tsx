import { useState } from 'react'
import { trackRoute } from '../api/client'

interface Props {
  origin: string
  destination: string
  sessionId: string
  searchCount: number
  onTracked: () => void
}

export default function TrackPromptBanner({ origin, destination, sessionId, searchCount, onTracked }: Props) {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  async function handleTrack() {
    setLoading(true)
    try {
      await trackRoute({ origin, destination, session_id: sessionId, alert_email: email || undefined })
      onTracked()
      setDismissed(true)
    } catch {
      alert('Something went wrong, please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-brand-50 border border-brand-500/20 rounded-xl p-4 mb-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-900">
            🤖 You've searched <strong>{origin} → {destination}</strong> {searchCount} times this week
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            Want us to monitor prices and alert you when they drop?
          </p>
          <div className="flex gap-2 mt-3">
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="your@email.com (optional)"
              className="input text-sm py-1.5 max-w-xs"
            />
            <button
              onClick={handleTrack}
              disabled={loading}
              className="btn-primary text-sm py-1.5"
            >
              {loading ? 'Setting up…' : 'Track prices'}
            </button>
          </div>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-gray-400 hover:text-gray-600 text-lg leading-none mt-0.5"
        >
          ×
        </button>
      </div>
    </div>
  )
}
