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

// Ждём появления window.Telegram.WebApp. На мобильных он инжектируется
// асинхронно, на десктопе обычно сразу. Монтируем при первой возможности.
function waitAndMount(attempt = 0) {
  if (window.Telegram?.WebApp || attempt >= 8) {
    mount()
  } else {
    setTimeout(() => waitAndMount(attempt + 1), 100 * (attempt + 1))
  }
}

waitAndMount()
