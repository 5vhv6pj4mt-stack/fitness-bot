import { useEffect, useState } from 'react'
import { api, friendlyError } from '../api'
import { haptic } from '../tg'

const DAYS_RU = ['Воскресенье','Понедельник','Вторник','Среда','Четверг','Пятница','Суббота']
const MONTHS_RU = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']

function todayLabel() {
  const d = new Date()
  return `${DAYS_RU[d.getDay()]}, ${d.getDate()} ${MONTHS_RU[d.getMonth()]}`
}

// SVG ring chart for calories
function CalorieRing({ current, goal }) {
  const r = 38
  const circ = 2 * Math.PI * r
  const ratio = goal > 0 ? current / goal : 0
  const pct = Math.min(ratio, 1)
  const offset = circ * (1 - pct)
  const overflow = ratio > 1.1
  const ringColor = overflow ? '#ff453a' : 'var(--blue)'
  return (
    <div style={{ position: 'relative', flexShrink: 0 }}>
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--bg3)" strokeWidth="9" />
        <circle
          cx="50" cy="50" r={r} fill="none"
          stroke={ringColor} strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          transform="rotate(-90 50 50)"
          style={{ transition: 'stroke-dashoffset 0.5s, stroke 0.3s' }}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: overflow ? '#ff453a' : 'var(--text)' }}>
          {Math.round(current)}
        </div>
        <div style={{ fontSize: 10, color: 'var(--hint)', marginTop: 1 }}>из {goal}</div>
      </div>
    </div>
  )
}

// Macro bar row
function MacroRow({ label, current, goal, color }) {
  const pct = goal > 0 ? Math.min((current / goal) * 100, 100) : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 12, color: 'var(--hint)', width: 14, fontWeight: 600 }}>{label}</span>
      <div style={{ flex: 1, height: 6, background: 'var(--bg3)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 3, transition: 'width 0.5s' }} />
      </div>
      <span style={{ fontSize: 11, color: 'var(--hint)', width: 60, textAlign: 'right' }}>
        {Math.round(current)} / {goal}г
      </span>
    </div>
  )
}

export default function Dashboard({ onGoWorkout, onGoProfile }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  const load = () => {
    setLoading(true); setErr(null)
    api.dashboard()
      .then(setData)
      .catch((e) => setErr(friendlyError(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="spinner">Загружаем данные...</div>
  if (err) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16, padding: 24 }}>
      <div style={{ color: '#f87171', fontSize: 14, textAlign: 'center' }}>{err}</div>
      <button className="btn-primary" style={{ maxWidth: 200 }} onClick={() => { haptic('light'); load() }}>
        Попробовать снова
      </button>
    </div>
  )

  const { user, next_workout, nutrition_today, nutrition_goals, week_stats, streak } = data
  if (!user || !next_workout || !nutrition_today || !nutrition_goals) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16, padding: 24 }}>
        <div style={{ color: '#f87171', fontSize: 14, textAlign: 'center' }}>Не удалось загрузить данные</div>
        <button className="btn-primary" style={{ maxWidth: 200 }} onClick={() => { haptic('light'); load() }}>
          Попробовать снова
        </button>
      </div>
    )
  }

  const initial = (user.name || '?')[0].toUpperCase()
  const remaining = Math.max(0, Math.round((nutrition_goals.calories || 0) - (nutrition_today.calories || 0)))

  return (
    <div className="page">

      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
        padding: '4px 0 12px',
      }}>
        <div>
          <div style={{ fontSize: 24, fontWeight: 700 }}>Привет, {user.name} 👋</div>
          <div style={{ fontSize: 14, color: 'var(--hint)', marginTop: 2 }}>{todayLabel()}</div>
        </div>
        <button
          onClick={() => { haptic('light'); onGoProfile?.() }}
          style={{
            width: 36, height: 36, background: 'var(--blue)', borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, fontWeight: 700, color: '#fff', border: 'none', cursor: 'pointer',
            flexShrink: 0,
          }}
        >
          {initial}
        </button>
      </div>

      {/* Nutrition card */}
      <div className="card" style={{ marginBottom: 10 }}>
        <div className="section-title">Питание сегодня</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <CalorieRing current={nutrition_today.calories || 0} goal={nutrition_goals.calories || 1} />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <MacroRow label="Б" current={nutrition_today.protein || 0} goal={nutrition_goals.protein || 1} color="var(--blue)" />
            <MacroRow label="Ж" current={nutrition_today.fat || 0} goal={nutrition_goals.fat || 1} color="var(--orange)" />
            <MacroRow label="У" current={nutrition_today.carbs || 0} goal={nutrition_goals.carbs || 1} color="var(--green)" />
          </div>
        </div>
        <div style={{ fontSize: 12, color: 'var(--hint)', marginTop: 10 }}>
          Осталось <span style={{ color: 'var(--text)', fontWeight: 600 }}>{remaining} ккал</span> до цели
        </div>
      </div>

      {/* Today's workout */}
      <div className="card" style={{ marginBottom: 10 }}>
        <div className="section-title">Тренировка сегодня</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', padding: '3px 10px',
            borderRadius: 20, fontSize: 12, fontWeight: 600,
            background: 'rgba(255,159,10,0.15)', color: 'var(--orange)',
          }}>
            {next_workout.week_label}
          </span>
          <span style={{
            display: 'inline-flex', alignItems: 'center', padding: '3px 10px',
            borderRadius: 20, fontSize: 12, fontWeight: 600,
            background: 'rgba(10,132,255,0.15)', color: 'var(--blue)',
          }}>
            {next_workout.day_label}
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
          {(next_workout.exercises || []).map((ex, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
              <div style={{ width: 6, height: 6, background: 'var(--blue)', borderRadius: '50%', flexShrink: 0 }} />
              <span>{ex.name}</span>
              <span style={{ color: 'var(--hint)', fontSize: 13, marginLeft: 'auto' }}>
                {ex.sets}×{ex.reps}{ex.weight ? ` · ${ex.weight}кг` : ''}
              </span>
            </div>
          ))}
          {next_workout.total_exercises > 4 && (
            <div style={{ fontSize: 12, color: 'var(--hint)' }}>
              + ещё {next_workout.total_exercises - 4} упражнения
            </div>
          )}
        </div>
        <button className="btn-primary" onClick={() => { haptic('medium'); onGoWorkout() }}>
          💪 Начать тренировку
        </button>
      </div>

      {/* Streak */}
      {streak && streak.current > 0 && (
        <div className="card" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 28 }}>
                {streak.current >= 10 ? '🔥' : streak.current >= 5 ? '⚡' : '💪'}
              </span>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>
                  {streak.current} {streak.current === 1 ? 'тренировка' : streak.current < 5 ? 'тренировки' : 'тренировок'} подряд
                </div>
                <div style={{ fontSize: 12, color: 'var(--hint)', marginTop: 1 }}>
                  Серия не прерывается
                </div>
              </div>
            </div>
            {streak.longest > 1 && (
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 11, color: 'var(--hint)' }}>Рекорд</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--orange)' }}>{streak.longest}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Week stats */}
      {week_stats && week_stats.tonnage > 0 && (
        <div style={{
          fontSize: 13, color: 'var(--hint)', textAlign: 'center',
          padding: '6px 0', marginBottom: 4,
        }}>
          📊 Тоннаж{' '}
          <span style={{ color: week_stats.delta >= 0 ? 'var(--green)' : '#f87171', fontWeight: 600 }}>
            {week_stats.delta >= 0 ? '↑' : '↓'} {week_stats.delta !== 0 ? `+${Math.abs(week_stats.delta).toLocaleString()}кг` : ''}
          </span>
          {week_stats.delta === 0
            ? <span style={{ color: 'var(--text)', fontWeight: 600 }}> {week_stats.tonnage.toLocaleString()}кг</span>
            : <span> vs прошлая</span>
          }
        </div>
      )}

    </div>
  )
}
