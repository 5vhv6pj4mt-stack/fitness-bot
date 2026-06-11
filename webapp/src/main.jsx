import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { ready, applyColorScheme } from './tg'

function mount() {
  ready()
  applyColorScheme()
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

// Ждём пока Telegram WebApp загрузится и заполнит initData.
// На десктопе и при первом запуске на Android это занимает несколько итераций.
function waitAndMount(attempt = 0) {
  if (window.Telegram?.WebApp?.initData || attempt >= 7) {
    mount()
  } else {
    setTimeout(() => waitAndMount(attempt + 1), 150 * (attempt + 1))
  }
}

waitAndMount()
