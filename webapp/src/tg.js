// Telegram WebApp — with fallback for cases when the bridge loads late
function getTg() {
  return window.Telegram?.WebApp || null
}

export function getInitData() {
  return getTg()?.initData || ''
}

export function getUser() {
  return getTg()?.initDataUnsafe?.user || null
}

export function ready() {
  const tg = getTg()
  tg?.ready()
  tg?.expand()
}

export function haptic(type = 'light') {
  getTg()?.HapticFeedback?.impactOccurred(type)
}

export function showMainButton(text, onClick) {
  const tg = getTg()
  if (!tg) return
  tg.MainButton.setText(text)
  tg.MainButton.onClick(onClick)
  tg.MainButton.show()
}

export function hideMainButton() {
  getTg()?.MainButton?.hide()
}

export function getTheme() {
  return getTg()?.themeParams || {}
}
