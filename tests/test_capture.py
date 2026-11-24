"""카메라 없이 저장/인터벌 로직을 검증하는 테스트.  실행: python -m pytest tests"""

import time
from datetime import datetime

import numpy as np

from pccam.capture import IntervalCapture, build_path, save_frame
from pccam.config import Settings


def fake_frame():
    return np.full((120, 160, 3), 128, dtype=np.uint8)


def make_settings(tmp_path, **kw):
    s = Settings(save_dir=str(tmp_path / "사진 저장"), min_free_mb=0, **kw)
    return s


def test_save_korean_path(tmp_path):
    s = make_settings(tmp_path, timestamp_overlay=True)
    p = save_frame(fake_frame(), s)
    assert p.exists() and p.stat().st_size > 0
    assert p.parent.name == datetime.now().strftime("%Y-%m-%d")


def test_png_and_no_subfolder(tmp_path):
    s = make_settings(tmp_path, image_format="png", date_subfolder=False)
    p = save_frame(fake_frame(), s)
    assert p.suffix == ".png" and p.parent == tmp_path / "사진 저장"


def test_unique_names(tmp_path):
    s = make_settings(tmp_path)
    when = datetime(2026, 1, 1, 12, 0, 0)
    a = save_frame(fake_frame(), s, when)
    b = save_frame(fake_frame(), s, when)
    assert a != b and a.exists() and b.exists()
    assert build_path(s, when).name.startswith("cam_20260101_120000_000")


def test_interval_max_shots(tmp_path):
    s = make_settings(tmp_path, interval_value=0.2, interval_unit="초", max_shots=4)
    saved, stopped = [], []
    ic = IntervalCapture(fake_frame, s, on_saved=lambda p, n: saved.append((p, time.monotonic())),
                         on_stopped=stopped.append)
    t0 = time.monotonic()
    ic.start()
    ic._thread.join(5)
    assert len(saved) == 4 and stopped and "완료" in stopped[0]
    # 첫 장은 즉시, 이후 0.2초 간격 (드리프트 없음)
    gaps = [t - t0 for _, t in saved]
    for k, g in enumerate(gaps):
        assert abs(g - 0.2 * k) < 0.1, gaps


def test_interval_stop_and_missing_frame(tmp_path):
    s = make_settings(tmp_path, interval_value=0.1, interval_unit="초")
    errors = []
    ic = IntervalCapture(lambda: None, s, on_error=errors.append)
    ic.start()
    time.sleep(0.35)
    ic.stop()
    assert not ic.running and ic.count == 0 and len(errors) >= 2


def test_units():
    assert Settings(interval_value=2, interval_unit="분").interval_seconds() == 120
    assert Settings(interval_value=1, interval_unit="시간").interval_seconds() == 3600
