import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { ready, applyColorScheme } from './tg'

function showNotInTelegram() {
  document.getElementById('root').innerHTML = `
    <div style="
      display:flex;flex-direction:column;align-items:center;justify-content:center;
      min-height:100vh;padding:32px 24px;text-align:center;
      background:#1c1c1e;color:#ebebf5;font-family:-apple-system,sans-serif;
    ">
      <div style="font-size:48px;margin-bottom:16px;">💪</div>
      <div style="font-size:20px;font-weight:700;margin-bottom:8px;">Стать — фитнес</div>
      <div style="font-size:14px;color:#8e8e93;line-height:1.6;max-width:280px;">
        Откройте приложение через Telegram-бота<br>
        <a href="https://t.me/stat_sila_bot" style="color:#0a84ff;text-decoration:none;">@stat_sila_bot</a>
      </div>
      <div style="margin-top:24px;padding:12px 20px;background:#2c2c2e;border-radius:12px;font-size:12px;color:#636366;">
        Приложение работает только<br>внутри Telegram Mini App
      </div>
    </div>
  `
}

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
  if (window.Telegram?.WebApp) {
    mount()
  } else if (attempt >= 10) {
    // После 10 попыток (~5.5 сек) — показываем заглушку вместо вечного спиннера
    showNotInTelegram()
  } else {
    setTimeout(() => waitAndMount(attempt + 1), 100 * (attempt + 1))
  }
}

waitAndMount()
