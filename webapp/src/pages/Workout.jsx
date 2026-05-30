import { useEffect, useState, useRef } from 'react'
import { api } from '../api'
import { haptic } from '../tg'

// ── Rest timer ────────────────────────────────────────────────────────────────
function RestTimer({ onDone }) {
  const [selected, setSelected] = useState(null)
  const [remaining, setRemaining] = useState(0)
  const intervalRef = useRef(null)

  const OPTIONS = [
    { label: '1 мин', s: 60 },
    { label: '1:30', s: 90 },
    { label: '2 мин', s: 120 },
    { label: '2:30', s: 150 },
  ]

  const start = (s) => {
    clearInterval(intervalRef.current)
    setSelected(s)
    setRemaining(s)
    intervalRef.current = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          clearInterval(intervalRef.current)
          haptic('heavy')
          return 0
        }
        return r - 1
      })
    }, 1000)
  }

  useEffect(() => () => clearInterval(intervalRef.current), [])

  const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  return (
    <div className="card">
      {selected ? (
        <div className="rest-timer">
          <div className="rest-timer-count">{fmt(remaining)}</div>
          <div className="rest-timer-label">
            {remaining === 0 ? '⚡️ Время! Начинай подход' : 'Отдыхай...'}
          </div>
        </div>
      ) : (
        <div className="section-title" style={{ marginBottom: 12 }}>Выбери время отдыха</div>
      )}
      <div className="timer-btns">
        {OPTIONS.map((o) => (
          <button
            key={o.s}
            className={`timer-btn${selected === o.s ? ' active' : ''}`}
            onClick={() => { haptic('light'); start(o.s) }}
          >
            {o.label}
          </button>
        ))}
      </div>
      <button
        className="btn-primary"
        style={{ marginTop: 12 }}
        onClick={() => { haptic('medium'); onDone() }}
      >
        Следующий подход →
      </button>
    </div>
  )
}

// ── Set input form ────────────────────────────────────────────────────────────
function SetForm({ exercise, setNum, totalSets, plannedWeight, repsRange, rpeRange, onLog }) {
  const [weight, setWeight] = useState(String(plannedWeight || ''))
  const [reps, setReps] = useState('')
  const [rpe, setRpe] = useState('')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    const w = parseFloat(weight)
    const r = parseInt(reps)
    const rpeVal = parseFloat(rpe) || 8
    if (!w || !r) return
    setLoading(true)
    haptic('medium')
    await onLog({ weight: w, reps: r, rpe: rpeVal, notes: notes.trim() || null })
    setWeight(String(w))
    setReps('')
    setRpe('')
    setNotes('')
    setLoading(false)
  }

  return (
    <div className="card">
      <div className="ex-title">{exercise}</div>
      <div className="ex-meta">
        Подход {setNum}/{totalSets} · {repsRange} повт · RPE {rpeRange}
      </div>

      <div className="set-row">
        <div>
          <div className="set-input-label">Вес, кг</div>
          <input
            className="set-input"
            type="number"
            inputMode="decimal"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            placeholder={plannedWeight || '0'}
          />
        </div>
        <div>
          <div className="set-input-label">Повторы</div>
          <input
            className="set-input"
            type="number"
            inputMode="numeric"
            value={reps}
            onChange={(e) => setReps(e.target.value)}
            placeholder="—"
          />
        </div>
        <div>
          <div className="set-input-label">RPE</div>
          <input
            className="set-input"
            type="number"
            inputMode="decimal"
            value={rpe}
            onChange={(e) => setRpe(e.target.value)}
            placeholder="8"
          />
        </div>
      </div>

      <textarea
        className="notes-input"
        rows={1}
        placeholder="Заметка (с лямками, тяжело...)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        style={{ marginBottom: 12 }}
      />

      <button
        className="btn-primary"
        disabled={loading || !weight || !reps}
        onClick={submit}
      >
        {loading ? 'Сохраняю...' : 'Записать подход ✓'}
      </button>
    </div>
  )
}

// ── Finish screen ─────────────────────────────────────────────────────────────
function FinishScreen({ result, onBack }) {
  return (
    <div className="page">
      <div className="card" style={{ textAlign: 'center', padding: '32px 16px' }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>🏁</div>
        <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 24 }}>Тренировка завершена!</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 24 }}>
          <div>
            <div className="finish-stat">{result.tonnage}</div>
            <div className="finish-stat-label">кг тоннаж</div>
          </div>
          <div>
            <div className="finish-stat">{result.avg_rpe}</div>
            <div className="finish-stat-label">средний RPE</div>
          </div>
          <div>
            <div className="finish-stat">{result.sets_count}</div>
            <div className="finish-stat-label">подходов</div>
          </div>
        </div>
        <button className="btn-primary" onClick={onBack}>Отлично! 💪</button>
      </div>
    </div>
  )
}

// ── Main Workout page ─────────────────────────────────────────────────────────
export default function Workout() {
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  // active workout state
  const [workoutId, setWorkoutId] = useState(null)
  const [exercises, setExercises] = useState([])
  const [exIndex, setExIndex] = useState(0)
  const [setIndex, setSetIndex] = useState(0)
  const [loggedSets, setLoggedSets] = useState([])
  const [showRest, setShowRest] = useState(false)
  const [finishResult, setFinishResult] = useState(null)
  const [finishing, setFinishing] = useState(false)

  useEffect(() => {
    api.workoutPlan()
      .then(setPlan)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [])

  const handleStart = async () => {
    haptic('medium')
    const res = await api.startWorkout()
    setWorkoutId(res.workout_id)
    setExercises(res.exercises)
    setExIndex(0)
    setSetIndex(0)
    setLoggedSets([])
    setShowRest(false)
  }

  const handleLog = async ({ weight, reps, rpe, notes }) => {
    const ex = exercises[exIndex]
    await api.logSet({
      workout_id: workoutId,
      exercise: ex.exercise,
      set_number: setIndex + 1,
      planned_weight: ex.weight,
      actual_weight: weight,
      reps,
      rpe,
      notes,
    })

    const newSet = { exercise: ex.exercise, actual_weight: weight, reps, rpe }
    const newLogged = [...loggedSets, newSet]
    setLoggedSets(newLogged)

    const nextSet = setIndex + 1
    if (nextSet >= ex.sets) {
      const nextEx = exIndex + 1
      if (nextEx >= exercises.length) {
        await doFinish(newLogged)
        return
      }
      setExIndex(nextEx)
      setSetIndex(0)
    } else {
      setSetIndex(nextSet)
      setShowRest(true)
      return
    }
    setShowRest(false)
  }

  const doFinish = async (sets = loggedSets) => {
    setFinishing(true)
    haptic('heavy')
    const res = await api.finishWorkout({
      workout_id: workoutId,
      sets,
      day_type: plan.day_type,
      week_type: plan.week_type,
    })
    setFinishResult(res)
    setFinishing(false)
  }

  if (loading) return <div className="spinner">Загружаем план...</div>
  if (err) return <div className="spinner" style={{ color: '#f87171' }}>{err}</div>

  if (finishResult) {
    return <FinishScreen result={finishResult} onBack={() => {
      setFinishResult(null)
      setWorkoutId(null)
      setLoading(true)
      api.workoutPlan().then(setPlan).finally(() => setLoading(false))
    }} />
  }

  // Plan view (not started)
  if (!workoutId) {
    return (
      <div className="page">
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 22, fontWeight: 700 }}>💪 Тренировка</div>
          <div style={{ fontSize: 14, color: 'var(--hint)', marginTop: 2 }}>
            {plan.day_label} · {plan.week_label} · Неделя {plan.week_num}
          </div>
        </div>

        <div className="card">
          {plan.exercises.map((ex, i) => (
            <div key={i} style={{
              padding: '10px 0',
              borderBottom: i < plan.exercises.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none',
            }}>
              <div style={{ fontWeight: 600, marginBottom: 2 }}>
                {i + 1}. {ex.exercise}
              </div>
              <div style={{ fontSize: 13, color: 'var(--hint)' }}>
                {ex.sets}×{ex.reps_range} @{' '}
                {ex.weight > 0 ? `${ex.weight}кг` : 'свой вес'} · RPE {ex.rpe_range} · {ex.rest}
              </div>
            </div>
          ))}
        </div>

        <button
          className="btn-primary"
          style={{ marginTop: 4 }}
          onClick={handleStart}
        >
          ▶️ Начать тренировку
        </button>
      </div>
    )
  }

  // Active workout
  const ex = exercises[exIndex]
  const progress = Math.round(((exIndex * ex?.sets + setIndex) / exercises.reduce((s, e) => s + e.sets, 0)) * 100)

  return (
    <div className="page">
      {/* Progress header */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <div style={{ fontSize: 16, fontWeight: 700 }}>{plan.day_label}</div>
          <span className="badge">{progress}%</span>
        </div>
        <div className="prog-track">
          <div className="prog-fill" style={{ width: `${progress}%`, background: 'var(--accent)' }} />
        </div>
      </div>

      {showRest ? (
        <RestTimer onDone={() => setShowRest(false)} />
      ) : (
        <SetForm
          exercise={ex.exercise}
          setNum={setIndex + 1}
          totalSets={ex.sets}
          plannedWeight={ex.weight}
          repsRange={ex.reps_range}
          rpeRange={ex.rpe_range}
          onLog={handleLog}
        />
      )}

      {/* Logged sets */}
      {loggedSets.length > 0 && (
        <div className="card">
          <div className="section-title">Записано</div>
          {loggedSets.slice(-8).map((s, i) => (
            <div key={i} className="set-history-item">
              <span style={{ color: 'var(--hint)' }}>{s.exercise}</span>
              <span>{s.actual_weight}кг × {s.reps} · RPE {s.rpe}</span>
            </div>
          ))}
        </div>
      )}

      {/* Finish button */}
      <button
        className="btn-secondary"
        style={{ width: '100%', marginTop: 4 }}
        disabled={finishing}
        onClick={() => doFinish()}
      >
        {finishing ? 'Завершаем...' : '🏁 Завершить тренировку'}
      </button>
    </div>
  )
}
