"""Анализ техники жима гантелей лёжа через MediaPipe Pose."""
import math
import cv2
import mediapipe as mp
import numpy as np


mp_pose = mp.solutions.pose

# Индексы ключевых точек MediaPipe Pose
_L_SHOULDER = 11
_R_SHOULDER = 12
_L_ELBOW    = 13
_R_ELBOW    = 14
_L_WRIST    = 15
_R_WRIST    = 16
_L_HIP      = 23
_R_HIP      = 24


def _angle(a, b, c) -> float:
    """Угол в точке b (плечо-локоть-запястье), градусы."""
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    dot = ba[0] * bc[0] + ba[1] * bc[1]
    mag = math.hypot(*ba) * math.hypot(*bc)
    if mag < 1e-6:
        return 180.0
    cos_a = max(-1.0, min(1.0, dot / mag))
    return math.degrees(math.acos(cos_a))


def _lm(landmarks, idx, w, h):
    """Координаты точки в пикселях."""
    p = landmarks[idx]
    return (p.x * w, p.y * h)


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
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"status": "error", "message": f"Не удалось открыть видео: {video_path}"}

    left_angles:  list[float] = []
    right_angles: list[float] = []
    trajectory_deviations: list[float] = []
    back_warnings_count = 0
    frames_with_pose = 0

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        smooth_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as pose:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = pose.process(rgb)

            if not result.pose_landmarks:
                continue

            lm = result.pose_landmarks.landmark
            frames_with_pose += 1

            # Координаты ключевых точек
            l_sh = _lm(lm, _L_SHOULDER, w, h)
            r_sh = _lm(lm, _R_SHOULDER, w, h)
            l_el = _lm(lm, _L_ELBOW,    w, h)
            r_el = _lm(lm, _R_ELBOW,    w, h)
            l_wr = _lm(lm, _L_WRIST,    w, h)
            r_wr = _lm(lm, _R_WRIST,    w, h)
            l_hi = _lm(lm, _L_HIP,      w, h)
            r_hi = _lm(lm, _R_HIP,      w, h)

            # Углы в локтях
            left_angles.append(_angle(l_sh, l_el, l_wr))
            right_angles.append(_angle(r_sh, r_el, r_wr))

            # Ширина плеч
            shoulder_width = abs(l_sh[0] - r_sh[0])

            # Траектория: только в верхней точке (рука выпрямлена, угол > 150°)
            # В нижней точке запястья анатомически уходят в стороны — это норма
            if shoulder_width > 1e-3:
                avg_angle = (left_angles[-1] + right_angles[-1]) / 2
                if avg_angle > 150:
                    l_dev = abs(l_wr[0] - l_el[0]) / shoulder_width
                    r_dev = abs(r_wr[0] - r_el[0]) / shoulder_width
                    trajectory_deviations.append(max(l_dev, r_dev))

            # Поясница: таз (r_hip, y) выше груди (r_shoulder, y) — в пикселях y растёт вниз,
            # значит "выше на экране" = меньшее y. Прогиб: таз приподнят → y таза < y плеча
            mid_hip_y = (l_hi[1] + r_hi[1]) / 2
            mid_sh_y  = (l_sh[1] + r_sh[1]) / 2
            if mid_hip_y < mid_sh_y:
                back_warnings_count += 1

    cap.release()

    if frames_with_pose < 10:
        return {
            "status": "error",
            "message": f"Слишком мало кадров с обнаруженным человеком ({frames_with_pose}). "
                       "Убедись, что тело полностью в кадре.",
        }

    left_min  = float(np.min(left_angles))
    right_min = float(np.min(right_angles))
    best_min  = max(left_min, right_min)  # глубина = слабейшая рука

    depth = _depth_label(best_min)

    # Симметричность
    symmetry_warning = None
    if abs(left_min - right_min) > 15:
        symmetry_warning = (
            f"Несимметричный жим: левая рука {left_min:.0f}°, правая {right_min:.0f}°. "
            "Следи за одинаковой амплитудой обеих рук."
        )

    # Траектория
    trajectory_warning = None
    if trajectory_deviations:
        avg_dev = float(np.mean(trajectory_deviations))
        if avg_dev > 0.1:
            trajectory_warning = "Разводи руки в стороны: запястья уходят в сторону от локтей."

    # Поясница
    back_warning = None
    if frames_with_pose > 0 and back_warnings_count / frames_with_pose > 0.3:
        back_warning = "Не прогибай поясницу: таз приподнят над скамьёй."

    # Итоговая рекомендация
    if depth == "deep" and not symmetry_warning and not trajectory_warning and not back_warning:
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
