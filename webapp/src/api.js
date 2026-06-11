import { getInitData } from './tg'

const BASE = '/fitness/api'
const TIMEOUT_MS = 15000

export function friendlyError(e) {
  const msg = (e?.message || '').toLowerCase()
  if (msg.includes('abort') || msg.includes('не отвечает') || msg.includes('timeout'))
    return 'Сервер думает слишком долго — попробуй ещё раз'
  if (msg.includes('network') || msg.includes('fetch') || msg.includes('failed to fetch'))
    return 'Проверь интернет-соединение'
  if (msg.includes('500') || msg.includes('internal server'))
    return 'Сервер временно не работает — попробуй через минуту'
  if (msg.includes('401') || msg.includes('initdata') || msg.includes('unauthorized'))
    return 'Ошибка авторизации — закрой и открой приложение заново'
  if (msg.includes('404'))
    return 'Данные не найдены'
  if (msg.includes('400') || msg.includes('invalid'))
    return 'Некорректные данные — проверь введённое значение'
  return 'Что-то пошло не так — попробуй ещё раз'
}

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
  bodyData: () => req('/body'),
  logWeight: (weight) => req('/body/weight', { method: 'POST', body: JSON.stringify({ weight }) }),
  logMeasurements: (data) => req('/body/measurements', { method: 'POST', body: JSON.stringify(data) }),
  updateExerciseWeight: (exercise, weekType, dayType, weight) =>
    req('/workout/exercise-weight', { method: 'PATCH', body: JSON.stringify({ exercise, week_type: weekType, day_type: dayType, weight }) }),
  weekReport: () => req('/progress/week'),
  progress: () => req('/progress'),
  exerciseHistory: (name) => req(`/progress/exercise?name=${encodeURIComponent(name)}`),
  musclesData: () => req('/progress/muscles'),
  workoutAnalysis: (id) => req(`/workout/${id}/analysis`),
  recentWorkouts: () => req('/workout/recent'),
  deleteSet: (setId) => req(`/workout/set/${setId}`, { method: 'DELETE' }),
  exerciseInfo: (name) => req(`/exercise/info?name=${encodeURIComponent(name)}`),
}
