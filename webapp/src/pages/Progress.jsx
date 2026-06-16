import { useEffect, useState, memo } from 'react'
import { AreaChart, Area, BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api, friendlyError } from '../api'
import ProgressBar from '../components/ProgressBar'
import ExerciseProgressChart from '../components/ExerciseProgressChart'
import { useToast } from '../useToast.jsx'

const TAB_LABELS = ['Неделя', 'Тоннаж', 'Питание', 'Веса', 'Тело', 'Мышцы']

function SetRow({ s, onDeleted, onUpdated }) {
  const [editing, setEditing] = useState(false)
  const [weight, setWeight] = useState(String(s.actual_weight))
  const [reps, setReps] = useState(String(s.reps))
  const [rpe, setRpe] = useState(String(s.rpe || 8))
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const { show: showToast, ToastEl } = useToast()

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateSet(s.id, {
        actual_weight: parseFloat(weight) || 0,
        reps: parseInt(reps) || 1,
        rpe: parseFloat(rpe) || 8,
        notes: s.notes || null,
      })
      onUpdated({ ...s, actual_weight: parseFloat(weight) || 0, reps: parseInt(reps) || 1, rpe: parseFloat(rpe) || 8 })
      setEditing(false)
      showToast('Изменения сохранены ✓')
    } catch (e) {
      showToast(friendlyError(e), true)
    } finally { setSaving(false) }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await api.deleteSet(s.id)
      onDeleted(s.id)
    } catch (e) {
      showToast(friendlyError(e), true)
      setDeleting(false)
    }
  }

  if (editing) {
    return (
      <div style={{ padding: '8px 0', borderBottom: '1px solid var(--sep)' }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          {[
            { label: 'Вес кг', val: weight, set: setWeight, type: 'decimal' },
            { label: 'Повторы', val: reps, set: setReps, type: 'numeric' },
            { label: 'RPE', val: rpe, set: setRpe, type: 'decimal' },
          ].map(({ label, val, set, type }) => (
            <div key={label} style={{ flex: 1 }}>
              <div style={{ fontSize: 10, color: 'var(--hint)', marginBottom: 3 }}>{label}</div>
              <input
                type="number" inputMode={type} value={val}
                onChange={e => set(e.target.value)}
                style={{
                  width: '100%', background: 'var(--bg)', color: 'var(--text)',
                  border: '1.5px solid var(--blue)', borderRadius: 8,
                  padding: '7px 8px', fontSize: 15, fontWeight: 600,
                  textAlign: 'center', boxSizing: 'border-box',
                }}
              />
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => setEditing(false)}
            style={{ flex: 1, background: 'var(--bg3)', border: 'none', borderRadius: 8, padding: '8px', fontSize: 13, color: 'var(--hint)', cursor: 'pointer' }}>
            Отмена
          </button>
          <button onClick={handleSave} disabled={saving}
            style={{ flex: 2, background: 'var(--blue)', border: 'none', borderRadius: 8, padding: '8px', fontSize: 13, fontWeight: 700, color: '#fff', cursor: 'pointer' }}>
            {saving ? 'Сохраняю...' : 'Сохранить'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 0' }}>
      <div onClick={() => setEditing(true)} style={{ flex: 1, cursor: 'pointer' }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>
          {s.actual_weight > 0 ? `${s.actual_weight}кг × ${s.reps}` : `${s.reps} повт.`}
        </span>
        {s.rpe ? <span style={{ color: 'var(--hint)', fontSize: 12, marginLeft: 8 }}>RPE {s.rpe}</span> : null}
        <span style={{ fontSize: 11, color: 'var(--blue)', marginLeft: 8 }}>✎</span>
      </div>
      <button onClick={handleDelete} disabled={deleting}
        style={{ background: 'rgba(255,69,58,.12)', border: 'none', borderRadius: 8, padding: '4px 10px', color: 'var(--red)', fontSize: 13, cursor: 'pointer', flexShrink: 0 }}>
        {deleting ? '...' : '✕'}
      </button>
      {ToastEl}
    </div>
  )
}

function WorkoutSheet({ workout, onClose, onSetDeleted }) {
  const [sets, setSets] = useState(workout.sets || [])

  const handleDeleted = (setId) => {
    setSets(prev => prev.filter(s => s.id !== setId))
    onSetDeleted()
  }

  const handleUpdated = (updated) => {
    setSets(prev => prev.map(s => s.id === updated.id ? updated : s))
    onSetDeleted() // обновляем тоннаж в списке
  }

  const grouped = sets.reduce((acc, s) => {
    if (!acc[s.exercise]) acc[s.exercise] = []
    acc[s.exercise].push(s)
    return acc
  }, {})

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 200 }} />
      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 201,
        background: 'var(--bg2)', borderRadius: '20px 20px 0 0',
        padding: '16px 0 32px', maxHeight: '75vh', overflowY: 'auto',
      }}>
        <div style={{ width: 36, height: 4, background: 'var(--bg4)', borderRadius: 2, margin: '0 auto 12px' }} />
        <div style={{ padding: '0 16px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>{workout.day_type}</div>
            <div style={{ fontSize: 12, color: 'var(--hint)' }}>{workout.date} · {workout.tonnage.toLocaleString()} кг тоннаж</div>
          </div>
          <button onClick={onClose} style={{ background: 'var(--bg3)', border: 'none', borderRadius: 10, padding: '6px 12px', color: 'var(--hint)', cursor: 'pointer' }}>✕</button>
        </div>
        {sets.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--hint)', padding: '20px 0' }}>Все подходы удалены</div>
        ) : Object.entries(grouped).map(([exercise, exSets]) => (
          <div key={exercise} style={{ padding: '4px 16px 4px', borderTop: '1px solid var(--sep)' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--hint)', marginBottom: 2, paddingTop: 6 }}>{exercise}</div>
            {exSets.map((s) => (
              <SetRow key={s.id} s={s} onDeleted={handleDeleted} onUpdated={handleUpdated} />
            ))}
          </div>
        ))}
      </div>
    </>
  )
}

function WeekTab() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [recentWorkouts, setRecentWorkouts] = useState([])
  const [selectedWorkout, setSelectedWorkout] = useState(null)

  const loadRecent = () => api.recentWorkouts().then(r => setRecentWorkouts(r.workouts || [])).catch(() => {})

  useEffect(() => {
    api.weekReport()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
    loadRecent()
  }, [])

  const handleSetDeleted = () => { loadRecent() }

  if (loading) return <div style={{ color: 'var(--hint)', textAlign: 'center', padding: 32 }}>Загружаем...</div>
  if (!data) return <div style={{ color: '#f87171', textAlign: 'center', padding: 32 }}>Ошибка загрузки</div>

  const { workouts, workouts_count, tonnage_this_week, tonnage_prev_week, tonnage_delta,
    nutrition, goals, days_planned } = data
  const nutrPct = goals.calories > 0 ? Math.round(nutrition.avg_calories / goals.calories * 100) : 0
  const deltaSign = tonnage_delta > 0 ? '+' : ''
  const deltaColor = tonnage_delta > 0 ? 'var(--green)' : tonnage_delta < 0 ? '#f87171' : 'var(--hint)'

  const DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
  const today = new Date()
  const weekDayIdx = (today.getDay() + 6) % 7
  const weekStart = new Date(today)
  weekStart.setDate(today.getDate() - weekDayIdx)
  weekStart.setHours(0, 0, 0, 0)

  return (
    <>
      {/* Тренировки */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>💪 Тренировки</div>
          <div style={{ fontSize: 13, color: 'var(--hint)' }}>{workouts_count} / {days_planned} запл.</div>
        </div>

        {/* Дни недели */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
          {DAY_NAMES.map((d, i) => {
            const done = workouts.some(w => {
              const wd = new Date(w.date)
              return (wd.getDay() + 6) % 7 === i
            })
            const isFuture = i > weekDayIdx
            return (
              <div key={i} style={{
                flex: 1, textAlign: 'center', padding: '6px 0', borderRadius: 8, fontSize: 11,
                background: done ? 'var(--green)' : isFuture ? 'var(--bg)' : 'var(--bg3)',
                color: done ? '#fff' : isFuture ? 'var(--bg3)' : 'var(--hint)',
                fontWeight: done ? 700 : 400,
              }}>{d}</div>
            )
          })}
        </div>

        {recentWorkouts.length > 0 ? recentWorkouts.map((w, i) => {
          const isThisWeek = new Date(w.date) >= weekStart
          return (
            <div key={w.id}
              onClick={() => setSelectedWorkout(w)}
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '8px 0', borderBottom: i < recentWorkouts.length - 1 ? '1px solid var(--sep)' : 'none',
                cursor: 'pointer' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{w.day_type}</span>
                  {isThisWeek && (
                    <span style={{ fontSize: 10, background: 'var(--green)', color: '#fff', borderRadius: 4, padding: '1px 5px', fontWeight: 700 }}>
                      эта нед.
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: 'var(--hint)' }}>{w.date} · {w.week_type}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{w.tonnage.toLocaleString()} кг</div>
                  {w.avg_rpe > 0 && <div style={{ fontSize: 11, color: 'var(--hint)' }}>RPE {w.avg_rpe}</div>}
                </div>
                <span style={{ color: 'var(--hint)', fontSize: 16 }}>›</span>
              </div>
            </div>
          )
        }) : (
          <div style={{ color: 'var(--hint)', fontSize: 13, textAlign: 'center', padding: '8px 0' }}>
            Тренировок ещё нет
          </div>
        )}
      </div>

      {selectedWorkout && (
        <WorkoutSheet
          workout={selectedWorkout}
          onClose={() => setSelectedWorkout(null)}
          onSetDeleted={handleSetDeleted}
        />
      )}

      {/* Тоннаж */}
      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 8 }}>⚡ Тоннаж недели</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{tonnage_this_week.toLocaleString()} кг</div>
          {tonnage_delta !== null && (
            <div style={{ fontSize: 14, color: deltaColor, fontWeight: 600 }}>
              {deltaSign}{tonnage_delta.toLocaleString()} кг vs прошлая
            </div>
          )}
        </div>
        {tonnage_prev_week > 0 && (
          <div style={{ fontSize: 12, color: 'var(--hint)', marginTop: 4 }}>
            Прошлая неделя: {tonnage_prev_week.toLocaleString()} кг
          </div>
        )}
      </div>

      {/* Питание */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>🍽 Питание (средн.)</div>
          <div style={{ fontSize: 12, color: 'var(--hint)' }}>{nutrition.days_tracked} дн. из 7</div>
        </div>
        {nutrition.days_tracked > 0 ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 13 }}>🔥 Калории</span>
              <span style={{ fontSize: 13, fontWeight: 600 }}>
                {nutrition.avg_calories} / {goals.calories}
                <span style={{ color: nutrPct >= 90 && nutrPct <= 110 ? 'var(--green)' : '#f59e0b',
                  marginLeft: 6, fontSize: 11 }}>{nutrPct}%</span>
              </span>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {[
                { label: 'Белок', val: nutrition.avg_protein, goal: goals.protein, color: '#3b82f6' },
                { label: 'Углев.', val: nutrition.avg_carbs, goal: goals.carbs, color: '#10b981' },
                { label: 'Жиры', val: nutrition.avg_fat, goal: goals.fat, color: '#8b5cf6' },
              ].map(({ label, val, goal, color }) => (
                <div key={label} style={{ flex: 1, background: 'var(--bg)', borderRadius: 10, padding: '8px 10px', textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--hint)', marginBottom: 2 }}>{label}</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color }}>{val}г</div>
                  <div style={{ fontSize: 10, color: 'var(--hint)' }}>/{goal}г</div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div style={{ color: 'var(--hint)', fontSize: 13, textAlign: 'center' }}>
            Питание на этой неделе не записано
          </div>
        )}
      </div>
    </>
  )
}

const TonnageTooltip = memo(({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: 'var(--bg2)', padding: '8px 12px', borderRadius: 8, fontSize: 13 }}>
      <div style={{ fontWeight: 600 }}>{payload[0].payload.label}</div>
      <div style={{ color: 'var(--hint)' }}>{payload[0].value.toLocaleString('ru')} кг</div>
    </div>
  )
})

const CalTooltip = memo(({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: 'var(--bg2)', padding: '8px 12px', borderRadius: 8, fontSize: 13 }}>
      <div style={{ fontWeight: 600 }}>{payload[0].payload.day_label}</div>
      <div style={{ color: 'var(--hint)' }}>{payload[0].value} ккал</div>
    </div>
  )
})

const WeightTooltip = memo(({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={{ background: 'var(--bg2)', padding: '8px 12px', borderRadius: 8, fontSize: 13 }}>
      <div style={{ fontWeight: 600 }}>{d.date}</div>
      <div style={{ color: 'var(--hint)' }}>{d.weight} кг</div>
    </div>
  )
})

function TonnageTab({ data }) {
  const { tonnage_weeks, stats, exercise_prs, plateaus = [] } = data
  const currentTonnage = tonnage_weeks[tonnage_weeks.length - 1]?.tonnage || 0
  const prevTonnage = tonnage_weeks[tonnage_weeks.length - 2]?.tonnage || 0
  const delta = currentTonnage - prevTonnage
  const [chartEx, setChartEx] = useState(null)

  return (
    <>
      <div className="card">
        <div className="section-title">Тоннаж по неделям</div>
        <div style={{ marginBottom: 8 }}>
          <span style={{ fontSize: 26, fontWeight: 700 }}>{currentTonnage.toLocaleString('ru')} кг</span>
          {delta !== 0 && prevTonnage > 0 && (
            <span style={{ marginLeft: 8, fontSize: 13, color: delta >= 0 ? '#30d158' : '#ff453a' }}>
              {delta >= 0 ? '↑ +' : '↓ '}{delta.toLocaleString('ru')} кг
            </span>
          )}
        </div>
        <ResponsiveContainer width="100%" height={150}>
          <AreaChart data={tonnage_weeks} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="tonnageGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.3} />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="label" tick={{ fontSize: 9, fill: 'var(--hint)' }} axisLine={false} tickLine={false} />
            <Tooltip content={<TonnageTooltip />} cursor={{ stroke: 'var(--accent)', strokeWidth: 1, strokeDasharray: '4 2' }} />
            <Area
              type="monotone"
              dataKey="tonnage"
              stroke="var(--accent)"
              strokeWidth={2.5}
              fill="url(#tonnageGrad)"
              dot={{ fill: 'var(--accent)', r: 3, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: 'var(--accent)', stroke: 'var(--bg)', strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 12 }}>
        <div className="card" style={{ textAlign: 'center', padding: 12, marginBottom: 0 }}>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{stats.total_workouts}</div>
          <div style={{ fontSize: 11, color: 'var(--hint)', marginTop: 2 }}>Тренировок</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 12, marginBottom: 0 }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#ff9f0a' }}>{stats.avg_rpe || '—'}</div>
          <div style={{ fontSize: 11, color: 'var(--hint)', marginTop: 2 }}>Средний RPE</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 12, marginBottom: 0 }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#30d158' }}>
            {stats.body_weight ? `${stats.body_weight}кг` : '—'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--hint)', marginTop: 2 }}>Вес тела</div>
        </div>
      </div>

      {exercise_prs.length > 0 && (
        <div className="card">
          <div className="section-title">Лучшие веса</div>
          {exercise_prs.map((pr, i) => (
            <div key={i}
              onClick={() => setChartEx(chartEx === pr.exercise ? null : pr.exercise)}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 0', cursor: 'pointer',
                borderBottom: i < exercise_prs.length - 1 ? '1px solid var(--sep)' : 'none',
              }}>
              <div style={{ fontSize: 14 }}>{pr.exercise}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontWeight: 700, fontSize: 16 }}>{pr.weight} кг</span>
                <span style={{
                  background: 'var(--accent)', color: 'var(--accent-text)',
                  fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 6,
                }}>ПР</span>
                <span style={{ color: 'var(--hint)', fontSize: 14 }}>
                  {chartEx === pr.exercise ? '▲' : '▼'}
                </span>
              </div>
            </div>
          ))}
          {chartEx && (
            <ExerciseProgressChart
              exercise={chartEx}
              onClose={() => setChartEx(null)}
            />
          )}
        </div>
      )}

      {plateaus.length > 0 && (
        <div className="card" style={{ border: '1px solid rgba(255,159,10,0.3)', background: 'rgba(255,159,10,0.06)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span style={{ fontSize: 18 }}>⚠️</span>
            <div style={{ fontSize: 15, fontWeight: 700 }}>Плато</div>
            <span style={{ fontSize: 11, color: 'var(--orange)', background: 'rgba(255,159,10,0.15)', padding: '2px 8px', borderRadius: 10, fontWeight: 600 }}>
              {plateaus.length} упр.
            </span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--hint)', marginBottom: 10, lineHeight: 1.4 }}>
            Одинаковый вес 3+ тренировки подряд. Попробуй увеличить на 2.5–5 кг.
          </div>
          {plateaus.map((p, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '8px 0',
              borderTop: i > 0 ? '1px solid var(--sep)' : 'none',
            }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{p.exercise}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, color: 'var(--hint)' }}>{p.weight} кг · {p.sessions} сес.</span>
                {p.avg_rpe > 0 && (
                  <span style={{ fontSize: 11, color: 'var(--orange)', fontWeight: 600 }}>RPE {p.avg_rpe.toFixed(1)}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}

function NutritionTab({ data }) {
  const { nutrition_week, nutrition_daily, goals } = data

  return (
    <>
      <div className="card">
        <div className="section-title">Среднее за 7 дней</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginTop: 8 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{(nutrition_week.avg_calories).toLocaleString('ru')}</div>
            <div style={{ fontSize: 11, color: 'var(--hint)', marginTop: 2 }}>ккал / день</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--accent)' }}>{nutrition_week.avg_protein}г</div>
            <div style={{ fontSize: 11, color: 'var(--hint)', marginTop: 2 }}>белки / день</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: '#30d158' }}>{nutrition_week.days_tracked}/7</div>
            <div style={{ fontSize: 11, color: 'var(--hint)', marginTop: 2 }}>дней залог.</div>
          </div>
        </div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
          <div className="section-title" style={{ marginBottom: 0 }}>Калории по дням</div>
          <div style={{ fontSize: 11, color: 'var(--hint)' }}>цель {goals.calories.toLocaleString('ru')} ккал</div>
        </div>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart data={nutrition_daily} margin={{ top: 4, right: 4, bottom: 0, left: 0 }} barCategoryGap="25%">
            <XAxis dataKey="day_label" tick={{ fontSize: 10, fill: 'var(--hint)' }} axisLine={false} tickLine={false} />
            <Tooltip content={<CalTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
            <Bar dataKey="calories" radius={[4, 4, 0, 0]}>
              {nutrition_daily.map((d, i) => (
                <Cell key={i} fill={d.is_today ? 'var(--accent)' : 'rgba(59,130,246,0.4)'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <div className="section-title">Выполнение целей (среднее)</div>
        <ProgressBar label="🔥 Калории" current={nutrition_week.avg_calories} goal={goals.calories} color="#f59e0b" />
        <ProgressBar label="🥩 Белки" current={nutrition_week.avg_protein} goal={goals.protein} color="#3b82f6" />
        <ProgressBar label="🌾 Углеводы" current={nutrition_week.avg_carbs} goal={goals.carbs} color="#10b981" />
        <ProgressBar label="🫒 Жиры" current={nutrition_week.avg_fat} goal={goals.fat} color="#8b5cf6" />
      </div>
    </>
  )
}

function BodyTab() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [weightInput, setWeightInput] = useState('')
  const [showWeightForm, setShowWeightForm] = useState(false)
  const [showMeasForm, setShowMeasForm] = useState(false)
  const [measInputs, setMeasInputs] = useState({ chest: '', waist: '', bicep: '', hips: '' })
  const [saving, setSaving] = useState(false)
  const { show: showToast, ToastEl } = useToast()

  const load = () => {
    setLoading(true)
    api.bodyData()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const saveWeight = async () => {
    const w = parseFloat(weightInput)
    if (!w || w < 20 || w > 400) {
      showToast('Введи вес от 20 до 400 кг', true)
      return
    }
    setSaving(true)
    try {
      await api.logWeight(w)
      setShowWeightForm(false)
      setWeightInput('')
      load()
      showToast('Вес записан ✓')
    } catch (e) {
      showToast(friendlyError(e), true)
    } finally { setSaving(false) }
  }

  const saveMeasurements = async () => {
    const payload = {}
    for (const [k, v] of Object.entries(measInputs)) {
      const n = parseFloat(v)
      if (n > 0) payload[k] = n
    }
    if (!Object.keys(payload).length) {
      showToast('Заполни хотя бы одно поле', true)
      return
    }
    setSaving(true)
    try {
      await api.logMeasurements(payload)
      setShowMeasForm(false)
      setMeasInputs({ chest: '', waist: '', bicep: '', hips: '' })
      load()
      showToast('Замеры сохранены ✓')
    } catch (e) {
      showToast(friendlyError(e), true)
    } finally { setSaving(false) }
  }

  if (loading) return <div style={{ color: 'var(--hint)', textAlign: 'center', padding: 32 }}>Загружаем...</div>
  if (!data) return <div style={{ color: '#f87171', textAlign: 'center', padding: 32 }}>Ошибка загрузки</div>

  const { current_weight, weight_history, measurements, deltas, bmi, bmi_label } = data
  const chartData = weight_history.map(d => ({ ...d, date: d.date.slice(5) }))
  const wFirst = weight_history[0]?.weight
  const wLast = weight_history[weight_history.length - 1]?.weight
  const weightDelta = (weight_history.length >= 2 && wFirst && wLast)
    ? parseFloat((wLast - wFirst).toFixed(1)) : null

  const MEAS_LABELS = { chest: 'Грудь', waist: 'Талия', bicep: 'Бицепс', hips: 'Бёдра' }

  return (
    <>
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div className="section-title" style={{ marginBottom: 0 }}>Вес тела</div>
          <button
            onClick={() => setShowWeightForm(v => !v)}
            style={{
              background: showWeightForm ? 'var(--bg3)' : 'var(--accent)',
              color: showWeightForm ? 'var(--text)' : 'var(--accent-text)',
              borderRadius: 8, padding: '4px 12px', fontSize: 13, fontWeight: 600,
            }}
          >{showWeightForm ? 'Отмена' : '+ Вес'}</button>
        </div>

        {showWeightForm && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <input
              type="number"
              value={weightInput}
              onChange={e => setWeightInput(e.target.value)}
              placeholder="кг, напр. 82.5"
              style={{
                flex: 1, background: 'var(--bg)', color: 'var(--text)',
                border: '1px solid var(--border)', borderRadius: 10,
                padding: '10px 12px', fontSize: 14,
              }}
            />
            <button
              onClick={saveWeight} disabled={saving}
              style={{
                background: '#30d158', color: '#fff', borderRadius: 10,
                padding: '10px 16px', fontSize: 14, fontWeight: 600,
              }}
            >{saving ? '...' : 'OK'}</button>
          </div>
        )}

        <div style={{ marginBottom: 8 }}>
          <span style={{ fontSize: 32, fontWeight: 700 }}>{current_weight || '—'}</span>
          {current_weight > 0 && <span style={{ fontSize: 16, color: 'var(--hint)', marginLeft: 4 }}>кг</span>}
          {weightDelta !== null && (
            <span style={{ marginLeft: 12, fontSize: 13, color: weightDelta > 0 ? '#ff453a' : '#30d158' }}>
              {weightDelta > 0 ? '↑ +' : '↓ '}{Math.abs(weightDelta)} кг за 8 нед.
            </span>
          )}
        </div>

        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height={130}>
            <AreaChart data={chartData} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="bodyWGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#bf5af2" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#bf5af2" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--hint)' }} axisLine={false} tickLine={false} />
              <Tooltip content={<WeightTooltip />} cursor={{ stroke: '#bf5af2', strokeWidth: 1, strokeDasharray: '4 2' }} />
              <Area type="monotone" dataKey="weight" stroke="#bf5af2" strokeWidth={2.5} fill="url(#bodyWGrad)"
                dot={{ fill: '#bf5af2', r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: '#bf5af2', stroke: 'var(--bg)', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ color: 'var(--hint)', fontSize: 13, padding: '8px 0' }}>
            Нет истории — записывай вес каждую неделю
          </div>
        )}
      </div>

      {bmi && (
        <div className="card" style={{ background: 'rgba(10,132,255,0.12)', border: '1px solid rgba(10,132,255,0.25)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--hint)', marginBottom: 4 }}>Индекс массы тела (ИМТ)</div>
              <div style={{ fontSize: 30, fontWeight: 700, color: '#0a84ff' }}>{bmi}</div>
            </div>
            <div style={{
              background: '#0a84ff', color: '#fff',
              borderRadius: 10, padding: '8px 16px', fontSize: 15, fontWeight: 600,
            }}>{bmi_label}</div>
          </div>
        </div>
      )}

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div className="section-title" style={{ marginBottom: 0 }}>Замеры (см)</div>
          <button
            onClick={() => setShowMeasForm(v => !v)}
            style={{
              background: showMeasForm ? 'var(--bg3)' : 'var(--bg3)',
              color: 'var(--text)', borderRadius: 8, padding: '4px 12px', fontSize: 13,
            }}
          >{showMeasForm ? 'Отмена' : '+ Замеры'}</button>
        </div>

        {showMeasForm && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
              {Object.entries(MEAS_LABELS).map(([key, label]) => (
                <div key={key}>
                  <div style={{ fontSize: 11, color: 'var(--hint)', marginBottom: 4 }}>{label}</div>
                  <input
                    type="number"
                    value={measInputs[key]}
                    onChange={e => setMeasInputs(v => ({ ...v, [key]: e.target.value }))}
                    placeholder="см"
                    style={{
                      width: '100%', background: 'var(--bg)', color: 'var(--text)',
                      border: '1px solid var(--border)', borderRadius: 8,
                      padding: '8px 10px', fontSize: 14, boxSizing: 'border-box',
                    }}
                  />
                </div>
              ))}
            </div>
            <button
              onClick={saveMeasurements} disabled={saving}
              style={{
                width: '100%', background: '#30d158', color: '#fff',
                borderRadius: 10, padding: 10, fontSize: 14, fontWeight: 600,
              }}
            >{saving ? 'Сохраняю...' : 'Сохранить замеры'}</button>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {Object.entries(MEAS_LABELS).map(([key, label]) => {
            const val = measurements[key]
            const d = deltas[key]
            return (
              <div key={key} style={{ background: 'var(--bg)', borderRadius: 12, padding: '12px 14px' }}>
                <div style={{ fontSize: 11, color: 'var(--hint)', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 20, fontWeight: 700 }}>
                  {val != null ? val : '—'}
                  {val != null && <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--hint)', marginLeft: 2 }}>см</span>}
                </div>
                {d != null && (
                  <div style={{ fontSize: 11, marginTop: 2, color: d > 0 ? '#ff9f0a' : '#30d158' }}>
                    {d > 0 ? '↑ +' : '↓ '}{Math.abs(d)} за 30 дн.
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
      {ToastEl}
    </>
  )
}

function WeightsTab({ exercises }) {
  const [selected, setSelected] = useState(exercises[0] || '')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    api.exerciseHistory(selected)
      .then(d => setHistory(d.history || []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false))
  }, [selected])

  const lastWeight = history[history.length - 1]?.weight || 0
  const prevWeight = history[history.length - 2]?.weight || 0
  const delta = lastWeight - prevWeight

  if (exercises.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', color: 'var(--hint)', padding: 32 }}>
        Нет данных — сначала залогируй тренировки
      </div>
    )
  }

  return (
    <div className="card">
      <select
        value={selected}
        onChange={e => setSelected(e.target.value)}
        style={{
          width: '100%', background: 'var(--bg)', color: 'var(--text)',
          border: '1px solid var(--border)', borderRadius: 10,
          padding: '10px 12px', fontSize: 14, marginBottom: 12,
        }}
      >
        {exercises.map(ex => <option key={ex} value={ex}>{ex}</option>)}
      </select>

      {loading && (
        <div style={{ color: 'var(--hint)', textAlign: 'center', padding: 24 }}>Загружаем...</div>
      )}

      {!loading && history.length > 0 && (
        <>
          <div style={{ marginBottom: 8 }}>
            <span style={{ fontSize: 26, fontWeight: 700 }}>{lastWeight} кг</span>
            {delta !== 0 && history.length > 1 && (
              <span style={{ marginLeft: 8, fontSize: 13, color: delta > 0 ? '#30d158' : '#ff453a' }}>
                {delta > 0 ? '↑ +' : '↓ '}{delta} кг
              </span>
            )}
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={history} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="weightGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#30d158" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#30d158" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--hint)' }} axisLine={false} tickLine={false} />
              <Tooltip content={<WeightTooltip />} cursor={{ stroke: '#30d158', strokeWidth: 1, strokeDasharray: '4 2' }} />
              <Area
                type="monotone"
                dataKey="weight"
                stroke="#30d158"
                strokeWidth={2.5}
                fill="url(#weightGrad)"
                dot={{ fill: '#30d158', r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: '#30d158', stroke: 'var(--bg)', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </>
      )}

      {!loading && history.length === 0 && (
        <div style={{ color: 'var(--hint)', textAlign: 'center', padding: 24 }}>
          Нет данных по этому упражнению
        </div>
      )}
    </div>
  )
}

function muscleColor(g) {
  if (!g || !g.last_trained) return 'rgba(255,255,255,0.07)'
  const a = (0.35 + g.intensity * 0.55).toFixed(2)
  if (g.days_since <= 5) return `rgba(48,209,88,${a})`
  if (g.days_since <= 12) return `rgba(255,159,10,${a})`
  return `rgba(255,69,58,${a})`
}

function BodyFront({ byId }) {
  const c = (id) => muscleColor(byId[id])
  const fill = '#2a2a2e'
  const stroke = '#48484a'
  const sw = '1'
  return (
    <svg viewBox="0 0 100 240" style={{ width: '100%' }}>
      {/* head */}
      <circle cx="50" cy="13" r="11" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* neck */}
      <rect x="46" y="24" width="8" height="7" fill={fill} stroke={stroke} strokeWidth="0.5" />
      {/* left arm */}
      <rect x="13" y="32" width="13" height="52" rx="6" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* right arm */}
      <rect x="74" y="32" width="13" height="52" rx="6" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* torso upper */}
      <path d="M26 32 L74 32 L69 82 L31 82 Z" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* hips */}
      <path d="M31 82 L69 82 L73 100 L27 100 Z" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* left thigh */}
      <rect x="27" y="99" width="19" height="60" rx="8" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* right thigh */}
      <rect x="54" y="99" width="19" height="60" rx="8" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* left calf */}
      <rect x="29" y="157" width="15" height="52" rx="6" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* right calf */}
      <rect x="56" y="157" width="15" height="52" rx="6" fill={fill} stroke={stroke} strokeWidth={sw} />

      {/* ── muscles ── */}
      {/* chest */}
      <ellipse cx="37" cy="50" rx="9" ry="11" fill={c('chest')} />
      <ellipse cx="63" cy="50" rx="9" ry="11" fill={c('chest')} />
      {/* shoulders */}
      <ellipse cx="21" cy="38" rx="7" ry="6" fill={c('shoulders')} />
      <ellipse cx="79" cy="38" rx="7" ry="6" fill={c('shoulders')} />
      {/* biceps */}
      <ellipse cx="19.5" cy="56" rx="5" ry="10" fill={c('biceps')} />
      <ellipse cx="80.5" cy="56" rx="5" ry="10" fill={c('biceps')} />
      {/* abs */}
      <rect x="41" y="62" width="7" height="8" rx="2" fill={c('abs')} />
      <rect x="52" y="62" width="7" height="8" rx="2" fill={c('abs')} />
      <rect x="41" y="72" width="7" height="8" rx="2" fill={c('abs')} />
      <rect x="52" y="72" width="7" height="8" rx="2" fill={c('abs')} />
      {/* quads */}
      <ellipse cx="36.5" cy="127" rx="8" ry="20" fill={c('quads')} />
      <ellipse cx="63.5" cy="127" rx="8" ry="20" fill={c('quads')} />
      {/* calves front */}
      <ellipse cx="36.5" cy="175" rx="6" ry="15" fill={c('calves')} />
      <ellipse cx="63.5" cy="175" rx="6" ry="15" fill={c('calves')} />
    </svg>
  )
}

function BodyBack({ byId }) {
  const c = (id) => muscleColor(byId[id])
  const fill = '#2a2a2e'
  const stroke = '#48484a'
  const sw = '1'
  return (
    <svg viewBox="0 0 100 240" style={{ width: '100%' }}>
      {/* head */}
      <circle cx="50" cy="13" r="11" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* neck */}
      <rect x="46" y="24" width="8" height="7" fill={fill} stroke={stroke} strokeWidth="0.5" />
      {/* left arm */}
      <rect x="13" y="32" width="13" height="52" rx="6" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* right arm */}
      <rect x="74" y="32" width="13" height="52" rx="6" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* torso upper */}
      <path d="M26 32 L74 32 L69 82 L31 82 Z" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* hips */}
      <path d="M31 82 L69 82 L73 100 L27 100 Z" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* left thigh */}
      <rect x="27" y="99" width="19" height="60" rx="8" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* right thigh */}
      <rect x="54" y="99" width="19" height="60" rx="8" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* left calf */}
      <rect x="29" y="157" width="15" height="52" rx="6" fill={fill} stroke={stroke} strokeWidth={sw} />
      {/* right calf */}
      <rect x="56" y="157" width="15" height="52" rx="6" fill={fill} stroke={stroke} strokeWidth={sw} />

      {/* ── muscles ── */}
      {/* traps */}
      <path d="M26 32 Q50 50 74 32 L62 46 Q50 54 38 46 Z" fill={c('back')} />
      {/* lats */}
      <path d="M26 32 L31 82 L45 68 L36 38 Z" fill={c('back')} />
      <path d="M74 32 L69 82 L55 68 L64 38 Z" fill={c('back')} />
      {/* rear delts */}
      <ellipse cx="21" cy="38" rx="7" ry="6" fill={c('shoulders')} />
      <ellipse cx="79" cy="38" rx="7" ry="6" fill={c('shoulders')} />
      {/* triceps */}
      <ellipse cx="19.5" cy="56" rx="5" ry="10" fill={c('triceps')} />
      <ellipse cx="80.5" cy="56" rx="5" ry="10" fill={c('triceps')} />
      {/* glutes */}
      <ellipse cx="36.5" cy="100" rx="11" ry="9" fill={c('glutes')} />
      <ellipse cx="63.5" cy="100" rx="11" ry="9" fill={c('glutes')} />
      {/* hamstrings */}
      <ellipse cx="36.5" cy="127" rx="8" ry="20" fill={c('hamstrings')} />
      <ellipse cx="63.5" cy="127" rx="8" ry="20" fill={c('hamstrings')} />
      {/* calves back */}
      <ellipse cx="36.5" cy="175" rx="6" ry="15" fill={c('calves')} />
      <ellipse cx="63.5" cy="175" rx="6" ry="15" fill={c('calves')} />
    </svg>
  )
}

function MusclesTab() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.musclesData()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ color: 'var(--hint)', textAlign: 'center', padding: 32 }}>Загружаем...</div>
  if (!data) return <div style={{ color: '#f87171', textAlign: 'center', padding: 32 }}>Ошибка загрузки</div>

  const { groups } = data
  const byId = Object.fromEntries(groups.map(g => [g.id, g]))

  const daysLabel = (g) => {
    if (!g.last_trained) return '—'
    if (g.days_since === 0) return 'сегодня'
    if (g.days_since === 1) return 'вчера'
    return `${g.days_since}д`
  }

  const dotColor = (g) => {
    if (!g.last_trained) return 'var(--bg3)'
    if (g.days_since <= 5) return '#30d158'
    if (g.days_since <= 12) return '#ff9f0a'
    return '#ff453a'
  }

  return (
    <>
      {/* body figures */}
      <div className="card">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <div>
            <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--hint)', marginBottom: 4 }}>Спереди</div>
            <BodyFront byId={byId} />
          </div>
          <div>
            <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--hint)', marginBottom: 4 }}>Сзади</div>
            <BodyBack byId={byId} />
          </div>
        </div>

        {/* legend */}
        <div style={{ display: 'flex', gap: 12, marginTop: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
          {[
            { color: '#30d158', label: '≤5 дн.' },
            { color: '#ff9f0a', label: '6–12 дн.' },
            { color: '#ff453a', label: '13+ дн.' },
          ].map(({ color, label }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
              <span style={{ color: 'var(--hint)' }}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* compact list */}
      <div className="card">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          {groups.map(g => (
            <div key={g.id} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '6px 8px', background: 'var(--bg)', borderRadius: 8,
            }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: dotColor(g), flexShrink: 0 }} />
              <div style={{ flex: 1, fontSize: 12, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{g.label}</div>
              <div style={{ fontSize: 11, color: dotColor(g), fontWeight: 600, flexShrink: 0 }}>{daysLabel(g)}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

export default function Progress() {
  const [tab, setTab] = useState(0)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.progress()
      .then(setData)
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="spinner">Загружаем прогресс...</div>
  if (err) return <div className="spinner" style={{ color: '#f87171' }}>{err}</div>

  return (
    <div className="page">
      <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 16 }}>Прогресс</div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        {TAB_LABELS.map((label, i) => (
          <button
            key={i}
            onClick={() => setTab(i)}
            style={{
              flex: 1, padding: '7px 2px', borderRadius: 10, fontSize: 11, fontWeight: 600,
              background: tab === i ? 'var(--accent)' : 'var(--bg2)',
              color: tab === i ? 'var(--accent-text)' : 'var(--hint)',
              transition: 'background 0.15s, color 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 0 && <WeekTab />}
      {tab === 1 && <TonnageTab data={data} />}
      {tab === 2 && <NutritionTab data={data} />}
      {tab === 3 && <WeightsTab exercises={data.exercises} />}
      {tab === 4 && <BodyTab />}
      {tab === 5 && <MusclesTab />}
    </div>
  )
}
