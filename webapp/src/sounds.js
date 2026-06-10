// Web Audio API sounds for rest timer. No files needed.

let _ctx = null
function ctx() {
  if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)()
  return _ctx
}

function tone(freq, start, dur, gain = 0.35, type = 'sine') {
  const ac = ctx()
  const osc = ac.createOscillator()
  const g = ac.createGain()
  osc.type = type
  osc.frequency.value = freq
  g.gain.setValueAtTime(0, ac.currentTime + start)
  g.gain.linearRampToValueAtTime(gain, ac.currentTime + start + 0.01)
  g.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + start + dur)
  osc.connect(g)
  g.connect(ac.destination)
  osc.start(ac.currentTime + start)
  osc.stop(ac.currentTime + start + dur + 0.05)
}

const SOUNDS = {
  // Короткий чистый сигнал — классический таймер
  beep: () => { tone(880, 0, 0.25, 0.3, 'square') },
  // Мягкий колокол — приятный звон
  bell: () => { tone(740, 0, 1.2, 0.35, 'sine'); tone(1480, 0, 0.4, 0.1, 'sine') },
  // Два восходящих тона — «готов!»
  ready: () => { tone(660, 0, 0.18, 0.3, 'sine'); tone(880, 0.22, 0.22, 0.3, 'sine') },
}

export function playSound(name) {
  const fn = SOUNDS[name]
  if (!fn) return
  try {
    // Resume suspended context (browser requires user gesture first)
    if (_ctx?.state === 'suspended') _ctx.resume()
    fn()
  } catch { /* ignore if audio not available */ }
}

export function getRestSound() {
  return localStorage.getItem('rest-sound') || 'bell'
}

export function setRestSound(name) {
  localStorage.setItem('rest-sound', name)
}

export const SOUND_OPTIONS = [
  { id: 'beep', label: 'Сигнал', desc: 'Короткий чёткий бип' },
  { id: 'bell', label: 'Колокол', desc: 'Мягкий мелодичный звон' },
  { id: 'ready', label: 'Готов', desc: 'Два восходящих тона' },
]
