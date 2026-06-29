import { useEffect, useState, useCallback } from 'react'
import { api, friendlyError } from '../api'
import { haptic } from '../tg'

const STATUS_ICON = { done: '✅', current: '▶️', upcoming: '🔒' }

// ── Edit workout bottom sheet ──────────────────────────────────────────────

function EditSetRow({ s, onSave, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [w, setW] = useState(String(s.actual_weight))
  const [r, setR] = useState(String(s.reps))
  const [rpe, setRpe] = useState(String(s.rpe))
  const [saving, setSaving] = useState(false)

  const fmtW = (v) => parseFloat(v) === parseInt(v) ? parseInt(v) : parseFloat(v)

  const save = async () => {
    const weight = parseFloat(w)
    const reps = parseInt(r)
    const rpeVal = parseFloat(rpe)
    if (!weight || !reps || isNaN(rpeVal)) return
    setSaving(true)
    try {
      await api.updateSet(s.id, { actual_weight: weight, reps, rpe: rpeVal, notes: s.notes })
      haptic('medium')
      onSave({ ...s, actual_weight: weight, reps, rpe: rpeVal })
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const del = async () => {
    if (!confirm(`Удалить подход ${fmtW(s.actual_weight)}кг × ${s.reps}?`)) return
    setSaving(true)
    try {
      await api.deleteSet(s.id)
      haptic('medium')
      onDelete(s.id)
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <div style={{ padding: '8px 0', borderBottom: '1px solid var(--sep)' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: 'var(--hint)', marginBottom: 3 }}>Вес (кг)</div>
            <input
              type="number" value={w} onChange={e => setW(e.target.value)} step="0.5"
              style={{ width: '100%', padding: '6px 8px', borderRadius: 8, border: '1px solid var(--sep)',
                background: 'var(--bg3)', color: 'var(--text)', fontSize: 14 }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: 'var(--hint)', marginBottom: 3 }}>Повт.</div>
            <input
              type="number" value={r} onChange={e => setR(e.target.value)}
              style={{ width: '100%', padding: '6px 8px', borderRadius: 8, border: '1px solid var(--sep)',
                background: 'var(--bg3)', color: 'var(--text)', fontSize: 14 }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: 'var(--hint)', marginBottom: 3 }}>RPE</div>
            <input
              type="number" value={rpe} onChange={e => setRpe(e.target.value)} step="0.5" min="1" max="10"
              style={{ width: '100%', padding: '6px 8px', borderRadius: 8, border: '1px solid var(--sep)',
                background: 'var(--bg3)', color: 'var(--text)', fontSize: 14 }}
            />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={save} disabled={saving}
            style={{ flex: 2, padding: '7px', borderRadius: 8, border: 'none',
              background: 'var(--blue)', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
            {saving ? '...' : '✅ Сохранить'}
          </button>
          <button onClick={() => setEditing(false)}
            style={{ flex: 1, padding: '7px', borderRadius: 8, border: '1px solid var(--sep)',
              background: 'transparent', color: 'var(--hint)', fontSize: 13, cursor: 'pointer' }}>
            Отмена
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0',
      borderBottom: '1px solid var(--sep)' }}>
      <div style={{ fontSize: 13, color: 'var(--hint)', width: 24, flexShrink: 0 }}>
        {s.set_number}
      </div>
      <div style={{ flex: 1, fontSize: 14 }}>
        {fmtW(s.actual_weight)}кг × {s.reps} <span style={{ color: 'var(--hint)', fontSize: 12 }}>RPE {s.rpe}</span>
      </div>
      <button onClick={() => { haptic('light'); setEditing(true) }}
        style={{ padding: '4px 10px', borderRadius: 7, border: '1px solid var(--sep)',
          background: 'transparent', color: 'var(--blue)', fontSize: 12, cursor: 'pointer' }}>
        ✏️
      </button>
      <button onClick={del} disabled={saving}
        style={{ padding: '4px 10px', borderRadius: 7, border: '1px solid var(--sep)',
          background: 'transparent', color: '#f87171', fontSize: 12, cursor: 'pointer' }}>
        🗑
      </button>
    </div>
  )
}

function EditWorkoutSheet({ workoutId, dayLabel, onClose }) {
  const [sets, setSets] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.workoutSets(workoutId)
      .then(setSets)
      .catch(e => setErr(friendlyError(e)))
      .finally(() => setLoading(false))
  }, [workoutId])

  const handleSave = useCallback((updated) => {
    setSets(prev => prev.map(s => s.id === updated.id ? updated : s))
  }, [])

  const handleDelete = useCallback((id) => {
    setSets(prev => prev.filter(s => s.id !== id))
  }, [])

  // Group sets by exercise
  const grouped = sets ? Object.entries(
    sets.reduce((acc, s) => {
      ;(acc[s.exercise] = acc[s.exercise] || []).push(s)
      return acc
    }, {})
  ) : []

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 100,
      }} />
      {/* Sheet */}
      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 101,
        background: 'var(--bg)', borderRadius: '18px 18px 0 0',
        maxHeight: '80vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 -4px 24px rgba(0,0,0,0.3)',
      }}>
        {/* Handle */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0 0' }}>
          <div style={{ width: 36, height: 4, borderRadius: 2, background: 'var(--sep)' }} />
        </div>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 16px 12px' }}>
          <div style={{ fontSize: 16, fontWeight: 700 }}>✏️ {dayLabel}</div>
          <button onClick={onClose} style={{ background: 'none', border: 'none',
            fontSize: 20, color: 'var(--hint)', cursor: 'pointer', padding: '0 4px' }}>×</button>
        </div>
        {/* Content */}
        <div style={{ overflow: 'auto', padding: '0 16px 24px', flex: 1 }}>
          {loading && <div style={{ color: 'var(--hint)', textAlign: 'center', padding: 24 }}>Загружаем...</div>}
          {err && <div style={{ color: '#f87171', textAlign: 'center', padding: 24 }}>{err}</div>}
          {sets && sets.length === 0 && (
            <div style={{ color: 'var(--hint)', textAlign: 'center', padding: 24 }}>Нет подходов</div>
          )}
          {grouped.map(([exercise, exSets]) => (
            <div key={exercise} style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--blue)', marginBottom: 4 }}>
                {exercise}
              </div>
              {exSets.map(s => (
                <EditSetRow key={s.id} s={s} onSave={handleSave} onDelete={handleDelete} />
              ))}
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

// ── Day item ───────────────────────────────────────────────────────────────

function DayItem({ day, defaultOpen, onStartWorkout }) {
  const [open, setOpen] = useState(defaultOpen)
  const [editWorkoutId, setEditWorkoutId] = useState(null)

  const toggle = () => {
    haptic('light')
    setOpen((v) => !v)
  }

  return (
    <>
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
            {day.status === 'done' && day.workout?.id && (
              <button
                style={{
                  marginTop: 12, width: '100%', padding: '9px',
                  borderRadius: 10, border: '1px solid var(--sep)',
                  background: 'transparent', color: 'var(--blue)',
                  fontSize: 14, fontWeight: 500, cursor: 'pointer',
                }}
                onClick={(e) => { e.stopPropagation(); haptic('medium'); setEditWorkoutId(day.workout.id) }}
              >
                ✏️ Редактировать подходы
              </button>
            )}
          </div>
        )}
      </div>

      {editWorkoutId && (
        <EditWorkoutSheet
          workoutId={editWorkoutId}
          dayLabel={day.day_label}
          onClose={() => setEditWorkoutId(null)}
        />
      )}
    </>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────

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
