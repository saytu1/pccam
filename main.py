"""PCCam 실행 파일.

  python main.py                       → GUI 실행
  python main.py --headless -i 60      → 창 없이 60초마다 촬영 (Ctrl+C 로 종료)
"""

from __future__ import annotations

import argparse
import signal
import sys
import time


def headless(args: argparse.Namespace) -> int:
    from pccam.camera import Camera
    from pccam.capture import IntervalCapture
    from pccam.config import load_settings

    s = load_settings()
    if args.camera is not None:
        s.camera_index = args.camera
    if args.interval is not None:
        s.interval_value, s.interval_unit = args.interval, "초"
    if args.out:
        s.save_dir = args.out
    if args.count is not None:
        s.max_shots = args.count
    if args.resolution:
        s.resolution = args.resolution

    cam = Camera()
    w, h = cam.open(s.camera_index, *s.resolution_wh())
    print(f"카메라 {s.camera_index} 연결 ({w}x{h}), {s.interval_seconds():g}초 간격, 저장: {s.save_dir}")

    done = {"flag": False}
    ic = IntervalCapture(
        cam.latest_frame, s,
        on_saved=lambda p, n: print(f"[{n}] {p}", flush=True),
        on_error=lambda m: print("오류:", m, flush=True),
        on_stopped=lambda r: (print("종료:", r), done.update(flag=True)),
    )
    signal.signal(signal.SIGINT, lambda *_: ic.stop())
    ic.start()
    try:
        while not done["flag"]:
            time.sleep(0.2)
    finally:
        ic.stop()
        cam.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="PCCam - USB 카메라 인터벌 촬영")
    ap.add_argument("--headless", action="store_true", help="창 없이 인터벌 촬영만 실행")
    ap.add_argument("-c", "--camera", type=int, help="카메라 번호 (0부터)")
    ap.add_argument("-i", "--interval", type=float, help="촬영 간격(초)")
    ap.add_argument("-o", "--out", help="저장 폴더")
    ap.add_argument("-n", "--count", type=int, help="최대 촬영 장수 (0=무제한)")
    ap.add_argument("-r", "--resolution", help="해상도 예: 1920x1080")
    args = ap.parse_args()

    if args.headless:
        return headless(args)
    from pccam.gui import run
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
