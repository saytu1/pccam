"""설정 저장/불러오기 (settings.json)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def app_dir() -> Path:
    """실행 파일(.exe) 또는 main.py 가 있는 폴더."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def default_save_dir() -> str:
    pictures = Path(os.path.expanduser("~")) / "Pictures"
    base = pictures if pictures.exists() else Path(os.path.expanduser("~"))
    return str(base / "PCCam")


UNITS = {"초": 1, "분": 60, "시간": 3600}


@dataclass
class Settings:
    camera_index: int = 0
    resolution: str = "1280x720"
    save_dir: str = ""
    prefix: str = "cam"
    image_format: str = "jpg"      # jpg / png
    jpeg_quality: int = 95
    interval_value: float = 10.0
    interval_unit: str = "초"       # 초 / 분 / 시간
    date_subfolder: bool = True     # 날짜별(YYYY-MM-DD) 하위 폴더 생성
    timestamp_overlay: bool = False # 사진에 촬영 시각 글자 넣기
    max_shots: int = 0              # 0 = 무제한
    min_free_mb: int = 500          # 디스크 여유 공간이 이보다 적으면 자동 중지
    auto_connect: bool = True       # 프로그램 시작 시 카메라 자동 연결

    def interval_seconds(self) -> float:
        return float(self.interval_value) * UNITS.get(self.interval_unit, 1)

    def resolution_wh(self) -> tuple:
        try:
            w, h = self.resolution.lower().split("x")
            return int(w), int(h)
        except ValueError:
            return 0, 0  # 카메라 기본값


def settings_file() -> Path:
    """설정 파일 위치.

    exe 로 설치된 경우(Program Files 는 쓰기 불가) %APPDATA%\\PCCam\\settings.json,
    소스 실행 시에는 main.py 옆 settings.json.
    """
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("APPDATA") or os.path.expanduser("~")) / "PCCam"
        base.mkdir(parents=True, exist_ok=True)
        return base / "settings.json"
    return app_dir() / "settings.json"


SETTINGS_FILE = settings_file()


def load_settings(path: Path = SETTINGS_FILE) -> Settings:
    s = Settings()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        valid = {f.name for f in fields(Settings)}
        for k, v in data.items():
            if k in valid:
                setattr(s, k, v)
    except (OSError, ValueError):
        pass
    if not s.save_dir:
        s.save_dir = default_save_dir()
    return s


def save_settings(s: Settings, path: Path = SETTINGS_FILE) -> None:
    try:
        Path(path).write_text(
            json.dumps(asdict(s), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
