"""Анализ техники жима гантелей лёжа через MediaPipe Pose (Tasks API)."""
import math
import os
import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.core.base_options import BaseOptions

_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "models", "pose_landmarker_lite.task",
)

# Индексы ключевых точек (совпадают со старым API)
_L_SHOULDER, _R_SHOULDER = 11, 12
_L_ELBOW,    _R_ELBOW    = 13, 14
_L_WRIST,    _R_WRIST    = 15, 16
_L_HIP,      _R_HIP      = 23, 24


def _angle_3d(a, b, c) -> float:
    """
    Угол в точке b по 3D-координатам (x, y, z).
    Инвариантен к углу камеры — работает корректно при горизонтальном положении тела.
    """
    ba = (a[0]-b[0], a[1]-b[1], a[2]-b[2])
    bc = (c[0]-b[0], c[1]-b[1], c[2]-b[2])
    dot = ba[0]*bc[0] + ba[1]*bc[1] + ba[2]*bc[2]
    mag = math.sqrt(ba[0]**2 + ba[1]**2 + ba[2]**2) * \
          math.sqrt(bc[0]**2 + bc[1]**2 + bc[2]**2)
    if mag < 1e-6:
        return 180.0
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / mag))))


def _depth_label(angle_deg: float) -> str:
    if angle_deg < 70:
        return "deep"
    if angle_deg <= 90:
        return "good"
    return "shallow"


def analyze_dumbbell_press(video_path: str) -> dict:
    """
    Анализирует видео жима гантелей лёжа.

    Returns:
        dict с ключами: status, left_elbow_min_deg, right_elbow_min_deg,
        depth, symmetry_warning, trajectory_warning, back_warning, recommendation.
    """
    if not os.path.exists(_MODEL_PATH):
        return {
            "status":  "error",
            "message": f"Файл модели не найден: {_MODEL_PATH}",
        }

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"status": "error", "message": f"Не удалось открыть видео: {video_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    left_angles:  list[float] = []
    right_angles: list[float] = []
    trajectory_deviations: list[float] = []
    back_warnings_count = 0
    frames_with_pose    = 0

    options = mp_vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=_MODEL_PATH),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        output_segmentation_masks=False,
    )

    # Обрабатываем каждый 3-й кадр — ускоряет анализ в 3x без потери качества
    FRAME_STEP = 3

    try:
        with mp_vision.PoseLandmarker.create_from_options(options) as landmarker:
            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_idx += 1
                if frame_idx % FRAME_STEP != 0:
                    continue

                h, w = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int(frame_idx * 1000 / fps)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if not result.pose_landmarks or not result.pose_world_landmarks:
                    continue

                # Нормализованные координаты — для геометрии в плоскости изображения
                lm = result.pose_landmarks[0]
                # World landmarks (метры, 3D) — для угловых измерений, не зависят от камеры
                wlm = result.pose_world_landmarks[0]

                def img_pt(idx):
                    return (lm[idx].x * w, lm[idx].y * h)

                def world_pt(idx):
                    p = wlm[idx]
                    return (p.x, p.y, p.z)

                frames_with_pose += 1

                # Углы в локтях по 3D world-координатам — корректно при любом угле камеры
                l_sh_w = world_pt(_L_SHOULDER); r_sh_w = world_pt(_R_SHOULDER)
                l_el_w = world_pt(_L_ELBOW);    r_el_w = world_pt(_R_ELBOW)
                l_wr_w = world_pt(_L_WRIST);    r_wr_w = world_pt(_R_WRIST)

                left_angles.append(_angle_3d(l_sh_w, l_el_w, l_wr_w))
                right_angles.append(_angle_3d(r_sh_w, r_el_w, r_wr_w))

                # Для траектории и поясницы используем 2D-координаты в изображении
                l_sh = img_pt(_L_SHOULDER); r_sh = img_pt(_R_SHOULDER)
                l_el = img_pt(_L_ELBOW);    r_el = img_pt(_R_ELBOW)
                l_wr = img_pt(_L_WRIST);    r_wr = img_pt(_R_WRIST)
                l_hi = img_pt(_L_HIP);      r_hi = img_pt(_R_HIP)

                shoulder_width = abs(l_sh[0] - r_sh[0])

                # Траектория: только в верхней точке (угол > 150° — рука выпрямлена)
                if shoulder_width > 1e-3:
                    avg_angle = (left_angles[-1] + right_angles[-1]) / 2
                    if avg_angle > 150:
                        l_dev = abs(l_wr[0] - l_el[0]) / shoulder_width
                        r_dev = abs(r_wr[0] - r_el[0]) / shoulder_width
                        trajectory_deviations.append(max(l_dev, r_dev))

                # Поясница: таз приподнят → y таза < y плеча (y растёт вниз)
                mid_hip_y = (l_hi[1] + r_hi[1]) / 2
                mid_sh_y  = (l_sh[1] + r_sh[1]) / 2
                if mid_hip_y < mid_sh_y:
                    back_warnings_count += 1
    finally:
        cap.release()

    if frames_with_pose < 10:
        return {
            "status":  "error",
            "message": (
                f"Слишком мало кадров с обнаруженным человеком ({frames_with_pose}). "
                "Убедись, что тело полностью в кадре."
            ),
        }

    left_min  = float(np.min(left_angles))
    right_min = float(np.min(right_angles))
    best_min  = max(left_min, right_min)  # глубина = слабейшая рука

    depth = _depth_label(best_min)

    symmetry_warning = None
    if abs(left_min - right_min) > 15:
        symmetry_warning = (
            f"Несимметричный жим: левая рука {left_min:.0f}°, правая {right_min:.0f}°. "
            "Следи за одинаковой амплитудой обеих рук."
        )

    trajectory_warning = None
    if trajectory_deviations and float(np.mean(trajectory_deviations)) > 0.1:
        trajectory_warning = "Разводи руки в стороны: запястья уходят в сторону от локтей."

    back_warning = None
    if frames_with_pose > 0 and back_warnings_count / frames_with_pose > 0.3:
        back_warning = "Не прогибай поясницу: таз приподнят над скамьёй."

    if depth == "deep" and not any([symmetry_warning, trajectory_warning, back_warning]):
        recommendation = "Отличная техника — полная амплитуда, симметричное движение."
    elif depth == "shallow":
        recommendation = "Опускай гантели ниже — увеличь амплитуду для лучшей нагрузки на грудь."
    elif symmetry_warning:
        recommendation = "Работай над симметрией: следи чтобы обе руки двигались одинаково."
    elif trajectory_warning:
        recommendation = "Контролируй траекторию: запястья должны двигаться строго вертикально."
    elif back_warning:
        recommendation = "Держи поясницу на скамье — не допускай прогиба."
    else:
        recommendation = "Хорошая техника, есть небольшой запас для улучшения амплитуды."

    depth_label_ru = {
        "deep":    "отлично, полная амплитуда",
        "good":    "хорошо, достаточно глубоко",
        "shallow": "малая амплитуда, опускай гантели ниже",
    }[depth]

    return {
        "status":              "ok",
        "left_elbow_min_deg":  round(left_min, 1),
        "right_elbow_min_deg": round(right_min, 1),
        "depth":               depth_label_ru,
        "symmetry_warning":    symmetry_warning,
        "trajectory_warning":  trajectory_warning,
        "back_warning":        back_warning,
        "recommendation":      recommendation,
    }
