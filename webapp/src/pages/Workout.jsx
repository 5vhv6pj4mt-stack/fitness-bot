import { useEffect, useReducer, useRef, useState, useCallback, memo } from 'react'
import { api } from '../api'
import { haptic } from '../tg'

// ── Elapsed timer ────────────────────────────────────────────────────────────
function ElapsedTimer({ startedAt }) {
  const [elapsed, setElapsed] = useState(() => Math.floor((Date.now() - startedAt) / 1000))

  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000)
    return () => clearInterval(id)
  }, [startedAt])

  const h = Math.floor(elapsed / 3600)
  const m = Math.floor((elapsed % 3600) / 60)
  const s = elapsed % 60
  const fmt = h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${m}:${String(s).padStart(2, '0')}`

  return <span style={{ fontVariantNumeric: 'tabular-nums' }}>{fmt}</span>
}

// ── Rest seconds parser ───────────────────────────────────────────────────────
function parseRestSecs(rest) {
  if (!rest || rest === '—') return 0
  let s = 0
  const m = rest.match(/(\d+)м/)
  const sec = rest.match(/(\d+)с/)
  if (m) s += parseInt(m[1]) * 60
  if (sec) s += parseInt(sec[1])
  return s || 120
}

// ── Exercise info panel (image + brief technique) ─────────────────────────────
function ExerciseInfoPanel({ exercise }) {
  const [info, setInfo] = useState({ technique: null, image_url: null, loading: true })

  useEffect(() => {
    setInfo({ technique: null, image_url: null, loading: true })
    api.exerciseInfo(exercise)
      .then((d) => setInfo({ ...d, loading: false }))
      .catch(() => setInfo({ technique: null, image_url: null, loading: false }))
  }, [exercise])

  if (!info.loading && !info.technique && !info.image_url) return null

  return (
    <div style={{ marginBottom: 12 }}>
      {info.image_url && (
        <img
          src={info.image_url}
          alt={exercise}
          style={{
            width: '100%', height: 140, objectFit: 'cover',
            borderRadius: 10, marginBottom: 8, display: 'block',
          }}
        />
      )}
      <div style={{
        background: 'var(--bg)', borderRadius: 10, padding: '8px 12px',
        fontSize: 13, lineHeight: 1.55,
      }}>
        {info.loading ? (
          <span style={{ color: 'var(--hint)' }}>Загружаем технику...</span>
        ) : (
          <span style={{ color: 'var(--text)' }}>💡 {info.technique}</span>
        )}
      </div>
    </div>
  )
}

// ── Set input form ────────────────────────────────────────────────────────────
const RPE_PILLS = [6.5, 7, 7.5, 8, 8.5, 9, 9.5]

function Stepper({ value, onChange, step, min = 0, fmt = (v) => v }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, background: 'var(--bg)', borderRadius: 12, overflow: 'hidden' }}>
      <button
        onClick={() => { haptic('light'); onChange(Math.max(min, parseFloat((value - step).toFixed(1)))) }}
        style={{ width: 44, height: 52, fontSize: 22, color: 'var(--hint)', background: 'none', flexShrink: 0 }}
      >−</button>
      <div style={{ flex: 1, textAlign: 'center', fontSize: 22, fontWeight: 700, lineHeight: '52px' }}>
        {fmt(value)}
      </div>
      <button
        onClick={() => { haptic('light'); onChange(parseFloat((value + step).toFixed(1))) }}
        style={{ width: 44, height: 52, fontSize: 22, color: 'var(--hint)', background: 'none', flexShrink: 0 }}
      >+</button>
    </div>
  )
}

function SetForm({ exercise, setNum, totalSets, plannedWeight, repsRange, rpeRange, lastWeight, lastReps, lastRpe, suggestedWeight, restSecs, onLog }) {
  const initWeight = plannedWeight || suggestedWeight || 0
  const initReps = parseInt(String(repsRange).split('-')[0]) || 5

  const [weight, setWeight] = useState(initWeight)
  const [reps, setReps] = useState(initReps)
  const [rpe, setRpe] = useState('8')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [restRemaining, setRestRemaining] = useState(0)
  const restRef = useRef(null)

  useEffect(() => () => clearInterval(restRef.current), [])

  const fmtRest = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  const startRest = (secs) => {
    clearInterval(restRef.current)
    setRestRemaining(secs)
    restRef.current = setInterval(() => {
      setRestRemaining((r) => {
        if (r <= 1) { clearInterval(restRef.current); haptic('heavy'); return 0 }
        if (r === 11) haptic('light')
        return r - 1
      })
    }, 1000)
  }

  const submit = async () => {
    if (!weight || !reps) return
    setLoading(true)
    haptic('medium')
    await onLog({ weight, reps, rpe: parseFloat(rpe) || 8, notes: notes.trim() || null })
    setDone(true)
    setTimeout(() => setDone(false), 700)
    setReps(initReps)
    setRpe('8')
    setNotes('')
    setLoading(false)
    if (restSecs > 0) startRest(restSecs)
  }

  return (
    <div className="card">
      <div className="ex-title">{exercise}</div>
      <div className="ex-meta">Подход {setNum}/{totalSets} · {repsRange} повт · RPE {rpeRange}</div>

      <ExerciseInfoPanel exercise={exercise} />

      {lastWeight != null && (
        <div style={{
          background: 'var(--bg)', borderRadius: 10, padding: '8px 12px',
          marginBottom: 12, fontSize: 13,
        }}>
          <span style={{ color: 'var(--hint)' }}>Прошлый раз: </span>
          <span style={{ fontWeight: 600 }}>{lastWeight}кг × {lastReps}</span>
          {lastRpe && <span style={{ color: 'var(--hint)' }}> RPE {lastRpe}</span>}
          {suggestedWeight && suggestedWeight !== lastWeight && (
            <span style={{ marginLeft: 8, color: 'var(--green)', fontWeight: 600 }}>
              → {suggestedWeight}кг
            </span>
          )}
        </div>
      )}

      <div className="set-row-2col" style={{ marginBottom: 12 }}>
        <div>
          <div className="set-input-label">Вес, кг</div>
          <Stepper value={weight} onChange={setWeight} step={2.5} min={0} fmt={(v) => v > 0 ? v : '—'} />
        </div>
        <div>
          <div className="set-input-label">Повторы</div>
          <Stepper value={reps} onChange={setReps} step={1} min={1} />
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
        disabled={loading}
        onClick={submit}
      >
        {loading ? 'Сохраняю...' : done ? '✓ Записано!' : 'Записать подход ✓'}
      </button>

      {restRemaining > 0 && (
        <div style={{
          marginTop: 12, padding: '10px 14px',
          background: 'var(--bg)', borderRadius: 12,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 16 }}>⏱</span>
            <span style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: restRemaining <= 10 ? 'var(--orange)' : 'var(--text)' }}>
              Отдых: {fmtRest(restRemaining)}
            </span>
          </div>
          <button
            onClick={() => { clearInterval(restRef.current); setRestRemaining(0) }}
            style={{ fontSize: 13, color: 'var(--hint)', background: 'var(--bg3)', border: 'none', borderRadius: 8, padding: '4px 10px', cursor: 'pointer' }}
          >
            пропустить
          </button>
        </div>
      )}
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

// ── Plan view ────────────────────────────────────────────────────────────────
function ExerciseRow({ ex, weekType, dayType, onWeightSaved }) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(ex.weight || 0)
  const [saving, setSaving] = useState(false)

  const save = async () => {
    const w = parseFloat(val)
    if (!w || w <= 0) return
    setSaving(true)
    haptic('medium')
    try {
      await api.updateExerciseWeight(ex.exercise, weekType, dayType, w)
      onWeightSaved(ex.exercise, w)
      setEditing(false)
    } finally { setSaving(false) }
  }

  return (
    <div style={{ padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{ex.exercise}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, color: 'var(--hint)' }}>
          {ex.sets}×{ex.reps_range} · RPE {ex.rpe_range} · {ex.rest}
        </span>
        {editing ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input
              type="number"
              value={val}
              onChange={e => setVal(e.target.value)}
              step="2.5"
              min="0"
              style={{
                width: 70, padding: '4px 8px', borderRadius: 8, border: '1px solid var(--accent)',
                background: 'var(--bg)', color: 'var(--text)', fontSize: 14, fontWeight: 700,
              }}
              autoFocus
            />
            <span style={{ fontSize: 13, color: 'var(--hint)' }}>кг</span>
            <button
              onClick={save} disabled={saving}
              style={{ padding: '4px 10px', borderRadius: 8, background: 'var(--accent)', color: 'var(--accent-text)', fontSize: 13, fontWeight: 600 }}
            >{saving ? '...' : '✓'}</button>
            <button
              onClick={() => { setEditing(false); setVal(ex.weight || 0) }}
              style={{ padding: '4px 8px', borderRadius: 8, background: 'var(--bg3)', color: 'var(--hint)', fontSize: 13 }}
            >✕</button>
          </div>
        ) : (
          <button
            onClick={() => { haptic('light'); setEditing(true) }}
            style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 8,
              background: 'var(--bg2)', border: 'none', cursor: 'pointer' }}
          >
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>
              {ex.weight > 0 ? `${ex.weight}кг` : 'свой вес'}
            </span>
            <span style={{ fontSize: 11, color: 'var(--hint)' }}>✏️</span>
          </button>
        )}
        {ex.suggested_weight && ex.suggested_weight !== ex.weight && (
          <span style={{ fontSize: 12, color: 'var(--green)' }}>→ {ex.suggested_weight}кг</span>
        )}
      </div>
    </div>
  )
}

function PlanView({ plan, onStart }) {
  const [exercises, setExercises] = useState(plan.exercises)

  const handleWeightSaved = (exName, newWeight) => {
    setExercises(prev => prev.map(e => e.exercise === exName ? { ...e, weight: newWeight } : e))
  }

  return (
    <div className="page">
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 22, fontWeight: 700 }}>💪 Тренировка</div>
        <div style={{ fontSize: 14, color: 'var(--hint)', marginTop: 2 }}>
          {plan.day_label} · {plan.week_label} · Неделя {plan.week_num}
        </div>
      </div>

      <div className="card">
        {exercises.map((ex, i) => (
          <ExerciseRow
            key={i}
            ex={ex}
            weekType={plan.week_type}
            dayType={plan.day_type}
            onWeightSaved={handleWeightSaved}
          />
        ))}
      </div>

      <button className="btn-primary" style={{ marginTop: 4 }} onClick={onStart}>
        ▶️ Начать тренировку
      </button>
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
  finishResult: null,
  finishing: false,
  startedAt: null,
}

function reducer(state, action) {
  switch (action.type) {
    case 'PLAN_OK': {
      const aw = action.plan.active_workout
      if (aw) {
        const startedAt = aw.created_at
          ? new Date(aw.created_at.replace(' ', 'T') + 'Z').getTime()
          : Date.now()
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
          startedAt,
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
        startedAt: Date.now(),
      }
    case 'LOG':
      return { ...state, loggedSets: [...state.loggedSets, action.set] }
    case 'NEXT_SET':
      return { ...state, setIndex: state.setIndex + 1 }
    case 'NEXT_EX':
      return { ...state, exIndex: state.exIndex + 1, setIndex: 0 }
    case 'FINISHING':
      return { ...state, finishing: true }
    case 'FINISH_OK':
      return { ...state, finishing: false, finishResult: action.result }
    case 'FINISH_ERR':
      return { ...state, finishing: false, err: action.err }
    case 'BACK':
      return { ...state, finishResult: null, workoutId: null, loading: true, loggedSets: [], startedAt: null }
    case 'RELOAD_OK':
      return { ...state, plan: action.plan, loading: false }
    default:
      return state
  }
}

// ── Main Workout page ─────────────────────────────────────────────────────────
export default function Workout({ onGoProgress }) {
  const [state, dispatch] = useReducer(reducer, initial)
  const { plan, loading, err, workoutId, exercises, exIndex, setIndex, loggedSets, finishResult, finishing, startedAt } = state
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
    return <PlanView plan={plan} onStart={handleStart} />
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {startedAt && (
              <span style={{ fontSize: 13, color: 'var(--hint)', fontWeight: 600 }}>
                ⏱ <ElapsedTimer startedAt={startedAt} />
              </span>
            )}
            <span className="badge">{progress}%</span>
          </div>
        </div>
        <div className="prog-track">
          <div className="prog-fill" style={{ width: `${progress}%`, background: 'var(--accent)' }} />
        </div>
      </div>

      <SetForm
        key={exIndex}
        exercise={ex.exercise}
        setNum={setIndex + 1}
        totalSets={ex.sets}
        plannedWeight={ex.weight}
        repsRange={ex.reps_range}
        rpeRange={ex.rpe_range}
        lastWeight={ex.last_weight}
        lastReps={ex.last_reps}
        lastRpe={ex.last_rpe}
        suggestedWeight={ex.suggested_weight}
        restSecs={parseRestSecs(ex.rest)}
        onLog={handleLog}
      />

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
