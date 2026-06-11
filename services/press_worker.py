"""
Воркер обработки видео жима гантелей.
Запускается как отдельный процесс (systemd fitness-press-worker.service).

Директории:
  temp/queue/pending/    — задачи ожидают обработки
  temp/queue/processing/ — задача в работе (одна за раз)
  temp/queue/done/       — готовые результаты (TTL 2 часа)
"""
import asyncio
import json
import logging
import os
import shutil
import time
from pathlib import Path

from config import QUEUE_DIR

PENDING_DIR    = Path(QUEUE_DIR) / "pending"
PROCESSING_DIR = Path(QUEUE_DIR) / "processing"
DONE_DIR       = Path(QUEUE_DIR) / "done"

DONE_TTL_HOURS = 2
POLL_INTERVAL  = 1  # секунды между проверками очереди

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [press_worker] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("press_worker")


def _setup_dirs():
    for d in [PENDING_DIR, PROCESSING_DIR, DONE_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def _recover_stuck():
    """При старте возвращаем все зависшие 'processing' задачи в очередь."""
    stuck = list(PROCESSING_DIR.glob("*.json"))
    for f in stuck:
        dest = PENDING_DIR / f.name
        shutil.move(str(f), str(dest))
        log.warning("Recovered stuck task: %s", f.name)


def _cleanup_done(max_age_hours: int = DONE_TTL_HOURS):
    cutoff = time.time() - max_age_hours * 3600
    for f in DONE_DIR.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
        except OSError:
            pass


def _write_done(task_id: str, payload: dict):
    import tempfile
    target = DONE_DIR / f"{task_id}.json"
    content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=DONE_DIR, suffix=".tmp", delete=False) as tf:
        tf.write(content)
        tmp_path = tf.name
    os.replace(tmp_path, target)


def _process(task_file: Path):
    task = json.loads(task_file.read_text(encoding="utf-8"))
    task_id   = task["task_id"]
    user_id   = task["user_id"]
    set_id    = task.get("set_id")
    video_path = task["video_path"]

    proc_file = PROCESSING_DIR / task_file.name
    shutil.move(str(task_file), str(proc_file))
    log.info("Start  task=%s  video=%s", task_id, video_path)

    try:
        from services.dumbbell_press_analyzer import analyze_dumbbell_press
        result = analyze_dumbbell_press(video_path)

        if result["status"] == "ok":
            warnings = {
                k: result[k]
                for k in ("symmetry_warning", "trajectory_warning", "back_warning")
                if result.get(k)
            }
            from database.db import save_press_analysis
            asyncio.run(save_press_analysis(
                user_id=user_id,
                set_id=set_id,
                left_angle=result["left_elbow_min_deg"],
                right_angle=result["right_elbow_min_deg"],
                depth=result["depth"],
                warnings=warnings,
                recommendation=result["recommendation"],
            ))

        _write_done(task_id, result)
        log.info("Done   task=%s  status=%s", task_id, result["status"])

    except Exception as exc:
        log.exception("Error  task=%s", task_id)
        _write_done(task_id, {"status": "error", "message": str(exc)})

    finally:
        proc_file.unlink(missing_ok=True)
        try:
            os.remove(video_path)
        except OSError:
            pass


def run():
    _setup_dirs()
    _recover_stuck()
    log.info("Worker ready — watching %s", PENDING_DIR)

    idle_cycles = 0
    while True:
        pending = sorted(PENDING_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
        if pending:
            idle_cycles = 0
            try:
                _process(pending[0])
            except Exception:
                log.exception("Unhandled error in _process")
        else:
            idle_cycles += 1
            if idle_cycles % 120 == 0:  # каждые ~2 минуты
                _cleanup_done()
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
