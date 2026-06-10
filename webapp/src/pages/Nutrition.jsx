import { useEffect, useState, useRef, useCallback } from 'react'
import { api } from '../api'
import { haptic } from '../tg'

const DAYS_RU = ['Воскресенье','Понедельник','Вторник','Среда','Четверг','Пятница','Суббота']
const MONTHS_RU = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']

function todayLabel() {
  const d = new Date()
  return `${DAYS_RU[d.getDay()]}, ${d.getDate()} ${MONTHS_RU[d.getMonth()]}`
}

// ── Double-ring SVG ───────────────────────────────────────────────────────────
function NutritionRing({ calories, goalCalories, protein, goalProtein }) {
  const r = 44, rIn = 31
  const circ = 2 * Math.PI * r
  const circIn = 2 * Math.PI * rIn
  const calPct = goalCalories > 0 ? Math.min(calories / goalCalories, 1) : 0
  const protPct = goalProtein > 0 ? Math.min(protein / goalProtein, 1) : 0
  return (
    <div className="ring-wrap" style={{ width: 110, height: 110 }}>
      <svg width="110" height="110" viewBox="0 0 110 110">
        <circle cx="55" cy="55" r={r} fill="none" stroke="var(--bg3)" strokeWidth="10" />
        <circle cx="55" cy="55" r={r} fill="none" stroke="var(--blue)" strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={circ * (1 - calPct)}
          transform="rotate(-90 55 55)"
          style={{ transition: 'stroke-dashoffset 0.5s' }}
        />
        <circle cx="55" cy="55" r={rIn} fill="none" stroke="var(--bg3)" strokeWidth="6" opacity="0.5" />
        <circle cx="55" cy="55" r={rIn} fill="none" stroke="var(--green)" strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circIn} strokeDashoffset={circIn * (1 - protPct)}
          transform="rotate(-90 55 55)"
          opacity="0.8"
          style={{ transition: 'stroke-dashoffset 0.5s' }}
        />
      </svg>
      <div className="ring-center">
        <div className="ring-kcal">{Math.round(calories)}</div>
        <div className="ring-sub">ккал</div>
      </div>
    </div>
  )
}

// ── Food action sheet ─────────────────────────────────────────────────────────
function FoodSheet({ entry, onClose, onDelete, onUpdate }) {
  const [editMode, setEditMode] = useState(false)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (entry) { setEditMode(false); setText(entry.description || '') }
  }, [entry?.id])

  if (!entry) return null

  const doUpdate = async () => {
    if (!text.trim() || saving) return
    setSaving(true); haptic('medium')
    await onUpdate(text.trim())
    setSaving(false)
  }

  return (
    <>
      <div className="fs-overlay" onClick={onClose} />
      <div className="fs-sheet">
        <div className="fs-handle" />
        {editMode && (
          <div className="fs-edit-wrap">
            <div className="fs-edit-label">Описание блюда</div>
            <textarea className="fs-edit-input" value={text} onChange={(e) => setText(e.target.value)} rows={3} autoFocus />
            <button className="btn-primary" style={{ marginTop: 10 }} disabled={saving || !text.trim()} onClick={doUpdate}>
              {saving ? 'Пересчитываю КБЖУ...' : 'Сохранить'}
            </button>
            <div className="fs-sep" style={{ marginTop: 16 }} />
          </div>
        )}
        <div className="fs-item" onClick={() => setEditMode(!editMode)}>
          <span className="fs-icon">✏️</span>Изменить описание
        </div>
        <div className="fs-sep" />
        <div className="fs-item fs-danger" onClick={() => { haptic('heavy'); onDelete() }}>
          <span className="fs-icon">🗑</span>Удалить
        </div>
      </div>
    </>
  )
}

// ── Water strip inside dock ───────────────────────────────────────────────────
function WaterStrip() {
  const [water, setWater] = useState(null)

  useEffect(() => { api.waterToday().then(setWater).catch(() => {}) }, [])

  const handleAdd = async () => {
    haptic('light')
    try { const r = await api.waterAdd(); setWater(r) } catch {}
  }

  if (!water) return null
  const { glasses, goal } = water
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px 6px', borderBottom: '1px solid var(--sep)' }}>
      <span style={{ fontSize: 13 }}>💧</span>
      <div style={{ display: 'flex', gap: 3, flex: 1 }}>
        {Array.from({ length: goal }).map((_, i) => (
          <div key={i} style={{
            width: 11, height: 11, borderRadius: 3,
            background: i < glasses ? 'var(--blue)' : 'var(--bg3)',
            transition: 'background 0.2s',
          }} />
        ))}
      </div>
      <span style={{ fontSize: 11, color: 'var(--hint)', whiteSpace: 'nowrap' }}>{glasses} из {goal}</span>
      <button onClick={handleAdd} style={{
        background: 'rgba(10,132,255,.12)', border: 'none', borderRadius: 12,
        padding: '4px 11px', fontSize: 12, fontWeight: 700, color: 'var(--blue)', cursor: 'pointer',
      }}>+ стакан</button>
    </div>
  )
}

// ── Nutrition dock (fixed above navbar) ──────────────────────────────────────
function NutritionDock({ onLogged }) {
  const [mode, setMode] = useState(null)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [recording, setRecording] = useState(false)
  const [templates, setTemplates] = useState([])
  const mediaRef = useRef(null)
  const chunksRef = useRef([])
  const fileRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    api.nutritionTemplates().then((r) => setTemplates(r.templates || [])).catch(() => {})
  }, [])

  const send = async (fn) => {
    setSending(true)
    try {
      await fn(); onLogged(); setText(''); setMode(null); haptic('medium')
    } catch (e) {
      haptic('heavy'); alert('Ошибка: ' + e.message)
    } finally { setSending(false) }
  }

  const handleText = () => send(() => api.logFood(text.trim()))

  const handlePhotoChange = async (e) => {
    const file = e.target.files?.[0]; if (!file) return
    e.target.value = ''
    const fd = new FormData(); fd.append('file', file)
    await send(() => api.logPhoto(fd))
  }

  const startVoice = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const fd = new FormData(); fd.append('file', blob, 'voice.webm')
        await send(() => api.logVoice(fd))
        setRecording(false)
      }
      mr.start(); mediaRef.current = mr; setRecording(true)
    } catch { alert('Нет доступа к микрофону') }
  }

  const stopVoice = () => { mediaRef.current?.stop() }

  const toggleMode = (m) => {
    haptic('light')
    if (m === 'voice') { setMode('voice'); startVoice(); return }
    if (mode === m) { setMode(null); return }
    setMode(m)
    if (m === 'text') setTimeout(() => textareaRef.current?.focus(), 100)
  }

  return (
    <div className="nutr-dock">
      {/* Quick chips */}
      {templates.length > 0 && mode === null && (
        <div style={{ display: 'flex', gap: 6, overflowX: 'auto', padding: '6px 12px 2px', scrollbarWidth: 'none' }}>
          {templates.slice(0, 8).map((t) => (
            <button key={t.description}
              onClick={() => { setText(t.description); setMode('text'); setTimeout(() => textareaRef.current?.focus(), 100) }}
              style={{
                background: 'var(--bg2)', border: '1px solid var(--sep)', borderRadius: 12,
                padding: '6px 10px', fontSize: 11, fontWeight: 600, color: 'var(--text)',
                cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0, lineHeight: 1.2,
              }}
            >
              <div>{t.description}</div>
              <div style={{ color: 'var(--hint)', fontSize: 10 }}>{t.calories} ккал</div>
            </button>
          ))}
        </div>
      )}

      {/* Text expand */}
      {mode === 'text' && (
        <div style={{ padding: '10px 12px 8px', display: 'flex', gap: 8 }}>
          <textarea
            ref={textareaRef} rows={2} value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Что съел? Например: куриная грудка 200г, рис..."
            disabled={sending}
            style={{
              flex: 1, background: 'var(--bg2)', border: '1.5px solid var(--bg3)',
              borderRadius: 12, padding: '10px 12px', color: 'var(--text)',
              fontSize: 14, resize: 'none', fontFamily: 'inherit',
              outline: 'none',
            }}
          />
          <button onClick={handleText} disabled={!text.trim() || sending}
            style={{
              width: 44, height: 44, alignSelf: 'flex-end',
              background: sending ? 'var(--bg3)' : 'var(--blue)',
              border: 'none', borderRadius: 12, color: '#fff', fontSize: 18,
              cursor: 'pointer', flexShrink: 0,
            }}
          >{sending ? '…' : '→'}</button>
        </div>
      )}

      {/* Voice panel */}
      {mode === 'voice' && (
        <div style={{ padding: '12px', display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(10,132,255,.05)' }}>
          {recording ? (
            <>
              <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
                {[0,1,2,3,4,5,6,7,8].map((i) => (
                  <div key={i} style={{
                    width: 3.5, background: 'var(--blue)', borderRadius: 2,
                    animation: `voiceWave 1.1s ease-in-out ${i * 0.12}s infinite alternate`,
                    height: 16,
                  }} />
                ))}
              </div>
              <span style={{ flex: 1, fontSize: 13, color: 'var(--hint)' }}>Слушаю...</span>
              <button onClick={stopVoice} style={{
                background: 'rgba(255,69,58,.15)', border: 'none', borderRadius: 10,
                color: 'var(--red)', fontSize: 12, fontWeight: 700, padding: '7px 14px', cursor: 'pointer',
              }}>⏹ Стоп</button>
            </>
          ) : (
            <div style={{ flex: 1, textAlign: 'center', color: 'var(--hint)', fontSize: 13 }}>
              {sending ? 'Анализирую...' : 'Ошибка записи'}
            </div>
          )}
        </div>
      )}

      {/* Water strip */}
      <WaterStrip />

      {/* 3 NIB buttons */}
      <input ref={fileRef} type="file" accept="image/*" capture="environment" style={{ display: 'none' }} onChange={handlePhotoChange} />
      <div style={{ display: 'flex', gap: 6, padding: '6px 12px 10px' }}>
        {[
          { key: 'photo',  icon: '📷', label: 'Фото',  iconBg: 'rgba(255,159,10,.15)',  action: () => { haptic('light'); fileRef.current?.click() } },
          { key: 'voice',  icon: '🎤', label: 'Голос', iconBg: 'rgba(10,132,255,.15)',  action: () => toggleMode('voice') },
          { key: 'text',   icon: '✏️', label: 'Текст', iconBg: 'rgba(48,209,88,.15)',   action: () => toggleMode('text') },
        ].map(({ key, icon, label, iconBg, action }) => (
          <button key={key} onClick={action}
            className={`nib${mode === key ? ' nib-active' : ''}${key === 'voice' && recording ? ' nib-recording' : ''}`}
          >
            <div className="nib-icon" style={{ background: iconBg }}>{icon}</div>
            <span className="nib-label">{label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function Nutrition() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [toast, setToast] = useState(null)
  const [sheetEntry, setSheetEntry] = useState(null)

  const showToast = (msg, isError = false) => {
    setToast({ msg, isError }); setTimeout(() => setToast(null), 3000)
  }

  const load = useCallback(() => {
    api.nutritionToday()
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleDelete = async () => {
    const id = sheetEntry.id; setSheetEntry(null)
    try {
      await api.deleteFood(id)
      await api.nutritionToday().then(setData)
      showToast('Приём удалён')
    } catch (e) { showToast('Ошибка: ' + e.message, true) }
  }

  const handleUpdate = async (text) => {
    const id = sheetEntry.id
    try {
      await api.updateFood(id, text); setSheetEntry(null)
      await api.nutritionToday().then(setData)
      showToast('Обновлено ✓')
    } catch (e) { showToast('Ошибка: ' + e.message, true); throw e }
  }

  if (loading) return <div className="spinner">Загружаем питание...</div>
  if (err) return <div className="spinner" style={{ color: '#f87171' }}>{err}</div>

  const { meal_groups = [], totals, goals } = data || {}
  if (!totals || !goals) return <div className="spinner" style={{ color: '#f87171' }}>Ошибка загрузки данных</div>

  const remaining = Math.max(0, Math.round((goals.calories || 0) - (totals.calories || 0)))

  return (
    <div className="page" style={{ paddingBottom: 'calc(var(--nav-h) + 180px + var(--safe-bottom))' }}>
      {toast && <div className={`toast ${toast.isError ? 'toast-error' : 'toast-ok'}`}>{toast.msg}</div>}
      <FoodSheet entry={sheetEntry} onClose={() => setSheetEntry(null)} onDelete={handleDelete} onUpdate={handleUpdate} />

      {/* Header */}
      <div style={{ paddingBottom: 8 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text)' }}>Питание</div>
        <div style={{ fontSize: 13, color: 'var(--hint)', marginTop: 2 }}>{todayLabel()}</div>
      </div>

      {/* Summary ring + macros */}
      <div className="nutr-summary">
        <div className="nutr-top">
          <NutritionRing
            calories={totals.calories || 0}
            goalCalories={goals.calories || 1}
            protein={totals.protein || 0}
            goalProtein={goals.protein || 1}
          />
          <div className="nutr-macros">
            {[
              { label: 'Белки',   val: totals.protein, goal: goals.protein,  color: 'var(--blue)' },
              { label: 'Жиры',    val: totals.fat,     goal: goals.fat,      color: 'var(--orange)' },
              { label: 'Углев',   val: totals.carbs,   goal: goals.carbs,    color: 'var(--green)' },
            ].map(({ label, val, goal, color }) => (
              <div key={label} className="nm-row">
                <span className="nm-name" style={{ color }}>{label}</span>
                <div className="nm-bar-wrap">
                  <div className="nm-bar" style={{ width: `${goal > 0 ? Math.min((val/goal)*100, 100) : 0}%`, background: color }} />
                </div>
                <span className="nm-val">{Math.round(val || 0)} / {goal}г</span>
              </div>
            ))}
          </div>
        </div>
        <div className="kcal-goal">Осталось <span>{remaining} ккал</span> до цели</div>
      </div>

      {/* Meal groups */}
      {meal_groups.length > 0 ? (
        <>
          {meal_groups.map((group) => (
            <div key={group.meal_type} className="meal-group">
              <div className="meal-group-header">
                <div>
                  <div className="mgh-name">{group.icon} {group.label}</div>
                  {group.entries[0]?.time && <div className="mgh-time">{group.entries[0].time}</div>}
                </div>
                <div className="mgh-kcal">{Math.round(group.calories)} ккал</div>
              </div>
              {group.entries.map((e) => (
                <div key={e.id} className="meal-item">
                  <div className="mi-body">
                    <div className="mi-name">{e.description}</div>
                    <div className="mi-macros">
                      <span>Б {Math.round(e.protein)}г</span>
                      <span>Ж {Math.round(e.fat)}г</span>
                      <span>У {Math.round(e.carbs)}г</span>
                      <span>{Math.round(e.calories)} ккал</span>
                    </div>
                  </div>
                  <div className="mi-del" onClick={() => { haptic('light'); setSheetEntry(e) }}>⋮</div>
                </div>
              ))}
            </div>
          ))}
        </>
      ) : (
        <div className="meal-group" style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--hint)' }}>
          Ещё ничего не записано. Добавь первый приём пищи!
        </div>
      )}

      <NutritionDock onLogged={() => api.nutritionToday().then(setData)} />
    </div>
  )
}
