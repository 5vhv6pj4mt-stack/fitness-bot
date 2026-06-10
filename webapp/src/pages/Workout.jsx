import { useEffect, useReducer, useRef, useState, useCallback, memo } from 'react'
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
const RPE_PILLS = [6.5, 7, 7.5, 8, 8.5, 9, 9.5]

function SetForm({ exercise, setNum, totalSets, plannedWeight, repsRange, rpeRange, onLog }) {
  const [weight, setWeight] = useState(String(plannedWeight || ''))
  const [reps, setReps] = useState('')
  const [rpe, setRpe] = useState('8')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  const submit = async () => {
    const w = parseFloat(weight)
    const r = parseInt(reps)
    const rpeVal = parseFloat(rpe) || 8
    if (!w || !r) return
    setLoading(true)
    haptic('medium')
    await onLog({ weight: w, reps: r, rpe: rpeVal, notes: notes.trim() || null })
    setDone(true)
    setTimeout(() => setDone(false), 700)
    setWeight(String(w))
    setReps('')
    setRpe('8')
    setNotes('')
    setLoading(false)
  }

  return (
    <div className="card">
      <div className="ex-title">{exercise}</div>
      <div className="ex-meta">
        Подход {setNum}/{totalSets} · {repsRange} повт · RPE {rpeRange}
      </div>

      <div className="set-row-2col">
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
      </div>

      <div style={{ marginBottom: 12 }}>
        <div className="set-input-label" style={{ marginBottom: 6 }}>RPE — усилие</div>
        <div className="rpe-pills">
          {RPE_PILLS.map((v) => (
            <button
              key={v}
              className={`rpe-pill${String(rpe) === String(v) ? ' active' : ''}`}
              onClick={() => { haptic('light'); setRpe(String(v)) }}
            >
              {v}
            </button>
          ))}
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
        className={`btn-primary${done ? ' btn-success' : ''}`}
        disabled={loading || !weight || !reps}
        onClick={submit}
      >
        {loading ? 'Сохраняю...' : done ? '✓ Записано!' : 'Записать подход ✓'}
      </button>
    </div>
  )
}

// ── Finish screen ─────────────────────────────────────────────────────────────
function FinishScreen({ result, onBack, onGoProgress }) {
  const [analysis, setAnalysis] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(!!result.workout_id)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!result.workout_id) return
    const poll = async () => {
      try {
        const res = await api.workoutAnalysis(result.workout_id)
        if (res.ready) {
          clearInterval(intervalRef.current)
          setAnalysis(res.analysis)
          setAnalysisLoading(false)
        }
      } catch {
        clearInterval(intervalRef.current)
        setAnalysisLoading(false)
      }
    }
    poll()
    intervalRef.current = setInterval(poll, 2500)
    return () => clearInterval(intervalRef.current)
  }, [result.workout_id])

  const fmtDuration = (mins) => {
    if (!mins) return '—'
    const h = Math.floor(mins / 60)
    const m = mins % 60
    return h > 0 ? `${h}ч ${m}м` : `${m}м`
  }

  return (
    <div className="page">
      <div className="card" style={{ textAlign: 'center', padding: '28px 16px', marginBottom: 12 }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>🏁</div>
        <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 20 }}>Тренировка завершена!</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 20 }}>
          {[
            { val: result.tonnage, label: 'кг тоннаж' },
            { val: fmtDuration(result.duration_minutes), label: 'время' },
            { val: result.sets_count, label: 'подходов' },
            { val: result.avg_rpe, label: 'средний RPE' },
          ].map(({ val, label }) => (
            <div key={label} style={{ background: 'var(--bg)', borderRadius: 12, padding: '14px 8px' }}>
              <div className="finish-stat">{val}</div>
              <div className="finish-stat-label">{label}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 12 }}>
        <div className="section-title" style={{ marginBottom: 10 }}>🤖 Анализ тренировки</div>
        {analysisLoading ? (
          <div style={{ color: 'var(--hint)', fontSize: 14, display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
            <span className="spinner-dots" />
            Тренер анализирует...
          </div>
        ) : analysis ? (
          <div style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-wrap', color: 'var(--text)' }}>
            {analysis}
          </div>
        ) : (
          <div style={{ color: 'var(--hint)', fontSize: 13 }}>Анализ недоступен</div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        <button className="btn-secondary" style={{ flex: 1 }} onClick={onBack}>
          На главную
        </button>
        <button className="btn-primary" style={{ flex: 1 }} onClick={onGoProgress}>
          Прогресс →
        </button>
      </div>
    </div>
  )
}

// ── Reducer ───────────────────────────────────────────────────────────────────
const initial = {
  plan: null,
  loading: true,
  err: null,
  workoutId: null,
  exercises: [],
  exIndex: 0,
  setIndex: 0,
  loggedSets: [],
  showRest: false,
  finishResult: null,
  finishing: false,
}

function reducer(state, action) {
  switch (action.type) {
    case 'PLAN_OK': {
      const aw = action.plan.active_workout
      if (aw) {
        return {
          ...state,
          plan: action.plan,
          loading: false,
          workoutId: aw.id,
          exercises: action.plan.exercises,
          exIndex: aw.ex_index ?? 0,
          setIndex: aw.set_index ?? 0,
          loggedSets: [],
          showRest: false,
        }
      }
      return { ...state, plan: action.plan, loading: false }
    }
    case 'PLAN_ERR':
      return { ...state, err: action.err, loading: false }
    case 'START':
      return {
        ...state,
        workoutId: action.workoutId,
        exercises: action.exercises,
        exIndex: 0, setIndex: 0,
        loggedSets: [], showRest: false,
      }
    case 'LOG':
      return { ...state, loggedSets: [...state.loggedSets, action.set] }
    case 'NEXT_SET':
      return { ...state, setIndex: state.setIndex + 1, showRest: true }
    case 'NEXT_EX':
      return { ...state, exIndex: state.exIndex + 1, setIndex: 0, showRest: false }
    case 'REST_DONE':
      return { ...state, showRest: false }
    case 'FINISHING':
      return { ...state, finishing: true }
    case 'FINISH_OK':
      return { ...state, finishing: false, finishResult: action.result }
    case 'FINISH_ERR':
      return { ...state, finishing: false, err: action.err }
    case 'BACK':
      return { ...state, finishResult: null, workoutId: null, loading: true, loggedSets: [] }
    case 'RELOAD_OK':
      return { ...state, plan: action.plan, loading: false }
    default:
      return state
  }
}

// ── Main Workout page ─────────────────────────────────────────────────────────
export default function Workout({ onGoProgress }) {
  const [state, dispatch] = useReducer(reducer, initial)
  const { plan, loading, err, workoutId, exercises, exIndex, setIndex, loggedSets, showRest, finishResult, finishing } = state
  const finishingRef = useRef(false)

  useEffect(() => {
    api.workoutPlan()
      .then((plan) => dispatch({ type: 'PLAN_OK', plan }))
      .catch((e) => dispatch({ type: 'PLAN_ERR', err: e.message }))
  }, [])

  const handleStart = async () => {
    haptic('medium')
    const res = await api.startWorkout()
    dispatch({ type: 'START', workoutId: res.workout_id, exercises: res.exercises })
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

    const newSet = { id: `${ex.exercise}-${setIndex}-${Date.now()}`, exercise: ex.exercise, actual_weight: weight, reps, rpe }
    dispatch({ type: 'LOG', set: newSet })
    const newLogged = [...loggedSets, newSet]

    const nextSet = setIndex + 1
    if (nextSet >= ex.sets) {
      const nextEx = exIndex + 1
      if (nextEx >= exercises.length) {
        await doFinish(newLogged)
        return
      }
      dispatch({ type: 'NEXT_EX' })
    } else {
      dispatch({ type: 'NEXT_SET' })
    }
  }

  const doFinish = useCallback(async (sets = loggedSets) => {
    if (finishingRef.current) return
    finishingRef.current = true
    dispatch({ type: 'FINISHING' })
    haptic('heavy')
    try {
      const res = await api.finishWorkout({
        workout_id: workoutId,
        sets,
        day_type: plan.day_type,
        week_type: plan.week_type,
      })
      dispatch({ type: 'FINISH_OK', result: res })
    } catch (e) {
      dispatch({ type: 'FINISH_ERR', err: e.message })
    } finally {
      finishingRef.current = false
    }
  }, [loggedSets, workoutId, plan])

  if (loading) return <div className="spinner">Загружаем план...</div>
  if (err) return <div className="spinner" style={{ color: '#f87171' }}>{err}</div>

  if (finishResult) {
    return <FinishScreen
      result={finishResult}
      onGoProgress={onGoProgress}
      onBack={() => {
        dispatch({ type: 'BACK' })
        api.workoutPlan()
          .then((plan) => dispatch({ type: 'RELOAD_OK', plan }))
          .catch((e) => dispatch({ type: 'PLAN_ERR', err: e.message }))
      }}
    />
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
  const totalSets = exercises.reduce((s, e) => s + e.sets, 0)
  const doneSets = exercises.slice(0, exIndex).reduce((s, e) => s + e.sets, 0) + setIndex
  const progress = Math.round((doneSets / totalSets) * 100)

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
        <RestTimer onDone={() => dispatch({ type: 'REST_DONE' })} />
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
            <div key={s.id} className="set-history-item">
              <div>
                <span className="set-history-num">#{i + 1}</span>
                <span className="set-history-exercise">{s.exercise}</span>
              </div>
              <div className="set-history-data">
                <span>{s.actual_weight}кг × {s.reps}</span>
                <span className="set-history-rpe">RPE {s.rpe}</span>
              </div>
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
