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
      <button onclick="location.reload()" style="
        margin-top:24px;padding:12px 28px;background:#0a84ff;border:none;
        border-radius:12px;font-size:15px;font-weight:600;color:#fff;cursor:pointer;
      ">Попробовать снова</button>
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

// Ждём появления window.Telegram.WebApp.
// async-скрипт TG может грузиться дольше модуля — ждём до 15 сек.
function waitAndMount(attempt = 0) {
  if (window.Telegram?.WebApp) {
    mount()
  } else if (attempt >= 30) {
    showNotInTelegram()
  } else {
    setTimeout(() => waitAndMount(attempt + 1), Math.min(100 * (attempt + 1), 500))
  }
}

waitAndMount()
