import { useEffect, useState, memo } from 'react'
import { AreaChart, Area, BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api } from '../api'
import ProgressBar from '../components/ProgressBar'

const TAB_LABELS = ['Тоннаж', 'Питание', 'Веса']

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
  const { tonnage_weeks, stats, exercise_prs } = data
  const currentTonnage = tonnage_weeks[tonnage_weeks.length - 1]?.tonnage || 0
  const prevTonnage = tonnage_weeks[tonnage_weeks.length - 2]?.tonnage || 0
  const delta = currentTonnage - prevTonnage

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
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '10px 0',
              borderBottom: i < exercise_prs.length - 1 ? '1px solid var(--sep)' : 'none',
            }}>
              <div style={{ fontSize: 14 }}>{pr.exercise}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontWeight: 700, fontSize: 16 }}>{pr.weight} кг</span>
                <span style={{
                  background: 'var(--accent)', color: 'var(--accent-text)',
                  fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 6,
                }}>ПР</span>
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

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {TAB_LABELS.map((label, i) => (
          <button
            key={i}
            onClick={() => setTab(i)}
            style={{
              flex: 1, padding: '8px 4px', borderRadius: 10, fontSize: 13, fontWeight: 600,
              background: tab === i ? 'var(--accent)' : 'var(--bg2)',
              color: tab === i ? 'var(--accent-text)' : 'var(--hint)',
              transition: 'background 0.15s, color 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 0 && <TonnageTab data={data} />}
      {tab === 1 && <NutritionTab data={data} />}
      {tab === 2 && <WeightsTab exercises={data.exercises} />}
    </div>
  )
}
