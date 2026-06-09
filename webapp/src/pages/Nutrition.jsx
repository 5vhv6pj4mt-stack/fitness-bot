import { useEffect, useState, useRef } from 'react'
import { api } from '../api'
import { haptic } from '../tg'
import ProgressBar from '../components/ProgressBar'

// ── Food action sheet ─────────────────────────────────────────────────────────
function FoodSheet({ entry, onClose, onDelete, onUpdate }) {
  const [editMode, setEditMode] = useState(false)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (entry) {
      setEditMode(false)
      setText(entry.description || '')
    }
  }, [entry?.id])

  if (!entry) return null

  const doUpdate = async () => {
    if (!text.trim() || saving) return
    setSaving(true)
    haptic('medium')
    await onUpdate(text.trim())
    setSaving(false)
  }

  const doDelete = () => {
    haptic('heavy')
    onDelete()
  }

  return (
    <>
      <div className="fs-overlay" onClick={onClose} />
      <div className="fs-sheet">
        <div className="fs-handle" />

        {editMode && (
          <div className="fs-edit-wrap">
            <div className="fs-edit-label">Описание блюда</div>
            <textarea
              className="fs-edit-input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={3}
              autoFocus
            />
            <button
              className="btn-primary"
              style={{ marginTop: 10 }}
              disabled={saving || !text.trim()}
              onClick={doUpdate}
            >
              {saving ? 'Пересчитываю КБЖУ...' : 'Сохранить'}
            </button>
            <div className="fs-sep" style={{ marginTop: 16 }} />
          </div>
        )}

        <div className="fs-item" onClick={() => setEditMode(!editMode)}>
          <span className="fs-icon">✏️</span>
          Изменить описание
        </div>
        <div className="fs-sep" />
        <div className="fs-item fs-danger" onClick={doDelete}>
          <span className="fs-icon">🗑</span>
          Удалить
        </div>
      </div>
    </>
  )
}

// ── Main Nutrition page ───────────────────────────────────────────────────────
export default function Nutrition() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [foodText, setFoodText] = useState('')
  const [sending, setSending] = useState(false)
  const [toast, setToast] = useState(null)
  const [sheetEntry, setSheetEntry] = useState(null)
  const inputRef = useRef(null)

  const showToast = (msg, isError = false) => {
    setToast({ msg, isError })
    setTimeout(() => setToast(null), 3000)
  }

  const load = () => {
    setLoading(true)
    api.nutritionToday()
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleLog = async () => {
    if (!foodText.trim() || sending) return
    setSending(true)
    haptic('light')
    try {
      await api.logFood(foodText.trim())
      setFoodText('')
      await api.nutritionToday().then(setData)
      haptic('medium')
      showToast('Приём пищи записан ✓')
    } catch (e) {
      showToast('Ошибка: ' + e.message, true)
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleLog()
    }
  }

  const handleDelete = async () => {
    const id = sheetEntry.id
    setSheetEntry(null)
    try {
      await api.deleteFood(id)
      await api.nutritionToday().then(setData)
      showToast('Приём удалён')
    } catch (e) {
      showToast('Ошибка: ' + e.message, true)
    }
  }

  const handleUpdate = async (text) => {
    const id = sheetEntry.id
    try {
      await api.updateFood(id, text)
      setSheetEntry(null)
      await api.nutritionToday().then(setData)
      showToast('Обновлено ✓')
    } catch (e) {
      showToast('Ошибка: ' + e.message, true)
      throw e
    }
  }

  if (loading) return <div className="spinner">Загружаем питание...</div>
  if (err) return <div className="spinner" style={{ color: '#f87171' }}>{err}</div>

  const { entries, totals, goals } = data

  return (
    <div className="page">
      {toast && (
        <div className={`toast ${toast.isError ? 'toast-error' : 'toast-ok'}`}>
          {toast.msg}
        </div>
      )}

      <FoodSheet
        entry={sheetEntry}
        onClose={() => setSheetEntry(null)}
        onDelete={handleDelete}
        onUpdate={handleUpdate}
      />

      <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 16 }}>🍽 Питание</div>

      {/* КБЖУ прогресс */}
      <div className="card">
        <ProgressBar label="🔥 Калории" current={totals.calories} goal={goals.calories} color="#f59e0b" />
        <ProgressBar label="🥩 Белок" current={totals.protein} goal={goals.protein} color="#3b82f6" />
        <ProgressBar label="🌾 Углеводы" current={totals.carbs} goal={goals.carbs} color="#10b981" />
        <ProgressBar label="🫒 Жиры" current={totals.fat} goal={goals.fat} color="#8b5cf6" />
      </div>

      {/* Добавить еду */}
      <div className="card">
        <div className="section-title">Добавить приём пищи</div>
        <div className="food-input-row">
          <input
            ref={inputRef}
            className="food-text-input"
            placeholder="200г куриной грудки, рис..."
            value={foodText}
            onChange={(e) => setFoodText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
          />
          <button
            className="food-send-btn"
            disabled={!foodText.trim() || sending}
            onClick={handleLog}
          >
            {sending ? '...' : '→'}
          </button>
        </div>
        <div style={{ fontSize: 12, color: 'var(--hint)', marginTop: 8 }}>
          ИИ подсчитает КБЖУ автоматически
        </div>
      </div>

      {/* Список за день */}
      {entries.length > 0 ? (
        <div className="card">
          <div className="section-title">Сегодня</div>
          {entries.map((e) => (
            <div key={e.id} className="food-entry">
              <div className="food-entry-body">
                <div className="food-entry-name">{e.description}</div>
                <div className="food-entry-kcal">
                  {e.calories} ккал · Б:{e.protein} У:{e.carbs} Ж:{e.fat}
                </div>
              </div>
              <div className="food-entry-right">
                <div className="food-entry-time">{e.time}</div>
                <button
                  className="food-entry-more"
                  onClick={() => { haptic('light'); setSheetEntry(e) }}
                >
                  ⋮
                </button>
              </div>
            </div>
          ))}
          <div style={{
            display: 'flex', justifyContent: 'space-between',
            paddingTop: 10, marginTop: 4,
            borderTop: '1px solid rgba(255,255,255,0.08)',
            fontSize: 14, fontWeight: 600,
          }}>
            <span>ИТОГО</span>
            <span>{Math.round(totals.calories)} ккал</span>
          </div>
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', color: 'var(--hint)', padding: '24px 16px' }}>
          Ещё ничего не записано. Добавь первый приём пищи!
        </div>
      )}
    </div>
  )
}
