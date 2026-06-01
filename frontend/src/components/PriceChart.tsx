import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, ReferenceArea,
} from 'recharts'
import type { PriceHistoryResponse } from '../api/client'

interface Props {
  data: PriceHistoryResponse
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="card p-2 text-xs shadow-lg">
      <div className="text-gray-500">{label}</div>
      <div className="font-semibold text-gray-900">${payload[0].value}</div>
      <div className="text-gray-400">{payload[0].payload.airline}</div>
    </div>
  )
}

export default function PriceChart({ data }: Props) {
  const chartData = data.history.map(p => ({
    date: p.date.slice(5),   // MM-DD
    price: p.price,
    airline: p.airline,
  }))

  // "Good price zone" = below 30-day average
  const goodZoneTop = data.avg_30d
  const goodZoneBottom = data.min_30d

  return (
    <div>
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="card p-3 text-center">
          <div className="text-xs text-gray-400 mb-1">30-day avg</div>
          <div className="text-xl font-bold">${data.avg_30d}</div>
        </div>
        <div className="card p-3 text-center">
          <div className="text-xs text-gray-400 mb-1">Lowest seen</div>
          <div className="text-xl font-bold text-green-600">${data.min_30d}</div>
        </div>
        <div className="card p-3 text-center">
          <div className="text-xs text-gray-400 mb-1">Highest seen</div>
          <div className="text-xl font-bold text-red-500">${data.max_30d}</div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#9ca3af' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#9ca3af' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={v => `$${v}`}
            domain={['auto', 'auto']}
          />
          <Tooltip content={<CustomTooltip />} />

          {/* Good price zone shading */}
          <ReferenceArea
            y1={goodZoneBottom}
            y2={goodZoneTop}
            fill="#dcfce7"
            fillOpacity={0.4}
          />

          {/* Average line */}
          <ReferenceLine
            y={data.avg_30d}
            stroke="#9ca3af"
            strokeDasharray="4 3"
            label={{ value: 'avg', fontSize: 10, fill: '#9ca3af', position: 'right' }}
          />

          <Line
            type="monotone"
            dataKey="price"
            stroke="#3b5bdb"
            strokeWidth={2}
            dot={{ r: 3, fill: '#3b5bdb', strokeWidth: 0 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
        <span className="inline-block w-3 h-3 rounded bg-green-100 border border-green-200" />
        Good price zone (below 30-day avg)
      </div>
    </div>
  )
}
