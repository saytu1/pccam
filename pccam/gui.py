"""Tkinter GUI."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from . import __version__
from .camera import Camera, list_cameras
from .capture import IntervalCapture, save_frame
from .config import UNITS, Settings, load_settings, save_settings

RESOLUTIONS = ["기본값", "640x480", "800x600", "1280x720", "1920x1080", "2560x1440", "3840x2160"]


def open_folder(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class App:
    PREVIEW_MS = 33

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.s: Settings = load_settings()
        self.cam = Camera()
        self.interval: IntervalCapture | None = None
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self._photo = None

        root.title(f"PCCam v{__version__} - USB 카메라 인터벌 촬영")
        root.geometry("1180x720")
        root.minsize(900, 560)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        icon = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets" / "pccam.ico"
        if sys.platform.startswith("win") and icon.exists():
            try:
                root.iconbitmap(str(icon))
            except tk.TclError:
                pass

        self._build_ui()
        self._load_into_ui()
        self.root.after(100, self.refresh_cameras)
        self.root.after(self.PREVIEW_MS, self._tick_preview)
        self.root.after(200, self._tick_status)

    # ================================================================== UI
    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=6)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        # ---- 미리보기
        self.preview = tk.Label(main, bg="black", fg="gray", text="카메라를 연결하세요",
                                font=("맑은 고딕", 14))
        self.preview.grid(row=0, column=0, sticky="nsew")

        # ---- 제어판
        panel = ttk.Frame(main, padding=(8, 0, 0, 0))
        panel.grid(row=0, column=1, sticky="ns")

        # 카메라
        f = ttk.LabelFrame(panel, text="카메라", padding=6)
        f.pack(fill="x", pady=(0, 6))
        self.v_cam = tk.StringVar()
        self.cb_cam = ttk.Combobox(f, textvariable=self.v_cam, width=14, state="readonly")
        self.cb_cam.grid(row=0, column=0, sticky="ew")
        ttk.Button(f, text="새로고침", command=self.refresh_cameras).grid(row=0, column=1, padx=(4, 0))
        ttk.Label(f, text="해상도").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.v_res = tk.StringVar()
        ttk.Combobox(f, textvariable=self.v_res, values=RESOLUTIONS, width=14).grid(
            row=2, column=0, sticky="ew")
        self.btn_connect = ttk.Button(f, text="연결", command=self.toggle_camera)
        self.btn_connect.grid(row=2, column=1, padx=(4, 0))
        ttk.Button(f, text="카메라 속성(밝기/초점 등)", command=self.cam.open_settings_dialog).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.lbl_caminfo = ttk.Label(f, text="-", foreground="gray")
        self.lbl_caminfo.grid(row=4, column=0, columnspan=2, sticky="w")

        # 저장
        f = ttk.LabelFrame(panel, text="저장", padding=6)
        f.pack(fill="x", pady=(0, 6))
        self.v_dir = tk.StringVar()
        ttk.Entry(f, textvariable=self.v_dir, width=26).grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Button(f, text="폴더 선택", command=self.choose_dir).grid(row=1, column=0, sticky="ew", pady=2)
        ttk.Button(f, text="폴더 열기", command=lambda: open_folder(self.v_dir.get())).grid(
            row=1, column=1, columnspan=2, sticky="ew", pady=2, padx=(4, 0))
        ttk.Label(f, text="파일 이름 앞부분").grid(row=2, column=0, sticky="w")
        self.v_prefix = tk.StringVar()
        ttk.Entry(f, textvariable=self.v_prefix, width=12).grid(row=2, column=1, columnspan=2, sticky="ew")
        ttk.Label(f, text="형식 / JPG 품질").grid(row=3, column=0, sticky="w")
        self.v_fmt = tk.StringVar()
        ttk.Combobox(f, textvariable=self.v_fmt, values=["jpg", "png"], width=5,
                     state="readonly").grid(row=3, column=1, sticky="w")
        self.v_quality = tk.IntVar()
        ttk.Spinbox(f, from_=10, to=100, textvariable=self.v_quality, width=5).grid(row=3, column=2, sticky="w")
        self.v_datedir = tk.BooleanVar()
        ttk.Checkbutton(f, text="날짜별 하위 폴더 만들기", variable=self.v_datedir).grid(
            row=4, column=0, columnspan=3, sticky="w")
        self.v_overlay = tk.BooleanVar()
        ttk.Checkbutton(f, text="사진에 촬영 시각 표시", variable=self.v_overlay).grid(
            row=5, column=0, columnspan=3, sticky="w")
        ttk.Button(f, text="📷 지금 한 장 찍기 (Space)", command=self.snapshot).grid(
            row=6, column=0, columnspan=3, sticky="ew", pady=(4, 0))

        # 인터벌 촬영
        f = ttk.LabelFrame(panel, text="인터벌(자동 반복) 촬영", padding=6)
        f.pack(fill="x", pady=(0, 6))
        ttk.Label(f, text="촬영 간격").grid(row=0, column=0, sticky="w")
        self.v_ival = tk.StringVar()
        ttk.Spinbox(f, from_=0.5, to=100000, increment=1, textvariable=self.v_ival, width=8).grid(
            row=0, column=1, sticky="w")
        self.v_unit = tk.StringVar()
        ttk.Combobox(f, textvariable=self.v_unit, values=list(UNITS), width=5, state="readonly").grid(
            row=0, column=2, sticky="w", padx=(4, 0))
        ttk.Label(f, text="최대 장수 (0=무제한)").grid(row=1, column=0, columnspan=2, sticky="w")
        self.v_max = tk.StringVar()
        ttk.Spinbox(f, from_=0, to=10000000, textvariable=self.v_max, width=8).grid(row=1, column=2, sticky="w")
        ttk.Label(f, text="최소 여유 공간(MB)").grid(row=2, column=0, columnspan=2, sticky="w")
        self.v_minfree = tk.StringVar()
        ttk.Spinbox(f, from_=0, to=1000000, increment=100, textvariable=self.v_minfree, width=8).grid(
            row=2, column=2, sticky="w")
        self.btn_interval = tk.Button(f, text="▶ 인터벌 촬영 시작", bg="#2e7d32", fg="white",
                                      font=("맑은 고딕", 11, "bold"), command=self.toggle_interval)
        self.btn_interval.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 2))
        self.lbl_status = ttk.Label(f, text="대기 중", font=("맑은 고딕", 10))
        self.lbl_status.grid(row=4, column=0, columnspan=3, sticky="w")

        # 로그
        f = ttk.LabelFrame(panel, text="기록", padding=4)
        f.pack(fill="both", expand=True)
        self.log = tk.Listbox(f, height=6, width=34)
        self.log.pack(fill="both", expand=True)

        self.root.bind("<space>", lambda e: self.snapshot())

    def _load_into_ui(self) -> None:
        s = self.s
        self.v_res.set(s.resolution or "기본값")
        self.v_dir.set(s.save_dir)
        self.v_prefix.set(s.prefix)
        self.v_fmt.set(s.image_format)
        self.v_quality.set(s.jpeg_quality)
        self.v_datedir.set(s.date_subfolder)
        self.v_overlay.set(s.timestamp_overlay)
        self.v_ival.set(f"{s.interval_value:g}")
        self.v_unit.set(s.interval_unit)
        self.v_max.set(str(s.max_shots))
        self.v_minfree.set(str(s.min_free_mb))

    def _read_ui(self) -> bool:
        """UI 값을 설정에 반영. 잘못된 값이면 False."""
        s = self.s
        try:
            ival = float(self.v_ival.get())
            if ival <= 0:
                raise ValueError
            s.interval_value = ival
        except ValueError:
            messagebox.showerror("입력 오류", "촬영 간격은 0보다 큰 숫자여야 합니다.")
            return False
        try:
            s.max_shots = max(0, int(self.v_max.get() or 0))
            s.min_free_mb = max(0, int(self.v_minfree.get() or 0))
            s.jpeg_quality = int(self.v_quality.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("입력 오류", "숫자 입력값을 확인하세요.")
            return False
        s.interval_unit = self.v_unit.get() or "초"
        s.resolution = self.v_res.get()
        s.save_dir = self.v_dir.get().strip()
        s.prefix = self.v_prefix.get().strip() or "cam"
        s.image_format = self.v_fmt.get() or "jpg"
        s.date_subfolder = bool(self.v_datedir.get())
        s.timestamp_overlay = bool(self.v_overlay.get())
        if not s.save_dir:
            messagebox.showerror("입력 오류", "저장 폴더를 지정하세요.")
            return False
        save_settings(s)
        return True

    # ============================================================== camera
    def refresh_cameras(self) -> None:
        if self.cam.is_open:
            return  # 연결 중에는 다시 검색하지 않음 (장치 충돌 방지)
        self.cb_cam.set("검색 중...")
        self.root.update_idletasks()

        def work():
            cams = list_cameras()
            self.events.put(("cams", cams))

        threading.Thread(target=work, daemon=True).start()

    def _set_cameras(self, cams) -> None:
        values = [f"카메라 {i}" for i in cams]
        self.cb_cam["values"] = values
        if not cams:
            self.cb_cam.set("카메라 없음")
            self.add_log("카메라를 찾지 못했습니다. USB 연결을 확인하세요.")
            return
        pick = self.s.camera_index if self.s.camera_index in cams else cams[0]
        self.cb_cam.set(f"카메라 {pick}")
        self.add_log(f"카메라 {len(cams)}대 발견: {', '.join(map(str, cams))}")
        if self.s.auto_connect:
            self.connect()

    def _selected_index(self):
        txt = self.v_cam.get()
        try:
            return int(txt.split()[-1])
        except (ValueError, IndexError):
            return None

    def toggle_camera(self) -> None:
        if self.cam.is_open:
            self.disconnect()
        else:
            self.connect()

    def connect(self) -> None:
        idx = self._selected_index()
        if idx is None:
            messagebox.showwarning("카메라", "카메라를 선택하세요.")
            return
        self.s.camera_index = idx
        self.s.resolution = self.v_res.get()
        w, h = self.s.resolution_wh()
        self.btn_connect.config(text="연결 중...", state="disabled")

        def work():
            try:
                size = self.cam.open(idx, w, h)
                self.events.put(("connected", idx, size))
            except Exception as e:  # noqa: BLE001
                self.events.put(("connect_fail", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def disconnect(self) -> None:
        if self.interval and self.interval.running:
            if not messagebox.askyesno("확인", "인터벌 촬영 중입니다. 중지하고 연결을 끊을까요?"):
                return
            self.interval.stop()
        self.cam.close()
        self.btn_connect.config(text="연결")
        self.lbl_caminfo.config(text="-")
        self.preview.config(image="", text="카메라 연결 끊김")
        self._photo = None
        self.add_log("카메라 연결 해제")

    # ============================================================= capture
    def choose_dir(self) -> None:
        d = filedialog.askdirectory(initialdir=self.v_dir.get() or None, title="저장 폴더 선택")
        if d:
            self.v_dir.set(d)

    def snapshot(self) -> None:
        frame = self.cam.latest_frame()
        if frame is None:
            messagebox.showwarning("촬영", "카메라 영상이 없습니다.")
            return
        if not self._read_ui():
            return
        try:
            path = save_frame(frame, self.s)
            self.add_log(f"수동 저장: {path.name}")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("저장 실패", str(e))

    def toggle_interval(self) -> None:
        if self.interval and self.interval.running:
            self.interval.stop()
            return
        if not self.cam.is_open:
            messagebox.showwarning("인터벌 촬영", "먼저 카메라를 연결하세요.")
            return
        if not self._read_ui():
            return
        self.interval = IntervalCapture(
            self.cam.latest_frame,
            self.s,
            on_saved=lambda p, n: self.events.put(("saved", p, n)),
            on_error=lambda m: self.events.put(("error", m)),
            on_stopped=lambda r: self.events.put(("stopped", r)),
        )
        self.interval.start()
        self.btn_interval.config(text="■ 인터벌 촬영 중지", bg="#c62828")
        self.add_log(f"인터벌 촬영 시작: {self.s.interval_value:g}{self.s.interval_unit} 간격 → {self.s.save_dir}")

    # =============================================================== ticks
    def _tick_preview(self) -> None:
        frame = self.cam.latest_frame() if self.cam.is_open else None
        if frame is not None:
            lw = max(1, self.preview.winfo_width())
            lh = max(1, self.preview.winfo_height())
            h, w = frame.shape[:2]
            scale = min(lw / w, lh / h)
            if scale > 0:
                size = (max(1, int(w * scale)), max(1, int(h * scale)))
                frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._photo = ImageTk.PhotoImage(Image.fromarray(rgb))
                self.preview.config(image=self._photo, text="")
        self._drain_events()
        self.root.after(self.PREVIEW_MS, self._tick_preview)

    def _tick_status(self) -> None:
        if self.cam.index is not None and self.cam.is_open:
            self.lbl_caminfo.config(text=f"카메라 {self.cam.index} · {self.cam.fps:.1f} fps")
        elif self.cam.index is not None and not self.cam.is_open:
            self.lbl_caminfo.config(text="연결 끊김! USB를 확인하세요", foreground="red")
        if self.interval and self.interval.running:
            sec = int(round(self.interval.seconds_to_next()))
            hh, rem = divmod(sec, 3600)
            mm, ss = divmod(rem, 60)
            left = f"{hh:d}:{mm:02d}:{ss:02d}" if hh else f"{mm:02d}:{ss:02d}"
            self.lbl_status.config(text=f"촬영 중 · {self.interval.count}장 저장 · 다음 촬영 {left} 후")
        self.root.after(200, self._tick_status)

    def _drain_events(self) -> None:
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                return
            kind = ev[0]
            if kind == "cams":
                self._set_cameras(ev[1])
            elif kind == "connected":
                _, idx, (w, h) = ev
                self.btn_connect.config(text="연결 해제", state="normal")
                self.lbl_caminfo.config(text=f"카메라 {idx} · {w}x{h}", foreground="")
                self.add_log(f"카메라 {idx} 연결됨 ({w}x{h})")
                save_settings(self.s)
            elif kind == "connect_fail":
                self.btn_connect.config(text="연결", state="normal")
                self.add_log(ev[1])
                messagebox.showerror("카메라 연결 실패", ev[1])
            elif kind == "saved":
                self.add_log(f"[{ev[2]}] {Path(ev[1]).name}")
            elif kind == "error":
                self.add_log(ev[1])
            elif kind == "stopped":
                self.btn_interval.config(text="▶ 인터벌 촬영 시작", bg="#2e7d32")
                n = self.interval.count if self.interval else 0
                self.lbl_status.config(text=f"중지됨 ({ev[1]}) · 총 {n}장")
                self.add_log(f"인터벌 촬영 종료: {ev[1]} · 총 {n}장")

    def add_log(self, msg: str) -> None:
        self.log.insert("end", f"{datetime.now():%H:%M:%S} {msg}")
        if self.log.size() > 500:
            self.log.delete(0, self.log.size() - 500)
        self.log.see("end")

    # =============================================================== close
    def on_close(self) -> None:
        if self.interval and self.interval.running:
            if not messagebox.askyesno("종료", "인터벌 촬영 중입니다. 종료할까요?"):
                return
            self.interval.stop()
        try:
            self._read_ui()
        except Exception:  # noqa: BLE001
            pass
        self.cam.close()
        self.root.destroy()


def run() -> None:
    if sys.platform.startswith("win"):
        try:  # 고해상도 모니터에서 글자 흐림 방지
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()
