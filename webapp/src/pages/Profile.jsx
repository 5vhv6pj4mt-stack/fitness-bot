import { useEffect, useState } from 'react'
import { api, friendlyError } from '../api'
import { haptic, setThemeOverride, getThemeOverride } from '../tg'
import { playSound, getRestSound, setRestSound, SOUND_OPTIONS } from '../sounds'

const MONTHS_RU = ['январе','феврале','марте','апреле','мае','июне','июле','августе','сентябре','октябре','ноябре','декабре']
const MONTHS_SHORT = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']

function memberSince(createdAt) {
  if (!createdAt) return ''
  const d = new Date(createdAt.replace(' ', 'T'))
  if (isNaN(d)) return ''
  return `В приложении с ${MONTHS_RU[d.getMonth()]} ${d.getFullYear()}`
}

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
  const onKey = (e) => { if (e.key === 'Enter') save() }

  return (
    <div>
      <div className="sr" onClick={open}>
        <div className="sr-icon" style={{ background: iconBg }}>{icon}</div>
        <div className="sr-label">{label}</div>
        <div className="sr-value">{value ? `${value} ${unit}` : '—'}</div>
        <div className="sr-chevron">›</div>
      </div>
      {editing && (
        <div style={{ padding: '0 16px 12px', display: 'flex', gap: 8, borderTop: '1px solid var(--sep)' }}>
          <input
            type="number" value={val} onChange={(e) => setVal(e.target.value)}
            onKeyDown={onKey} autoFocus
            style={{
              flex: 1, background: 'var(--bg3)', border: '1px solid var(--sep)',
              borderRadius: 10, padding: '8px 12px', color: 'var(--text)', fontSize: 15, outline: 'none',
            }}
          />
          <button onClick={save} className="btn-primary" style={{ width: 'auto', padding: '8px 16px', borderRadius: 10, fontSize: 14 }}>✓</button>
          <button onClick={close} style={{ padding: '8px 12px', background: 'var(--bg3)', border: 'none', borderRadius: 10, color: 'var(--hint)', cursor: 'pointer' }}>✕</button>
        </div>
      )}
    </div>
  )
}

function Toggle({ on, onChange }) {
  return (
    <button
      className={`toggle${on ? ' on' : ''}`}
      onClick={() => { haptic('light'); onChange(!on) }}
    />
  )
}

function TzPicker({ value, onClose, onSelect }) {
  const offsets = [-12,-11,-10,-9,-8,-7,-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14]
  return (
    <>
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 200 }} onClick={onClose} />
      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0,
        background: 'var(--bg2)', borderRadius: '20px 20px 0 0',
        padding: '16px 0 32px', zIndex: 201, maxHeight: '60vh', overflowY: 'auto',
      }}>
        <div style={{ width: 36, height: 4, background: 'var(--bg4)', borderRadius: 2, margin: '0 auto 16px' }} />
        <div style={{ fontSize: 16, fontWeight: 700, textAlign: 'center', marginBottom: 12, color: 'var(--text)' }}>Часовой пояс</div>
        {offsets.map((off) => {
          const label = off >= 0 ? `UTC+${off}` : `UTC${off}`
          return (
            <div key={off}
              onClick={() => { onSelect(off); onClose() }}
              style={{
                padding: '13px 20px', fontSize: 15,
                color: off === value ? 'var(--blue)' : 'var(--text)',
                fontWeight: off === value ? 700 : 400,
                borderBottom: '1px solid var(--sep)', cursor: 'pointer',
              }}
            >
              {label}
            </div>
          )
        })}
      </div>
    </>
  )
}

export default function Profile({ onBack }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [toast, setToast] = useState(null)
  const [showTzPicker, setShowTzPicker] = useState(false)
  const [darkMode, setDarkMode] = useState(() => {
    const override = getThemeOverride()
    if (override) return override === 'dark'
    return !document.documentElement.classList.contains('tg-light')
  })
  const [restSound, setRestSoundState] = useState(() => getRestSound())

  const showToast = (msg, isError = false) => {
    setToast({ msg, isError })
    setTimeout(() => setToast(null), 2500)
  }

  const load = () => {
    api.profileGet()
      .then(d => {
        setData(d)
        localStorage.setItem('press_analysis_enabled', d.press_analysis_enabled ? '1' : '0')
      })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const save = async (field, value) => {
    setData((prev) => ({ ...prev, [field]: value }))
    try {
      await api.profileUpdate({ [field]: value })
      showToast('Сохранено ✓')
    } catch (e) {
      setData((prev) => ({ ...prev, [field]: typeof value === 'boolean' ? !value : prev[field] }))
      showToast(friendlyError(e), true)
    }
  }

  if (loading) return <div className="spinner">Загружаем профиль...</div>
  if (err) return <div className="spinner" style={{ color: '#f87171' }}>{err}</div>
  if (!data) return null

  const initial = (data.name || '?')[0].toUpperCase()
  const tz = data.utc_offset ?? 7
  const tzLabel = tz >= 0 ? `UTC+${tz}` : `UTC${tz}`

  return (
    <div className="page">
      {toast && <div className={`toast ${toast.isError ? 'toast-error' : 'toast-ok'}`}>{toast.msg}</div>}
      {showTzPicker && (
        <TzPicker value={tz} onClose={() => setShowTzPicker(false)} onSelect={(v) => save('utc_offset', v)} />
      )}

      {/* Назад */}
      <div style={{ padding: '4px 0 8px' }}>
        <button
          onClick={() => { haptic('light'); onBack?.() }}
          style={{ background: 'none', border: 'none', color: 'var(--blue)', fontSize: 16, cursor: 'pointer', padding: '4px 0' }}
        >
          ← Назад
        </button>
      </div>

      {/* Profile hero */}
      <div className="profile-hero">
        <div className="profile-avatar-big">{initial}</div>
        <div className="profile-name">{data.name}</div>
        <div className="profile-since">{memberSince(data.created_at)}</div>
        <div className="profile-stats">
          <div className="ps-item">
            <div className="ps-val">{data.total_workouts}</div>
            <div className="ps-label">тренировки</div>
          </div>
          <div className="ps-item">
            <div className="ps-val" style={{ color: 'var(--green)' }}>{data.weight ? `${data.weight} кг` : '—'}</div>
            <div className="ps-label">вес тела</div>
          </div>
          <div className="ps-item">
            <div className="ps-val" style={{ color: 'var(--orange)' }}>{data.avg_rpe || '—'}</div>
            <div className="ps-label">средний RPE</div>
          </div>
        </div>
      </div>

      {/* Параметры тела */}
      <div className="settings-group">
        <div className="sg-title">Параметры тела</div>
        <EditRow icon="⚖️" iconBg="rgba(10,132,255,.12)" label="Вес" value={data.weight} unit="кг" field="weight" onSave={save} />
        <EditRow icon="📏" iconBg="rgba(48,209,88,.12)" label="Рост" value={data.height} unit="см" field="height" onSave={save} />
        <EditRow icon="🎂" iconBg="rgba(255,159,10,.12)" label="Возраст" value={data.age} unit="лет" field="age" onSave={save} />
      </div>

      {/* Цели питания */}
      <div className="settings-group">
        <div className="sg-title">Цели питания</div>
        <EditRow icon="🔥" iconBg="rgba(255,69,58,.12)" label="Калории" value={data.goal_calories} unit="ккал" field="goal_calories" onSave={save} />
        <EditRow icon="🥩" iconBg="rgba(10,132,255,.12)" label="Белки" value={data.goal_protein} unit="г" field="goal_protein" onSave={save} />
        <EditRow icon="🫒" iconBg="rgba(255,159,10,.12)" label="Жиры" value={data.goal_fat} unit="г" field="goal_fat" onSave={save} />
        <EditRow icon="🌾" iconBg="rgba(48,209,88,.12)" label="Углеводы" value={data.goal_carbs} unit="г" field="goal_carbs" onSave={save} />
      </div>

      {/* Программа тренировок */}
      <div className="settings-group">
        <div className="sg-title">Программа тренировок</div>
        <div className="sr" style={{ cursor: 'default' }}>
          <div className="sr-icon" style={{ background: 'rgba(191,90,242,.12)' }}>🎯</div>
          <div className="sr-label">Цель</div>
          <div className="sr-value">{data.goal_label || data.goal}</div>
        </div>
        <div className="sr" style={{ cursor: 'default' }}>
          <div className="sr-icon" style={{ background: 'rgba(48,209,88,.12)' }}>🏋️</div>
          <div className="sr-label">Оборудование</div>
          <div className="sr-value">{data.equipment_label || data.equipment}</div>
        </div>
        <div className="sr" style={{ cursor: 'default' }}>
          <div className="sr-icon" style={{ background: 'rgba(10,132,255,.12)' }}>📅</div>
          <div className="sr-label">Тренировок в неделю</div>
          <div className="sr-value">{data.days_per_week} дн.</div>
        </div>
        <div className="sr" onClick={() => { haptic('light'); setShowTzPicker(true) }}>
          <div className="sr-icon" style={{ background: 'rgba(100,100,100,.12)' }}>🕐</div>
          <div className="sr-label">Часовой пояс</div>
          <div className="sr-value">{tzLabel}</div>
          <div className="sr-chevron">›</div>
        </div>
        <div className="sr" onClick={() => haptic('light')}>
          <div className="sr-icon" style={{ background: 'rgba(255,159,10,.12)' }}>🔄</div>
          <div className="sr-label">Пересоздать программу</div>
          <div className="sr-chevron">›</div>
        </div>
      </div>

      {/* Вода */}
      <div className="settings-group">
        <div className="sg-title">Вода</div>
        <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12, borderTop: '1px solid var(--sep)' }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <div className="sr-icon" style={{ background: 'rgba(10,132,255,.12)', marginRight: 12 }}>💧</div>
            <div className="sr-label">Напоминать о воде</div>
            <Toggle on={data.notif_water ?? true} onChange={(v) => save('notif_water', v)} />
          </div>
          {(data.notif_water ?? true) && (
            <div style={{ paddingLeft: 44, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <div style={{ fontSize: 12, color: 'var(--hint)', marginBottom: 6 }}>Цель в день</div>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[6, 8, 10, 12].map((n) => (
                    <button key={n} className={`wset-chip${(data.water_goal || 8) === n ? ' active' : ''}`}
                      onClick={() => save('water_goal', n)}>
                      {n} ст.
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--hint)', marginBottom: 6 }}>Напоминать каждые</div>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[1, 2, 3].map((h) => (
                    <button key={h} className={`wset-chip${(data.water_interval || 2) === h ? ' active' : ''}`}
                      onClick={() => save('water_interval', h)}>
                      {h} ч
                    </button>
                  ))}
                </div>
              </div>
              <div style={{ fontSize: 12, color: 'var(--hint)', lineHeight: 1.5 }}>
                Бот отправит тихое уведомление в Telegram.<br />Не беспокоит ночью (с 22:00 до 8:00).
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Уведомления */}
      <div className="settings-group">
        <div className="sg-title">Уведомления</div>
        <div className="sr">
          <div className="sr-icon" style={{ background: 'rgba(255,159,10,.12)' }}>🌅</div>
          <div className="sr-label">Напоминание о завтраке</div>
          <Toggle on={!!data.notif_breakfast} onChange={(v) => save('notif_breakfast', v)} />
        </div>
        <div className="sr">
          <div className="sr-icon" style={{ background: 'rgba(10,132,255,.12)' }}>💪</div>
          <div className="sr-label">Напоминание о тренировке</div>
          <Toggle on={!!data.notif_workout} onChange={(v) => save('notif_workout', v)} />
        </div>
        <div className="sr">
          <div className="sr-icon" style={{ background: 'rgba(48,209,88,.12)' }}>🌙</div>
          <div className="sr-label">Вечерний итог дня</div>
          <Toggle on={!!data.notif_evening} onChange={(v) => save('notif_evening', v)} />
        </div>
      </div>

      {/* Экспериментальное */}
      <div className="settings-group">
        <div className="sg-title">Экспериментальное</div>
        <div className="sr">
          <div className="sr-icon" style={{ background: 'rgba(48,209,88,.12)' }}>📹</div>
          <div style={{ flex: 1 }}>
            <div className="sr-label">Анализ техники жима гантелей</div>
            <div style={{ fontSize: 11, color: 'var(--hint)', marginTop: 2 }}>
              Загрузи видео — AI оценит глубину, симметрию и траекторию
            </div>
          </div>
          <Toggle
            on={!!data.press_analysis_enabled}
            onChange={(v) => {
              localStorage.setItem('press_analysis_enabled', v ? '1' : '0')
              save('press_analysis_enabled', v)
            }}
          />
        </div>
      </div>

      {/* Прочее */}
      <div className="settings-group">
        <div className="sg-title">Прочее</div>
        <div className="sr">
          <div className="sr-icon" style={{ background: 'rgba(100,100,100,.12)' }}>🌙</div>
          <div className="sr-label">Тёмная тема</div>
          <Toggle on={darkMode} onChange={(v) => {
            setDarkMode(v)
            setThemeOverride(v ? 'dark' : 'light')
          }} />
        </div>
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--sep)' }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
            <div className="sr-icon" style={{ background: 'rgba(255,159,10,.12)', marginRight: 12 }}>🔔</div>
            <div className="sr-label">Звук конца отдыха</div>
          </div>
          <div style={{ display: 'flex', gap: 8, paddingLeft: 44 }}>
            {SOUND_OPTIONS.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  haptic('light')
                  setRestSound(s.id)
                  setRestSoundState(s.id)
                  playSound(s.id)
                }}
                style={{
                  flex: 1, padding: '8px 4px', borderRadius: 10, fontSize: 12, fontWeight: 600,
                  border: restSound === s.id ? '2px solid var(--accent)' : '2px solid var(--sep)',
                  background: restSound === s.id ? 'rgba(10,132,255,.12)' : 'var(--bg3)',
                  color: restSound === s.id ? 'var(--accent)' : 'var(--text)',
                  cursor: 'pointer', textAlign: 'center', lineHeight: 1.3,
                }}
              >
                <div>{s.label}</div>
                <div style={{ fontSize: 10, color: 'var(--hint)', marginTop: 2 }}>{s.desc}</div>
              </button>
            ))}
          </div>
        </div>
        <div className="sr" onClick={() => { haptic('light'); window.Telegram?.WebApp?.openTelegramLink('https://t.me/stat_sila_bot') }}>
          <div className="sr-icon" style={{ background: 'rgba(48,209,88,.12)' }}>🔗</div>
          <div className="sr-label">Открыть бота в Telegram</div>
          <div className="sr-chevron">›</div>
        </div>
        <div className="sr sr-danger">
          <div className="sr-icon" style={{ background: 'rgba(255,69,58,.1)' }}>🗑</div>
          <div className="sr-label">Удалить аккаунт</div>
          <div className="sr-chevron" style={{ color: 'var(--red)' }}>›</div>
        </div>
      </div>

      <div style={{ height: 16 }} />
    </div>
  )
}
