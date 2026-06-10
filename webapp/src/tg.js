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

const DARK_OVERRIDES = {
  '--tg-theme-bg-color': '#1c1c1e',
  '--tg-theme-secondary-bg-color': '#2c2c2e',
  '--tg-theme-text-color': '#ffffff',
  '--tg-theme-hint-color': '#8e8e93',
  '--tg-theme-button-color': '#0a84ff',
  '--tg-theme-button-text-color': '#ffffff',
  '--tg-theme-link-color': '#0a84ff',
}

export function applyColorScheme() {
  const tg = getTg()
  const override = localStorage.getItem('theme')
  const root = document.documentElement

  if (override === 'dark') {
    Object.entries(DARK_OVERRIDES).forEach(([k, v]) => root.style.setProperty(k, v))
    root.classList.remove('tg-light')
  } else if (override === 'light') {
    Object.keys(DARK_OVERRIDES).forEach((k) => root.style.removeProperty(k))
    root.classList.add('tg-light')
  } else {
    Object.keys(DARK_OVERRIDES).forEach((k) => root.style.removeProperty(k))
    const scheme = tg?.colorScheme || 'dark'
    if (scheme === 'light') root.classList.add('tg-light')
    else root.classList.remove('tg-light')
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
