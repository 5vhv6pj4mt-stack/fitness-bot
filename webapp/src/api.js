import { getInitData } from './tg'

const BASE = '/fitness/api'
const TIMEOUT_MS = 15000

async function req(path, options = {}) {
  const initData = getInitData()
  const isFormData = options.body instanceof FormData
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const headers = { 'x-init-data': initData }
    if (!isFormData) headers['Content-Type'] = 'application/json'
    Object.assign(headers, options.headers || {})

    const res = await fetch(BASE + path, {
      ...options,
      signal: controller.signal,
      headers,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'Request failed')
    }
    return res.json()
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Сервер не отвечает, попробуй ещё раз')
    throw e
  } finally {
    clearTimeout(timeoutId)
  }
}

export const api = {
  dashboard: () => req('/dashboard'),
  workoutPlan: () => req('/workout/plan'),
  startWorkout: () => req('/workout/start', { method: 'POST', body: '{}' }),
  logSet: (data) => req('/workout/log-set', { method: 'POST', body: JSON.stringify(data) }),
  finishWorkout: (data) => req('/workout/finish', { method: 'POST', body: JSON.stringify(data) }),
  nutritionToday: () => req('/nutrition'),
  logFood: (text) => req('/nutrition/log', { method: 'POST', body: JSON.stringify({ text }) }),
  updateFood: (id, text) => req(`/nutrition/${id}`, { method: 'PATCH', body: JSON.stringify({ text }) }),
  deleteFood: (id) => req(`/nutrition/${id}`, { method: 'DELETE' }),
  profileGet: () => req('/profile'),
  profileUpdate: (data) => req('/profile', { method: 'PATCH', body: JSON.stringify(data) }),
  programData: () => req('/program'),
  nutritionTemplates: () => req('/nutrition/templates'),
  logTemplate: (text) => req('/nutrition/log-template', { method: 'POST', body: JSON.stringify({ text }) }),
  logPhoto: (formData) => req('/nutrition/log-photo', { method: 'POST', body: formData }),
  logVoice: (formData) => req('/nutrition/log-voice', { method: 'POST', body: formData }),
  waterToday: () => req('/water/today'),
  waterAdd: () => req('/water/add', { method: 'POST', body: '{}' }),
  progress: () => req('/progress'),
  exerciseHistory: (name) => req(`/progress/exercise?name=${encodeURIComponent(name)}`),
  workoutAnalysis: (id) => req(`/workout/${id}/analysis`),
}
