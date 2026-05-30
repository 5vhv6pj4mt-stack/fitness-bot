export const tg = window.Telegram?.WebApp || null

export function getInitData() {
  return tg?.initData || ''
}

export function getUser() {
  return tg?.initDataUnsafe?.user || null
}

export function ready() {
  tg?.ready()
  tg?.expand()
}

export function haptic(type = 'light') {
  tg?.HapticFeedback?.impactOccurred(type)
}

export function showMainButton(text, onClick) {
  if (!tg) return
  tg.MainButton.setText(text)
  tg.MainButton.onClick(onClick)
  tg.MainButton.show()
}

export function hideMainButton() {
  tg?.MainButton?.hide()
}

export function getTheme() {
  return tg?.themeParams || {}
}
