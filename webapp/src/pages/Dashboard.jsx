import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, ResponsiveContainer, Tooltip, Cell } from 'recharts'
import { api } from '../api'
import { haptic } from '../tg'

function ProgressBar({ label, current, goal, color }) {
  const pct = goal ? Math.min((current / goal) * 100, 100) : 0
  return (
    <div className="prog-bar">
      <div className="prog-bar-header">
        <span className="prog-bar-label">{label}</span>
        <span className="prog-bar-value">
          {Math.round(current)} / {goal}
        </span>
      </div>
      <div className="prog-track">
        <div className="prog-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={{ background: 'var(--bg2)', padding: '8px 12px', borderRadius: 8, fontSize: 13 }}>
      <div style={{ fontWeight: 600 }}>{d.day_label}</div>
      <div style={{ color: 'var(--hint)' }}>{d.tonnage} кг тоннаж</div>
    </div>
  )
}

export default function Dashboard({ onGoWorkout }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.dashboard()
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="spinner">Загружаем данные...</div>
  if (err) return <div className="spinner" style={{ color: '#f87171' }}>{err}</div>

  const { user, next_workout, nutrition_today, nutrition_goals, workout_history } = data

  return (
    <div className="page">
      {/* Header */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 22, fontWeight: 700 }}>Привет, {user.name} 👋</div>
        <div style={{ fontSize: 14, color: 'var(--hint)', marginTop: 2 }}>
          Неделя {user.week} · {next_workout.week_label}
        </div>
      </div>

      {/* Next workout */}
      <div className="card">
        <div className="section-title">Следующая тренировка</div>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>
          💪 {next_workout.day_label}
        </div>
        <button
          className="btn-primary"
          onClick={() => { haptic('medium'); onGoWorkout() }}
        >
          Начать тренировку
        </button>
      </div>

      {/* Nutrition */}
      <div className="card">
        <div className="section-title">Питание сегодня</div>
        <ProgressBar
          label="🔥 Калории"
          current={nutrition_today.calories}
          goal={nutrition_goals.calories}
          color="#f59e0b"
        />
        <ProgressBar
          label="🥩 Белок"
          current={nutrition_today.protein}
          goal={nutrition_goals.protein}
          color="#3b82f6"
        />
        <ProgressBar
          label="🌾 Углеводы"
          current={nutrition_today.carbs}
          goal={nutrition_goals.carbs}
          color="#10b981"
        />
        <ProgressBar
          label="🫒 Жиры"
          current={nutrition_today.fat}
          goal={nutrition_goals.fat}
          color="#8b5cf6"
        />
      </div>

      {/* Tonnage chart */}
      {workout_history.length > 0 && (
        <div className="card">
          <div className="section-title">Тоннаж по тренировкам</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={[...workout_history].reverse()} barCategoryGap="30%">
              <XAxis
                dataKey="day_label"
                tick={{ fontSize: 10, fill: 'var(--hint)' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
              <Bar dataKey="tonnage" radius={[4, 4, 0, 0]}>
                {[...workout_history].reverse().map((_, i, arr) => (
                  <Cell
                    key={i}
                    fill={i === arr.length - 1 ? 'var(--accent)' : 'rgba(255,255,255,0.2)'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Last workouts list */}
      {workout_history.length > 0 && (
        <div className="card">
          <div className="section-title">Последние тренировки</div>
          {workout_history.slice(0, 5).map((w, i) => (
            <div key={i} className="set-history-item">
              <div>
                <span style={{ fontWeight: 600 }}>{w.day_label}</span>
                <span style={{ color: 'var(--hint)', marginLeft: 8, fontSize: 13 }}>{w.week_label}</span>
              </div>
              <div style={{ textAlign: 'right', fontSize: 13 }}>
                <div style={{ fontWeight: 600 }}>{w.tonnage} кг</div>
                <div style={{ color: 'var(--hint)' }}>RPE {w.avg_rpe} · {w.date}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
