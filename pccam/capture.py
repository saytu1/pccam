"""사진 저장 및 인터벌(일정 간격) 촬영."""

from __future__ import annotations

import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from .config import Settings


def add_timestamp(frame: np.ndarray, when: datetime) -> np.ndarray:
    """프레임 오른쪽 아래에 촬영 시각을 그린다."""
    text = when.strftime("%Y-%m-%d %H:%M:%S")
    h, w = frame.shape[:2]
    scale = max(0.5, w / 1280.0)
    thick = max(1, int(round(2 * scale)))
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    x, y = w - tw - 10, h - 10
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), thick, cv2.LINE_AA)
    return frame


def build_path(s: Settings, when: datetime) -> Path:
    """저장 경로: <저장폴더>[/YYYY-MM-DD]/<접두어>_YYYYMMDD_HHMMSS_mmm.jpg"""
    folder = Path(s.save_dir)
    if s.date_subfolder:
        folder = folder / when.strftime("%Y-%m-%d")
    ext = "png" if s.image_format.lower() == "png" else "jpg"
    stamp = when.strftime("%Y%m%d_%H%M%S_") + f"{when.microsecond // 1000:03d}"
    prefix = (s.prefix or "cam").strip()
    path = folder / f"{prefix}_{stamp}.{ext}"
    n = 1
    while path.exists():
        path = folder / f"{prefix}_{stamp}_{n}.{ext}"
        n += 1
    return path


def save_frame(frame: np.ndarray, s: Settings, when: Optional[datetime] = None) -> Path:
    """프레임을 파일로 저장하고 경로를 반환한다.

    cv2.imwrite 는 Windows에서 한글 경로를 처리하지 못하므로
    imencode + tofile 방식으로 저장한다.
    """
    when = when or datetime.now()
    img = frame.copy()
    if s.timestamp_overlay:
        add_timestamp(img, when)
    path = build_path(s, when)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".png":
        ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    else:
        q = int(min(100, max(1, s.jpeg_quality)))
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    if not ok:
        raise RuntimeError("이미지 인코딩 실패")
    buf.tofile(str(path))
    return path


def free_mb(folder: str) -> float:
    p = Path(folder)
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        return shutil.disk_usage(str(p)).free / (1024 * 1024)
    except OSError:
        return float("inf")


class IntervalCapture:
    """일정 간격으로 프레임을 저장하는 스케줄러 (별도 스레드).

    시작 시각 기준으로 다음 촬영 시각을 계산하므로 오래 돌려도 간격이 밀리지 않는다.
    """

    def __init__(
        self,
        get_frame: Callable[[], Optional[np.ndarray]],
        settings: Settings,
        on_saved: Callable[[Path, int], None] = lambda p, n: None,
        on_error: Callable[[str], None] = lambda msg: None,
        on_stopped: Callable[[str], None] = lambda reason: None,
    ) -> None:
        self.get_frame = get_frame
        self.settings = settings
        self.on_saved = on_saved
        self.on_error = on_error
        self.on_stopped = on_stopped
        self.count = 0
        self.next_shot_at = 0.0  # time.monotonic() 기준
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def seconds_to_next(self) -> float:
        return max(0.0, self.next_shot_at - time.monotonic()) if self.running else 0.0

    def start(self) -> None:
        if self.running:
            return
        interval = self.settings.interval_seconds()
        if interval <= 0:
            raise ValueError("촬영 간격은 0보다 커야 합니다.")
        self.count = 0
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="interval", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=3.0)

    def _loop(self) -> None:
        s = self.settings
        interval = s.interval_seconds()
        t_start = time.monotonic()
        k = 0
        reason = "사용자 중지"
        while not self._stop.is_set():
            self.next_shot_at = t_start + k * interval
            wait = self.next_shot_at - time.monotonic()
            if wait > 0 and self._stop.wait(wait):
                break
            # 너무 늦어진 경우(PC 절전 등) 밀린 촬영은 건너뛰고 지금 1장만 찍는다.
            now = time.monotonic()
            if now - self.next_shot_at > interval:
                k = int((now - t_start) // interval)
            k += 1

            if free_mb(s.save_dir) < s.min_free_mb:
                reason = f"디스크 여유 공간 부족 ({s.min_free_mb}MB 미만)"
                break
            frame = self.get_frame()
            if frame is None:
                self.on_error("카메라 프레임이 없습니다 (연결 확인). 이번 촬영은 건너뜁니다.")
                continue
            try:
                path = save_frame(frame, s)
            except Exception as e:  # noqa: BLE001
                self.on_error(f"저장 실패: {e}")
                continue
            self.count += 1
            self.on_saved(path, self.count)
            if s.max_shots and self.count >= s.max_shots:
                reason = f"지정한 {s.max_shots}장 촬영 완료"
                break
        self.next_shot_at = 0.0
        self.on_stopped(reason)
