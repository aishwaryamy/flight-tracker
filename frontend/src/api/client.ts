import axios from 'axios'

export const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL || ''}/api`,
  timeout: 15000,
})

// ---- Types ----

export interface FlightOffer {
  id: string
  airline: string
  airline_name: string
  price: number
  currency: string
  stops: number
  duration_minutes: number
  departure_at: string
  arrival_at: string
  origin: string
  destination: string
  price_vs_avg: number | null
  is_good_deal: boolean
  predicted_low: number | null
  predicted_high: number | null
}

export interface FlightSearchResponse {
  offers: FlightOffer[]
  search_count: number
  show_track_prompt: boolean
  route_key: string
}

export interface TrackRouteRequest {
  origin: string
  destination: string
  session_id: string
  alert_email?: string
  target_price?: number
}

export interface PricePoint {
  date: string
  price: number
  airline: string
}

export interface PriceHistoryResponse {
  origin: string
  destination: string
  history: PricePoint[]
  avg_30d: number
  min_30d: number
  max_30d: number
  current_price: number | null
}

export interface TrackedRoute {
  route_id: number
  origin: string
  destination: string
  message: string
}

export interface AlertOut {
  id: number
  route_id: number
  alert_type: string
  trigger_price: number
  baseline_price: number
  pct_change: number
  email_sent: boolean
  created_at: string
}

// ---- API calls ----

export async function searchFlights(params: {
  origin: string
  destination: string
  departure_date: string
  return_date?: string
  passengers: number
  session_id: string
}): Promise<FlightSearchResponse> {
  const { data } = await api.post('/flights/search', params)
  return data
}

export async function trackRoute(req: TrackRouteRequest): Promise<TrackedRoute> {
  const { data } = await api.post('/flights/track', req)
  return data
}

export async function untrackRoute(routeId: number): Promise<void> {
  await api.delete(`/flights/track/${routeId}`)
}

export async function getTrackedRoutes(sessionId: string): Promise<TrackedRoute[]> {
  const { data } = await api.get(`/flights/track/${sessionId}`)
  return data
}

export async function getPriceHistory(
  origin: string,
  destination: string,
  days = 30,
): Promise<PriceHistoryResponse> {
  const { data } = await api.get(`/flights/history/${origin}/${destination}`, {
    params: { days },
  })
  return data
}

export async function getAlertHistory(sessionId: string): Promise<AlertOut[]> {
  const { data } = await api.get(`/alerts/history/${sessionId}`)
  return data.alerts
}
