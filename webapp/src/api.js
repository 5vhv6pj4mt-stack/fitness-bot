import { getInitData } from './tg'

const BASE = '/fitness/api'

async function req(path, options = {}) {
  const initData = getInitData()
  const res = await fetch(BASE + path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'x-init-data': initData,
      ...(options.headers || {}),
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  dashboard: () => req('/dashboard'),
  workoutPlan: () => req('/workout/plan'),
  startWorkout: () => req('/workout/start', { method: 'POST', body: '{}' }),
  logSet: (data) => req('/workout/log-set', { method: 'POST', body: JSON.stringify(data) }),
  finishWorkout: (data) => req('/workout/finish', { method: 'POST', body: JSON.stringify(data) }),
  nutritionToday: () => req('/nutrition'),
  logFood: (text) => req('/nutrition/log', { method: 'POST', body: JSON.stringify({ text }) }),
}
