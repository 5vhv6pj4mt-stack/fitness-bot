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

export function applyColorScheme() {
  const tg = getTg()
  const override = localStorage.getItem('theme')
  const scheme = override || tg?.colorScheme || 'dark'
  if (scheme === 'light') {
    document.documentElement.classList.add('tg-light')
  } else {
    document.documentElement.classList.remove('tg-light')
  }
  tg?.onEvent?.('themeChanged', () => {
    if (!localStorage.getItem('theme')) applyColorScheme()
  })
}

export function setThemeOverride(scheme) {
  if (scheme) {
    localStorage.setItem('theme', scheme)
  } else {
    localStorage.removeItem('theme')
  }
  applyColorScheme()
}

export function getThemeOverride() {
  return localStorage.getItem('theme') || null
}
