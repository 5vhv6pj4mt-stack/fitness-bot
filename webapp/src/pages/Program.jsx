import { useEffect, useState } from 'react'
import { api } from '../api'
import { haptic } from '../tg'

const STATUS_ICON = { done: '✅', current: '▶️', upcoming: '🔒' }

function DayItem({ day, defaultOpen, onStartWorkout }) {
  const [open, setOpen] = useState(defaultOpen)

  const toggle = () => {
    haptic('light')
    setOpen((v) => !v)
  }

  return (
    <div style={{
      background: 'var(--bg2)',
      borderRadius: 14,
      overflow: 'hidden',
      cursor: 'pointer',
    }}>
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px' }}
        onClick={toggle}
      >
        <div style={{
          width: 36, height: 36, borderRadius: '50%', display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0,
          background: day.status === 'done'
            ? 'rgba(48,209,88,0.12)'
            : day.status === 'current'
              ? 'rgba(10,132,255,0.12)'
              : 'var(--bg3)',
        }}>
          {STATUS_ICON[day.status]}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{day.day_label}</div>
          <div style={{ fontSize: 12, color: day.status === 'current' ? 'var(--blue)' : 'var(--hint)', marginTop: 2 }}>
            {day.status === 'done' && day.workout
              ? `Выполнено · ${day.workout.date} · ${day.workout.tonnage.toLocaleString()} кг тоннаж`
              : day.status === 'done'
                ? 'Выполнено'
                : day.status === 'current'
                  ? 'Следующая тренировка'
                  : 'Запланировано'}
          </div>
        </div>
        <div style={{
          fontSize: 12, color: 'var(--hint)',
          transform: open ? 'rotate(90deg)' : 'none',
          transition: 'transform 0.2s',
        }}>›</div>
      </div>

      {open && (
        <div style={{ borderTop: '1px solid var(--sep)', padding: '0 16px 12px' }}>
          {day.exercises.map((ex, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 0',
              borderBottom: i < day.exercises.length - 1 ? '1px solid var(--sep)' : 'none',
            }}>
              <span style={{ fontSize: 12, color: 'var(--hint)', width: 18, flexShrink: 0 }}>{i + 1}</span>
              <span style={{ flex: 1, fontSize: 14 }}>{ex.name}</span>
              <span style={{ fontSize: 12, color: 'var(--hint)' }}>
                {ex.sets}×{ex.reps}{ex.weight ? ` · ${ex.weight}кг` : ''}
              </span>
            </div>
          ))}
          {day.status === 'current' && (
            <button
              className="btn-primary"
              style={{ marginTop: 12, width: '100%' }}
              onClick={(e) => { e.stopPropagation(); haptic('medium'); onStartWorkout() }}
            >
              💪 Начать тренировку
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default function Program({ onGoWorkout }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.programData()
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="spinner">Загружаем программу...</div>
  if (err) return <div className="spinner" style={{ color: '#f87171' }}>{err}</div>
  if (!data) return null

  const progress = data.total_days > 0 ? (data.completed_days / data.total_days) * 100 : 0

  return (
    <div className="page">
      <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 16 }}>📋 Программа</div>

      {/* Cycle card */}
      <div className="card" style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{data.week_type_label} неделя</div>
            <div style={{ fontSize: 13, color: 'var(--hint)', marginTop: 3 }}>
              Неделя {data.week_in_cycle} из {data.total_weeks_in_cycle} · Общая #{data.week_number}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {Array.from({ length: data.total_weeks_in_cycle }).map((_, i) => (
              <div key={i} style={{
                width: 10, height: 10, borderRadius: '50%',
                background: i < data.week_in_cycle - 1
                  ? 'var(--blue)'
                  : i === data.week_in_cycle - 1
                    ? 'var(--orange)'
                    : 'var(--bg3)',
              }} />
            ))}
          </div>
        </div>
        <div style={{ background: 'var(--bg3)', borderRadius: 4, height: 4, overflow: 'hidden', marginBottom: 8 }}>
          <div style={{
            height: '100%',
            width: `${progress}%`,
            background: 'linear-gradient(90deg, var(--blue), var(--purple))',
            borderRadius: 4,
            transition: 'width 0.5s',
          }} />
        </div>
        <div style={{ fontSize: 12, color: 'var(--hint)' }}>
          {data.completed_days} из {data.total_days} тренировок выполнено
        </div>
      </div>

      {/* Days list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 10 }}>
        {data.days.map((day) => (
          <DayItem
            key={day.index}
            day={day}
            defaultOpen={day.status === 'current'}
            onStartWorkout={onGoWorkout}
          />
        ))}
      </div>

      {/* Next cycle preview */}
      {data.next_week && (
        <div style={{
          background: 'rgba(191,90,242,0.08)',
          border: '1px solid rgba(191,90,242,0.2)',
          borderRadius: 13,
          padding: '13px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Следующий цикл</div>
            <div style={{ fontSize: 12, color: 'var(--hint)', marginTop: 2 }}>
              {data.next_week.week_type_label} — {data.next_week.day_label}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--purple)' }}>
              {data.next_week.week_type_label}
            </div>
            {data.days_until_next_cycle > 0 && (
              <div style={{ fontSize: 11, color: 'var(--hint)', marginTop: 2 }}>
                через {data.days_until_next_cycle} дн.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
