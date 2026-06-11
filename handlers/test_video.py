"""
/test_press — ручное тестирование видеоаналитики жима гантелей через Telegram.
"""
import asyncio
import hashlib
import hmac
import io
import json
import logging
import os
import tempfile
import time
from urllib.parse import urlencode

import aiohttp
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from config import BOT_TOKEN

log = logging.getLogger(__name__)
router = Router()

API_BASE      = "http://127.0.0.1:8001/api"
POLL_INTERVAL = 2   # секунды
POLL_MAX      = 90  # попыток (3 мин)


def _make_init_data(user_id: int, first_name: str = "Bot") -> str:
    """Генерирует валидный Telegram initData для внутренних запросов к API."""
    user_json = json.dumps({"id": user_id, "first_name": first_name}, separators=(",", ":"))
    params = {
        "auth_date": str(int(time.time())),
        "user":      user_json,
    }
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key  = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    sig         = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    params["hash"] = sig
    return urlencode(params)


def _depth_ru(depth: str) -> str:
    return {"deep": "Глубокая ✅", "good": "Хорошая ✅", "shallow": "Мелкая ⚠️"}.get(depth, depth)


@router.message(Command("test_press"))
async def cmd_test_press(message: Message):
    await message.answer(
        "Отправь видео жима гантелей лёжа (до 20 МБ, mp4/mov). "
        "Я проанализирую технику."
    )


@router.message(lambda m: m.video is not None or (
    m.document is not None
    and m.document.mime_type is not None
    and m.document.mime_type.startswith("video/")
))
async def handle_video_for_analysis(message: Message, bot: Bot):
    if message.video:
        file_id   = message.video.file_id
        file_size = message.video.file_size or 0
        mime      = message.video.mime_type or "video/mp4"
    else:
        file_id   = message.document.file_id
        file_size = message.document.file_size or 0
        mime      = message.document.mime_type or "video/mp4"

    if file_size > 20 * 1024 * 1024:
        await message.answer("Видео слишком большое (максимум 20 МБ).")
        return

    ext = ".mp4" if "mp4" in mime else ".mov"
    status_msg = await message.answer("Скачиваю видео...")

    tmp_path = None
    try:
        file_info = await bot.get_file(file_id)
        buf = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=buf)
        buf.seek(0)

        os.makedirs("temp/videos", exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir="temp/videos", suffix=ext)
        with os.fdopen(fd, "wb") as f:
            f.write(buf.read())
    except Exception as e:
        log.exception("Ошибка скачивания видео")
        await status_msg.edit_text(f"Ошибка скачивания: {e}")
        return

    init_data = _make_init_data(message.from_user.id, message.from_user.first_name or "User")
    headers   = {"x-init-data": init_data}

    try:
        await status_msg.edit_text("Видео загружено, анализ в очереди...")
        async with aiohttp.ClientSession() as session:
            with open(tmp_path, "rb") as vf:
                form = aiohttp.FormData()
                form.add_field("video", vf, filename=f"press{ext}", content_type=mime)
                async with session.post(
                    f"{API_BASE}/analyze_dumbbell_press",
                    data=form,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        await status_msg.edit_text(f"API ответил {resp.status}: {body[:300]}")
                        return
                    data = await resp.json()
                    task_id = data.get("task_id")
                    if not task_id:
                        await status_msg.edit_text("API не вернул task_id.")
                        return
    except Exception as e:
        log.exception("Ошибка отправки на API")
        await status_msg.edit_text(f"Ошибка API: {e}")
        return
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    await status_msg.edit_text("Анализирую кадры... ⏳")
    async with aiohttp.ClientSession() as session:
        for attempt in range(POLL_MAX):
            await asyncio.sleep(POLL_INTERVAL)
            try:
                async with session.get(
                    f"{API_BASE}/press_analysis_status/{task_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        continue
                    result = await resp.json()
            except Exception:
                continue

            status = result.get("status")
            if status in ("pending", "processing"):
                if attempt == 5:
                    await status_msg.edit_text("Анализирую кадры... ⏳ (обычно 10–30 сек)")
                continue

            if status == "done":
                r = result.get("result", {})
                if r.get("status") == "error":
                    await status_msg.edit_text(
                        f"Ошибка анализа: {r.get('message', 'неизвестно')}"
                    )
                    return

                lines = ["<b>Результат анализа жима гантелей</b>"]
                lines.append(f"Глубина: {_depth_ru(r.get('depth', '?'))}")

                left  = r.get("left_elbow_min_deg")
                right = r.get("right_elbow_min_deg")
                if left is not None and right is not None:
                    lines.append(f"Левый локоть: {left:.0f}°   Правый локоть: {right:.0f}°")

                for key in ("symmetry_warning", "trajectory_warning", "back_warning"):
                    w = r.get(key)
                    if w:
                        lines.append(f"\n⚠️ {w}")

                rec = r.get("recommendation")
                if rec:
                    lines.append(f"\n💡 {rec}")

                await status_msg.edit_text("\n".join(lines), parse_mode="HTML")
                return

        await status_msg.edit_text("Время ожидания истекло (3 мин). Попробуй снова.")
