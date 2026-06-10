import { useEffect, useState } from 'react'
import { api } from '../api'
import { haptic } from '../tg'

// Inline editable row — тап открывает числовой ввод
function EditRow({ icon, iconBg, label, value, unit, field, onSave }) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState('')

  const open = () => { setVal(String(value || '')); setEditing(true); haptic('light') }
  const close = () => setEditing(false)
  const save = async () => {
    const num = parseFloat(val)
    if (!isNaN(num) && num > 0) { await onSave(field, num); haptic('medium') }
    setEditing(false)
  }

  return (
    <div>
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', cursor: 'pointer' }}
        onClick={open}
      >
        <div style={{ width: 32, height: 32, borderRadius: 8, background: iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>{icon}</div>
        <div style={{ flex: 1, fontSize: 15 }}>{label}</div>
        <div style={{ fontSize: 15, color: 'var(--hint)' }}>{value ? `${value} ${unit}` : '—'}</div>
        <div style={{ fontSize: 12, color: 'var(--bg4)' }}>›</div>
      </div>
      {editing && (
        <div style={{ padding: '0 16px 12px', display: 'flex', gap: 8 }}>
          <input
            type="number"
            value={val}
            onChange={(e) => setVal(e.target.value)}
            autoFocus
            style={{
              flex: 1, background: 'var(--bg3)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '8px 12px', color: 'var(--text)', fontSize: 15,
            }}
          />
          <button onClick={save} className="btn-primary" style={{ padding: '8px 16px' }}>✓</button>
          <button onClick={close} style={{ padding: '8px 12px', background: 'var(--bg3)', border: 'none', borderRadius: 10, color: 'var(--hint)', cursor: 'pointer' }}>✕</button>
        </div>
      )}
    </div>
  )
}

function Divider() {
  return <div style={{ height: 1, background: 'var(--sep)', margin: '0 16px' }} />
}

function SectionTitle({ children }) {
  return <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--hint)', textTransform: 'uppercase', letterSpacing: 0.5, padding: '16px 16px 6px' }}>{children}</div>
}

function StaticRow({ icon, iconBg, label, value, danger }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px' }}>
      <div style={{ width: 32, height: 32, borderRadius: 8, background: iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>{icon}</div>
      <div style={{ flex: 1, fontSize: 15, color: danger ? 'var(--red)' : 'var(--text)' }}>{label}</div>
      {value && <div style={{ fontSize: 15, color: 'var(--hint)' }}>{value}</div>}
      <div style={{ fontSize: 12, color: danger ? 'var(--red)' : 'var(--bg4)' }}>›</div>
    </div>
  )
}

export default function Profile({ onBack }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [toast, setToast] = useState(null)

  const showToast = (msg, isError = false) => {
    setToast({ msg, isError })
    setTimeout(() => setToast(null), 2500)
  }

  const load = () => {
    api.profileGet()
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleSave = async (field, value) => {
    try {
      await api.profileUpdate({ [field]: value })
      setData((prev) => ({ ...prev, [field]: value }))
      showToast('Сохранено ✓')
    } catch (e) {
      showToast('Ошибка: ' + e.message, true)
    }
  }

  if (loading) return <div className="spinner">Загружаем профиль...</div>
  if (err) return <div className="spinner" style={{ color: '#f87171' }}>{err}</div>
  if (!data) return null

  const initial = (data.name || '?')[0].toUpperCase()

  return (
    <div className="page">
      {toast && (
        <div className={`toast ${toast.isError ? 'toast-error' : 'toast-ok'}`}>{toast.msg}</div>
      )}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0 4px' }}>
        <button
          onClick={() => { haptic('light'); onBack?.() }}
          style={{ background: 'none', border: 'none', color: 'var(--blue)', fontSize: 16, cursor: 'pointer', padding: '4px 0' }}
        >
          ← Назад
        </button>
      </div>

      {/* Hero */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '12px 16px 16px' }}>
        <div style={{
          width: 72, height: 72, borderRadius: '50%', background: 'var(--blue)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 28, fontWeight: 700, color: '#fff', marginBottom: 10, position: 'relative',
        }}>
          {initial}
        </div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>{data.name}</div>
        <div style={{ display: 'flex', gap: 24, marginTop: 14 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{data.total_workouts}</div>
            <div style={{ fontSize: 12, color: 'var(--hint)', marginTop: 2 }}>тренировки</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--green)' }}>{data.weight} кг</div>
            <div style={{ fontSize: 12, color: 'var(--hint)', marginTop: 2 }}>вес тела</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--orange)' }}>{data.avg_rpe || '—'}</div>
            <div style={{ fontSize: 12, color: 'var(--hint)', marginTop: 2 }}>средний RPE</div>
          </div>
        </div>
      </div>

      {/* Параметры тела */}
      <SectionTitle>Параметры тела</SectionTitle>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <EditRow icon="⚖️" iconBg="rgba(10,132,255,.12)" label="Вес" value={data.weight} unit="кг" field="weight" onSave={handleSave} />
        <Divider />
        <EditRow icon="📏" iconBg="rgba(48,209,88,.12)" label="Рост" value={data.height} unit="см" field="height" onSave={handleSave} />
        <Divider />
        <EditRow icon="🎂" iconBg="rgba(255,159,10,.12)" label="Возраст" value={data.age} unit="лет" field="age" onSave={handleSave} />
      </div>

      {/* Цели питания */}
      <SectionTitle>Цели питания</SectionTitle>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <EditRow icon="🔥" iconBg="rgba(255,69,58,.12)" label="Калории" value={data.goal_calories} unit="ккал" field="goal_calories" onSave={handleSave} />
        <Divider />
        <EditRow icon="🥩" iconBg="rgba(10,132,255,.12)" label="Белки" value={data.goal_protein} unit="г" field="goal_protein" onSave={handleSave} />
        <Divider />
        <EditRow icon="🫒" iconBg="rgba(255,159,10,.12)" label="Жиры" value={data.goal_fat} unit="г" field="goal_fat" onSave={handleSave} />
        <Divider />
        <EditRow icon="🌾" iconBg="rgba(48,209,88,.12)" label="Углеводы" value={data.goal_carbs} unit="г" field="goal_carbs" onSave={handleSave} />
      </div>

      {/* Программа */}
      <SectionTitle>Программа тренировок</SectionTitle>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <StaticRow icon="🎯" iconBg="rgba(191,90,242,.12)" label="Цель" value={data.goal_label} />
        <Divider />
        <StaticRow icon="🏋️" iconBg="rgba(48,209,88,.12)" label="Оборудование" value={data.equipment_label} />
        <Divider />
        <StaticRow icon="📅" iconBg="rgba(10,132,255,.12)" label="Тренировок в неделю" value={`${data.days_per_week} дня`} />
        <Divider />
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', cursor: 'pointer' }}
          onClick={() => haptic('light')}
        >
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(255,159,10,.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>🔄</div>
          <div style={{ flex: 1, fontSize: 15 }}>Пересоздать программу</div>
          <div style={{ fontSize: 12, color: 'var(--bg4)' }}>›</div>
        </div>
      </div>

      {/* Прочее */}
      <SectionTitle>Прочее</SectionTitle>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', cursor: 'pointer' }}
          onClick={() => { haptic('light'); window.Telegram?.WebApp?.openTelegramLink('https://t.me/stat_sila_bot') }}
        >
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(10,132,255,.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>🔗</div>
          <div style={{ flex: 1, fontSize: 15 }}>Открыть бота в Telegram</div>
          <div style={{ fontSize: 12, color: 'var(--bg4)' }}>›</div>
        </div>
        <Divider />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', cursor: 'pointer' }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(255,69,58,.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>🗑</div>
          <div style={{ flex: 1, fontSize: 15, color: 'var(--red)' }}>Удалить аккаунт</div>
          <div style={{ fontSize: 12, color: 'var(--red)' }}>›</div>
        </div>
      </div>

      <div style={{ height: 16 }} />
    </div>
  )
}
