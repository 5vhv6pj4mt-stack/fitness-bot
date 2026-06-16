import { useEffect, useRef, useState } from 'react'
import { api, friendlyError } from '../api'
import { haptic } from '../tg'

const POLL_INTERVAL_MS = 2000
const POLL_MAX_ATTEMPTS = 90  // 3 минуты максимум

function WarningRow({ icon, text }) {
  if (!text) return null
  return (
    <div style={{
      display: 'flex', gap: 10, alignItems: 'flex-start',
      background: 'rgba(255,159,10,0.12)', borderRadius: 10,
      padding: '10px 12px', marginBottom: 8,
    }}>
      <span style={{ fontSize: 18, flexShrink: 0 }}>{icon}</span>
      <span style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--text)' }}>{text}</span>
    </div>
  )
}

function depthColor(depthStr) {
  if (!depthStr) return 'var(--hint)'
  if (depthStr.includes('отлично')) return 'var(--green)'
  if (depthStr.includes('хорошо')) return '#30d158'
  return '#ff9f0a'
}

function AnalysisResult({ result, onRetry, onClose }) {
  return (
    <>
      <div style={{
        background: 'var(--bg)', borderRadius: 14, padding: '14px 16px',
        marginBottom: 12, display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <div style={{ fontSize: 26, fontWeight: 700, color: depthColor(result.depth) }}>
            {Math.round((result.left_elbow_min_deg + result.right_elbow_min_deg) / 2)}°
          </div>
          <div style={{ fontSize: 10, color: 'var(--hint)' }}>мин. угол</div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--hint)', marginBottom: 2 }}>Глубина</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: depthColor(result.depth) }}>
            {result.depth}
          </div>
          <div style={{ fontSize: 12, color: 'var(--hint)', marginTop: 4 }}>
            Лев. {result.left_elbow_min_deg}° · Пр. {result.right_elbow_min_deg}°
          </div>
        </div>
      </div>

      <WarningRow icon="⚖️" text={result.symmetry_warning} />
      <WarningRow icon="↔️" text={result.trajectory_warning} />
      <WarningRow icon="🔙" text={result.back_warning} />

      {!result.symmetry_warning && !result.trajectory_warning && !result.back_warning && (
        <div style={{
          display: 'flex', gap: 10, alignItems: 'center',
          background: 'rgba(48,209,88,0.12)', borderRadius: 10,
          padding: '10px 12px', marginBottom: 8,
        }}>
          <span style={{ fontSize: 18 }}>✅</span>
          <span style={{ fontSize: 13, color: 'var(--text)' }}>Нарушений не обнаружено</span>
        </div>
      )}

      <div style={{
        background: 'rgba(10,132,255,0.12)', borderRadius: 12,
        padding: '12px 14px', marginTop: 4, marginBottom: 16,
      }}>
        <div style={{ fontSize: 11, color: 'var(--hint)', marginBottom: 4 }}>Рекомендация</div>
        <div style={{ fontSize: 14, lineHeight: 1.5 }}>{result.recommendation}</div>
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={onRetry}
          style={{
            flex: 1, background: 'var(--bg3)', border: 'none', borderRadius: 12,
            padding: '12px', fontSize: 13, color: 'var(--hint)', cursor: 'pointer',
          }}>
          Загрузить ещё
        </button>
        <button onClick={onClose}
          style={{
            flex: 2, background: 'var(--accent)', color: 'var(--accent-text)',
            border: 'none', borderRadius: 12, padding: '12px',
            fontSize: 14, fontWeight: 700, cursor: 'pointer',
          }}>
          Закрыть
        </button>
      </div>
    </>
  )
}

export default function DumbbellPressAnalysis({ onClose }) {
  const fileRef = useRef(null)
  const pollRef = useRef(null)
  const attemptsRef = useRef(0)

  // phase: idle | uploading | polling | result | error
  const [phase, setPhase] = useState('idle')
  const [uploadPct, setUploadPct] = useState(0)
  const [pollStatus, setPollStatus] = useState('pending')  // pending | processing
  const [result, setResult] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => () => clearInterval(pollRef.current), [])

  const stopPolling = () => clearInterval(pollRef.current)

  const startPolling = (taskId) => {
    attemptsRef.current = 0
    pollRef.current = setInterval(async () => {
      attemptsRef.current += 1
      if (attemptsRef.current > POLL_MAX_ATTEMPTS) {
        stopPolling()
        setErrorMsg('Превышено время ожидания — попробуй ещё раз')
        setPhase('error')
        return
      }
      try {
        const resp = await api.pressAnalysisStatus(taskId)
        if (resp.status === 'done') {
          stopPolling()
          const r = resp.result
          if (r.status === 'error') {
            setErrorMsg(r.message || 'Ошибка анализа')
            setPhase('error')
          } else {
            setResult(r)
            setPhase('result')
            haptic('heavy')
          }
        } else {
          setPollStatus(resp.status)  // pending | processing
        }
      } catch (e) {
        stopPolling()
        setErrorMsg(friendlyError(e))
        setPhase('error')
      }
    }, POLL_INTERVAL_MS)
  }

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    // сброс value чтобы повторный выбор того же файла тоже работал
    e.target.value = ''

    if (file.size > 20 * 1024 * 1024) {
      setErrorMsg('Файл слишком большой — максимум 20 МБ')
      setPhase('error')
      return
    }

    setPhase('uploading')
    setUploadPct(0)
    haptic('medium')

    try {
      const data = await api.uploadPressVideo(file, null, (pct) => setUploadPct(pct))
      // API теперь возвращает { task_id }
      if (!data.task_id) {
        setErrorMsg(data.message || 'Сервер не вернул task_id')
        setPhase('error')
        return
      }
      setPhase('polling')
      setPollStatus('pending')
      startPolling(data.task_id)
    } catch (err) {
      setErrorMsg(friendlyError(err))
      setPhase('error')
    }
  }

  const handleRetry = () => {
    stopPolling()
    setPhase('idle')
    setResult(null)
    setErrorMsg('')
    setUploadPct(0)
  }

  const pollLabel = pollStatus === 'processing'
    ? 'MediaPipe анализирует кадры...'
    : 'Задача в очереди...'

  return (
    <>
      <div onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 300 }} />

      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 301,
        background: 'var(--bg2)', borderRadius: '20px 20px 0 0',
        padding: '16px 0 36px', maxHeight: '80vh', overflowY: 'auto',
      }}>
        <div style={{ width: 36, height: 4, background: 'var(--bg4)', borderRadius: 2, margin: '0 auto 14px' }} />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 16px 14px' }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>📹 Анализ техники</div>
            <div style={{ fontSize: 12, color: 'var(--hint)', marginTop: 2 }}>Жим гантелей лёжа</div>
          </div>
          <button onClick={onClose}
            style={{ background: 'var(--bg3)', border: 'none', borderRadius: 10, padding: '6px 12px', color: 'var(--hint)', cursor: 'pointer', fontSize: 13 }}>
            ✕
          </button>
        </div>

        <div style={{ padding: '0 16px' }}>

          {/* ── IDLE ── */}
          {phase === 'idle' && (
            <>
              <div style={{
                background: 'var(--bg)', borderRadius: 14, padding: '20px 16px',
                textAlign: 'center', marginBottom: 16, color: 'var(--hint)', fontSize: 13, lineHeight: 1.7,
              }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>🎬</div>
                Загрузи видео тренировки (до 20 МБ).<br />
                Тело должно быть полностью в кадре.<br />
                Анализ занимает 20–60 секунд.
              </div>
              <input ref={fileRef} type="file" accept="video/*"
                style={{ display: 'none' }} onChange={handleFileChange} />
              <button onClick={() => fileRef.current?.click()}
                style={{
                  width: '100%', background: 'var(--accent)', color: 'var(--accent-text)',
                  border: 'none', borderRadius: 14, padding: '14px', fontSize: 15, fontWeight: 700, cursor: 'pointer',
                }}>
                Выбрать видео
              </button>
            </>
          )}

          {/* ── UPLOADING ── */}
          {phase === 'uploading' && (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <div style={{ fontSize: 32, marginBottom: 16 }}>📤</div>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 6 }}>Загружаем видео...</div>
              <div style={{ fontSize: 13, color: 'var(--hint)', marginBottom: 20 }}>{uploadPct}%</div>
              <div style={{ height: 6, background: 'var(--bg)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 3, background: 'var(--accent)',
                  width: `${uploadPct}%`, transition: 'width 0.25s',
                }} />
              </div>
            </div>
          )}

          {/* ── POLLING ── */}
          {phase === 'polling' && (
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <div style={{ fontSize: 36, marginBottom: 16 }}>🧠</div>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 6 }}>
                {pollStatus === 'processing' ? 'Анализируем технику...' : 'Ожидаем обработки...'}
              </div>
              <div style={{ fontSize: 13, color: 'var(--hint)', marginBottom: 24 }}>{pollLabel}</div>

              {/* Animated dots */}
              <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
                {[0, 1, 2].map(i => (
                  <div key={i} style={{
                    width: 10, height: 10, borderRadius: '50%',
                    background: 'var(--accent)', opacity: 0.7,
                    animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                  }} />
                ))}
              </div>
              <style>{`
                @keyframes bounce {
                  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
                  40% { transform: scale(1); opacity: 1; }
                }
              `}</style>

              <div style={{ fontSize: 11, color: 'var(--hint)', marginTop: 20 }}>
                Проверяем каждые 2 секунды · до {Math.ceil(POLL_MAX_ATTEMPTS * POLL_INTERVAL_MS / 60000)} мин
              </div>
            </div>
          )}

          {/* ── RESULT ── */}
          {phase === 'result' && result && (
            <AnalysisResult
              result={result}
              onRetry={handleRetry}
              onClose={onClose}
            />
          )}

          {/* ── ERROR ── */}
          {phase === 'error' && (
            <>
              <div style={{
                background: 'rgba(255,69,58,0.12)', borderRadius: 14,
                padding: '20px 16px', textAlign: 'center', marginBottom: 16,
              }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>⚠️</div>
                <div style={{ fontSize: 14, color: '#ff453a', fontWeight: 600, marginBottom: 4 }}>Ошибка</div>
                <div style={{ fontSize: 13, color: 'var(--hint)', lineHeight: 1.5 }}>{errorMsg}</div>
              </div>
              <button onClick={handleRetry}
                style={{
                  width: '100%', background: 'var(--accent)', color: 'var(--accent-text)',
                  border: 'none', borderRadius: 12, padding: '13px',
                  fontSize: 14, fontWeight: 700, cursor: 'pointer',
                }}>
                Попробовать ещё раз
              </button>
            </>
          )}

        </div>
      </div>
    </>
  )
}
