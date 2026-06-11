import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { ready, applyColorScheme } from './tg'

function mount() {
  try {
    ready()
    applyColorScheme()
    createRoot(document.getElementById('root')).render(
      <StrictMode>
        <App />
      </StrictMode>,
    )
  } catch (e) {
    document.getElementById('root').innerHTML =
      '<div style="padding:24px;font-family:sans-serif;color:#f87171;font-size:13px">' +
      '<b>Ошибка запуска:</b><br><br>' + (e?.message || String(e)) +
      '</div>'
  }
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
