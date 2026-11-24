"""USB 카메라 제어 모듈.

별도 스레드에서 카메라 프레임을 계속 읽어 최신 프레임을 보관한다.
GUI/인터벌 촬영은 latest_frame() 으로 가장 최근 프레임을 가져다 쓴다.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np


def _backend() -> int:
    """Windows에서는 DirectShow 백엔드가 USB 카메라를 가장 안정적으로 연다."""
    if sys.platform.startswith("win"):
        return cv2.CAP_DSHOW
    return cv2.CAP_ANY


def list_cameras(max_index: int = 8) -> List[int]:
    """연결된 카메라 번호 목록을 반환한다."""
    found = []
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, _backend())
        try:
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    found.append(idx)
        finally:
            cap.release()
    return found


class Camera:
    """백그라운드 스레드로 프레임을 계속 읽는 카메라."""

    def __init__(self) -> None:
        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._frame_time = 0.0
        self.index: Optional[int] = None
        self.fps = 0.0

    # ------------------------------------------------------------------ open
    def open(self, index: int, width: int = 0, height: int = 0) -> Tuple[int, int]:
        """카메라를 연다. 실제 적용된 (가로, 세로) 해상도를 반환한다."""
        self.close()
        cap = cv2.VideoCapture(index, _backend())
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"카메라 {index}번을 열 수 없습니다.")
        # MJPG 로 요청하면 고해상도에서도 프레임레이트가 잘 나오는 카메라가 많다.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        if width > 0 and height > 0:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            raise RuntimeError(f"카메라 {index}번에서 영상을 읽을 수 없습니다.")
        self._cap = cap
        self.index = index
        with self._lock:
            self._frame = frame
            self._frame_time = time.time()
        self._running.set()
        self._thread = threading.Thread(target=self._loop, name="camera", daemon=True)
        self._thread.start()
        h, w = frame.shape[:2]
        return w, h

    def _loop(self) -> None:
        fails = 0
        count = 0
        t0 = time.monotonic()
        while self._running.is_set():
            cap = self._cap
            if cap is None:
                break
            ok, frame = cap.read()
            if not ok or frame is None:
                fails += 1
                if fails > 50:  # 약 2~5초 동안 실패하면 연결 끊김으로 판단
                    with self._lock:
                        self._frame = None
                    break
                time.sleep(0.05)
                continue
            fails = 0
            with self._lock:
                self._frame = frame
                self._frame_time = time.time()
            count += 1
            elapsed = time.monotonic() - t0
            if elapsed >= 1.0:
                self.fps = count / elapsed
                count = 0
                t0 = time.monotonic()
        self._running.clear()

    # ----------------------------------------------------------------- query
    @property
    def is_open(self) -> bool:
        return self._running.is_set()

    def latest_frame(self) -> Optional[np.ndarray]:
        """가장 최근 프레임의 복사본 (없으면 None)."""
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def open_settings_dialog(self) -> None:
        """Windows DirectShow 카메라 속성 창(밝기/노출/포커스 등)을 띄운다."""
        if self._cap is not None:
            self._cap.set(cv2.CAP_PROP_SETTINGS, 1)

    # ----------------------------------------------------------------- close
    def close(self) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        with self._lock:
            self._frame = None
        self.index = None
        self.fps = 0.0
