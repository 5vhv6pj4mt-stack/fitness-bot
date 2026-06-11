import { useState, useEffect } from 'react'
import { AreaChart, Area, XAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../api'

export default function ExerciseProgressChart({ exercise, onClose }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!exercise) return
    setLoading(true)
    api.exerciseHistory(exercise)
      .then(d => setHistory(d.history || []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false))
  }, [exercise])

  const last = history[history.length - 1]?.weight || 0
  const prev = history[history.length - 2]?.weight || 0
  const delta = history.length >= 2 ? parseFloat((last - prev).toFixed(1)) : 0

  return (
    <div style={{ marginTop: 12, borderTop: '1px solid var(--sep)', paddingTop: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{exercise}</div>
        {onClose && (
          <button onClick={onClose} style={{
            background: 'var(--bg3)', border: 'none', borderRadius: 8,
            padding: '3px 10px', color: 'var(--hint)', cursor: 'pointer', fontSize: 12,
          }}>✕</button>
        )}
      </div>

      {loading && (
        <div style={{ color: 'var(--hint)', fontSize: 13, textAlign: 'center', padding: '12px 0' }}>
          Загружаем...
        </div>
      )}

      {!loading && history.length < 2 && (
        <div style={{ color: 'var(--hint)', fontSize: 13, textAlign: 'center', padding: '12px 0' }}>
          Недостаточно данных для графика
        </div>
      )}

      {!loading && history.length >= 2 && (
        <>
          <div style={{ marginBottom: 8 }}>
            <span style={{ fontSize: 22, fontWeight: 700 }}>{last} кг</span>
            {delta !== 0 && (
              <span style={{ marginLeft: 8, fontSize: 13, color: delta > 0 ? '#30d158' : '#ff453a' }}>
                {delta > 0 ? '↑ +' : '↓ '}{Math.abs(delta)} кг
              </span>
            )}
            <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--hint)' }}>
              {history.length} записей
            </span>
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <AreaChart data={history} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="exPrGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#30d158" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#30d158" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--hint)' }} axisLine={false} tickLine={false} />
              <Tooltip
                content={({ active, payload }) =>
                  active && payload?.length
                    ? <div style={{ background: 'var(--bg2)', padding: '6px 10px', borderRadius: 8, fontSize: 12 }}>
                        <div style={{ fontWeight: 600 }}>{payload[0].payload.date}</div>
                        <div style={{ color: 'var(--hint)' }}>{payload[0].value} кг</div>
                      </div>
                    : null
                }
                cursor={{ stroke: '#30d158', strokeWidth: 1, strokeDasharray: '4 2' }}
              />
              <Area
                type="monotone" dataKey="weight"
                stroke="#30d158" strokeWidth={2.5}
                fill="url(#exPrGrad)"
                dot={{ fill: '#30d158', r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: '#30d158', stroke: 'var(--bg)', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  )
}
