import { useEffect, useState, useRef, useCallback } from 'react'
import { api } from '../api'
import { haptic } from '../tg'
import ProgressBar from '../components/ProgressBar'

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

// ── Water strip ───────────────────────────────────────────────────────────────
function WaterStrip({ onAdd }) {
  const [water, setWater] = useState(null)

  useEffect(() => {
    api.waterToday().then(setWater).catch(() => {})
  }, [])

  const handleAdd = async () => {
    haptic('light')
    try {
      const r = await api.waterAdd()
      setWater(r)
    } catch {}
  }

  if (!water) return null
  const { glasses, goal } = water

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderTop: '1px solid var(--sep)' }}>
      <span style={{ fontSize: 16 }}>💧</span>
      <div style={{ display: 'flex', gap: 4, flex: 1, flexWrap: 'wrap' }}>
        {Array.from({ length: goal }).map((_, i) => (
          <div key={i} style={{
            width: 18, height: 18, borderRadius: 4,
            background: i < glasses ? 'var(--blue)' : 'var(--bg3)',
            transition: 'background 0.2s',
          }} />
        ))}
      </div>
      <span style={{ fontSize: 12, color: 'var(--hint)', whiteSpace: 'nowrap' }}>{glasses} из {goal}</span>
      <button
        onClick={handleAdd}
        style={{
          background: 'rgba(10,132,255,0.15)', border: 'none', borderRadius: 8,
          color: 'var(--blue)', fontSize: 12, fontWeight: 600, padding: '4px 10px', cursor: 'pointer',
        }}
      >
        + стакан
      </button>
    </div>
  )
}

// ── Nutrition dock (fixed above navbar) ──────────────────────────────────────
function NutritionDock({ onLogged }) {
  const [mode, setMode] = useState(null) // null | 'text' | 'voice'
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
      await fn()
      onLogged()
      setText('')
      setMode(null)
      haptic('medium')
    } catch (e) {
      haptic('heavy')
      alert('Ошибка: ' + e.message)
    } finally {
      setSending(false)
    }
  }

  const handleText = () => send(() => api.logFood(text.trim()))

  const handlePhotoChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''
    const fd = new FormData()
    fd.append('file', file)
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
        const fd = new FormData()
        fd.append('file', blob, 'voice.webm')
        await send(() => api.logVoice(fd))
        setRecording(false)
      }
      mr.start()
      mediaRef.current = mr
      setRecording(true)
    } catch {
      alert('Нет доступа к микрофону')
    }
  }

  const stopVoice = () => { mediaRef.current?.stop() }

  const toggleMode = (m) => {
    haptic('light')
    if (mode === m) { setMode(null); return }
    setMode(m)
    if (m === 'text') setTimeout(() => textareaRef.current?.focus(), 100)
    if (m === 'voice') startVoice()
  }

  return (
    <div style={{
      position: 'fixed', bottom: 52, left: 0, right: 0,
      background: 'var(--bg2)', borderTop: '1px solid var(--sep)', zIndex: 99,
    }}>
      {/* Quick chips */}
      {templates.length > 0 && mode === null && (
        <div style={{ display: 'flex', gap: 6, overflowX: 'auto', padding: '8px 12px 0', scrollbarWidth: 'none' }}>
          {templates.slice(0, 8).map((t) => (
            <button
              key={t.description}
              onClick={() => { setText(t.description); setMode('text'); setTimeout(() => textareaRef.current?.focus(), 100) }}
              style={{
                background: 'var(--bg3)', border: 'none', borderRadius: 16,
                padding: '5px 12px', fontSize: 12, color: 'var(--text)',
                cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
              }}
            >
              {t.description}
              <span style={{ color: 'var(--hint)', marginLeft: 4 }}>{t.calories}</span>
            </button>
          ))}
        </div>
      )}

      {/* Text expand */}
      {mode === 'text' && (
        <div style={{ padding: '10px 12px 8px', display: 'flex', gap: 8 }}>
          <textarea
            ref={textareaRef}
            rows={2}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Что съел? Например: куриная грудка 200г, рис..."
            disabled={sending}
            style={{
              flex: 1, background: 'var(--bg3)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '8px 12px', color: 'var(--text)',
              fontSize: 14, resize: 'none', fontFamily: 'inherit',
            }}
          />
          <button
            onClick={handleText}
            disabled={!text.trim() || sending}
            style={{
              width: 40, background: sending ? 'var(--bg3)' : 'var(--blue)',
              border: 'none', borderRadius: 10, color: '#fff', fontSize: 18,
              cursor: 'pointer', flexShrink: 0,
            }}
          >
            {sending ? '…' : '→'}
          </button>
        </div>
      )}

      {/* Voice panel */}
      {mode === 'voice' && (
        <div style={{ padding: '12px', display: 'flex', alignItems: 'center', gap: 12 }}>
          {recording ? (
            <>
              <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
                {[0,1,2,3,4].map((i) => (
                  <div key={i} style={{
                    width: 4, background: 'var(--blue)', borderRadius: 2,
                    animation: `voiceWave 0.8s ease-in-out ${i * 0.1}s infinite alternate`,
                    height: 16,
                  }} />
                ))}
              </div>
              <span style={{ flex: 1, fontSize: 13, color: 'var(--hint)' }}>Слушаю...</span>
              <button onClick={stopVoice} style={{
                background: 'rgba(255,69,58,0.15)', border: 'none', borderRadius: 8,
                color: 'var(--red)', fontSize: 13, fontWeight: 600, padding: '6px 14px', cursor: 'pointer',
              }}>
                ⏹ Стоп
              </button>
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

      {/* 3 input buttons */}
      <div style={{ display: 'flex', padding: '6px 12px 8px', gap: 8 }}>
        <div style={{ flex: 1, fontSize: 13, color: 'var(--hint)', display: 'flex', alignItems: 'center' }}>
          Добавить приём пищи
        </div>
        <input ref={fileRef} type="file" accept="image/*" capture="environment" style={{ display: 'none' }} onChange={handlePhotoChange} />
        {[
          { key: 'photo', icon: '📷', label: 'Фото', color: 'var(--orange)', action: () => { haptic('light'); fileRef.current?.click() } },
          { key: 'voice', icon: '🎤', label: 'Голос', color: 'var(--blue)', action: () => toggleMode('voice') },
          { key: 'text', icon: '✏️', label: 'Текст', color: 'var(--green)', action: () => toggleMode('text') },
        ].map(({ key, icon, label, color, action }) => (
          <button
            key={key}
            onClick={action}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
              background: mode === key ? `${color}22` : 'var(--bg3)',
              border: mode === key ? `1px solid ${color}44` : '1px solid transparent',
              borderRadius: 10, padding: '6px 14px', cursor: 'pointer', minWidth: 56,
            }}
          >
            <span style={{ fontSize: 17 }}>{icon}</span>
            <span style={{ fontSize: 10, color: mode === key ? color : 'var(--hint)' }}>{label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Main Nutrition page ───────────────────────────────────────────────────────
export default function Nutrition() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [toast, setToast] = useState(null)
  const [sheetEntry, setSheetEntry] = useState(null)

  const showToast = (msg, isError = false) => {
    setToast({ msg, isError })
    setTimeout(() => setToast(null), 3000)
  }

  const load = useCallback(() => {
    api.nutritionToday()
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleDelete = async () => {
    const id = sheetEntry.id
    setSheetEntry(null)
    try {
      await api.deleteFood(id)
      await api.nutritionToday().then(setData)
      showToast('Приём удалён')
    } catch (e) { showToast('Ошибка: ' + e.message, true) }
  }

  const handleUpdate = async (text) => {
    const id = sheetEntry.id
    try {
      await api.updateFood(id, text)
      setSheetEntry(null)
      await api.nutritionToday().then(setData)
      showToast('Обновлено ✓')
    } catch (e) { showToast('Ошибка: ' + e.message, true); throw e }
  }

  if (loading) return <div className="spinner">Загружаем питание...</div>
  if (err) return <div className="spinner" style={{ color: '#f87171' }}>{err}</div>

  const { meal_groups = [], totals, goals } = data || {}
  if (!totals || !goals) return <div className="spinner" style={{ color: '#f87171' }}>Ошибка загрузки данных</div>

  return (
    <div className="page" style={{ paddingBottom: 200 }}>
      {toast && <div className={`toast ${toast.isError ? 'toast-error' : 'toast-ok'}`}>{toast.msg}</div>}

      <FoodSheet entry={sheetEntry} onClose={() => setSheetEntry(null)} onDelete={handleDelete} onUpdate={handleUpdate} />

      <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 16 }}>🍽 Питание</div>

      {/* КБЖУ прогресс */}
      <div className="card">
        <ProgressBar label="🔥 Калории" current={totals.calories} goal={goals.calories} color="#f59e0b" />
        <ProgressBar label="🥩 Белок" current={totals.protein} goal={goals.protein} color="#3b82f6" />
        <ProgressBar label="🌾 Углеводы" current={totals.carbs} goal={goals.carbs} color="#10b981" />
        <ProgressBar label="🫒 Жиры" current={totals.fat} goal={goals.fat} color="#8b5cf6" />
      </div>

      {/* Список за день */}
      {meal_groups.length > 0 ? (
        <>
          {meal_groups.map((group) => (
            <div key={group.meal_type} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div className="section-title" style={{ marginBottom: 0 }}>{group.icon} {group.label}</div>
                <div style={{ fontSize: 13, color: 'var(--hint)' }}>{Math.round(group.calories)} ккал</div>
              </div>
              {group.entries.map((e) => (
                <div key={e.id} className="food-entry">
                  <div className="food-entry-body">
                    <div className="food-entry-name">{e.description}</div>
                    <div className="food-entry-kcal">{e.calories} ккал · Б:{e.protein} У:{e.carbs} Ж:{e.fat}</div>
                  </div>
                  <div className="food-entry-right">
                    <div className="food-entry-time">{e.time}</div>
                    <button className="food-entry-more" onClick={() => { haptic('light'); setSheetEntry(e) }}>⋮</button>
                  </div>
                </div>
              ))}
            </div>
          ))}
          <div className="card" style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 16px', fontSize: 14, fontWeight: 600 }}>
            <span>ИТОГО за день</span>
            <span>{Math.round(totals.calories)} ккал</span>
          </div>
        </>
      ) : (
        <div className="card" style={{ textAlign: 'center', color: 'var(--hint)', padding: '24px 16px' }}>
          Ещё ничего не записано. Добавь первый приём пищи!
        </div>
      )}

      <NutritionDock onLogged={() => api.nutritionToday().then(setData)} />
    </div>
  )
}
