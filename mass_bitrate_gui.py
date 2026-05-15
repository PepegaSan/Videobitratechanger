#!/usr/bin/env python3
"""Mass bitrate changer GUI for folders of videos.

Rule:
- Target bitrate is resolution-based, editable in GUI.
- Effective target never exceeds source bitrate.
- If source bitrate is already <= rule, file is skipped by default.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mass_bitrate_gui_i18n import LANG_CODES, LANG_DE, LANG_EN, tr


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".wmv",
    ".webm",
    ".m4v",
    ".ts",
    ".flv",
}

RULE_ORDER = [2160, 1440, 1080, 720, 480, 360, 0]
BUILTIN_PRESETS: Dict[str, Dict[int, int]] = {
    "Standard": {2160: 12000, 1440: 8000, 1080: 5000, 720: 2800, 480: 1500, 360: 900, 0: 700},
    "Leicht reduziert": {2160: 8000, 1440: 6000, 1080: 4000, 720: 2000, 480: 1000, 360: 800, 0: 700},
    "Reduziert": {2160: 6000, 1440: 4000, 1080: 3000, 720: 1500, 480: 800, 360: 600, 0: 500},
}


@dataclass
class VideoInfo:
    path: Path
    width: int
    height: int
    source_size_bytes: Optional[int]
    source_kbps: Optional[int]
    target_rule_kbps: Optional[int]
    effective_target_kbps: Optional[int]
    estimated_output_bytes: Optional[int]
    estimated_saved_bytes: Optional[int]
    estimated_saved_pct: Optional[float]
    action: str
    reason: str


def is_tool_available(name: str) -> bool:
    try:
        completed = subprocess.run(
            [name, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return completed.returncode == 0
    except Exception:
        return False


def run_ffprobe(path: Path) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_entries",
        "stream=width,height,bit_rate",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format=bit_rate",
        str(path),
    ]
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if completed.returncode != 0:
        return None, None, None

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return None, None, None

    streams = payload.get("streams") or []
    video_stream = streams[0] if streams else None
    if not video_stream:
        return None, None, None

    width = int(video_stream["width"]) if video_stream.get("width") is not None else None
    height = int(video_stream["height"]) if video_stream.get("height") is not None else None

    stream_bitrate_raw = video_stream.get("bit_rate")
    format_bitrate_raw = (payload.get("format") or {}).get("bit_rate")
    bitrate_bps = None
    for raw in (stream_bitrate_raw, format_bitrate_raw):
        if raw is None:
            continue
        try:
            bitrate_bps = int(raw)
            break
        except (TypeError, ValueError):
            continue

    kbps = int(bitrate_bps / 1000) if bitrate_bps and bitrate_bps > 0 else None
    return width, height, kbps


def fmt_mb_from_bytes(value: Optional[int]) -> str:
    if value is None:
        return "-"
    return f"{(value / (1024 * 1024)):.1f}"


def estimate_sizes(source_size_bytes: int, source_kbps: int, target_kbps: int) -> Tuple[int, int, float]:
    if source_size_bytes <= 0 or source_kbps <= 0 or target_kbps <= 0:
        return source_size_bytes, 0, 0.0
    ratio = min(1.0, target_kbps / source_kbps)
    estimated_output = int(source_size_bytes * ratio)
    saved = max(0, source_size_bytes - estimated_output)
    saved_pct = (saved / source_size_bytes) * 100.0 if source_size_bytes > 0 else 0.0
    return estimated_output, saved, saved_pct


class BitrateChangerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.geometry("1180x800")
        self.root.minsize(1080, 760)

        self.lang_var = tk.StringVar(value=LANG_DE)
        self._jobs_cur = 0
        self._jobs_tot = 0
        self._ui: Dict[str, object] = {}

        self.video_rows: List[VideoInfo] = []
        self.worker: Optional[threading.Thread] = None
        self.rename_worker: Optional[threading.Thread] = None
        self.scan_worker: Optional[threading.Thread] = None
        self._scan_render_after_id: Optional[str] = None
        self._scan_in_path: Optional[Path] = None
        self._scan_generation: int = 0
        self.stop_flag = threading.Event()
        self.msg_queue: queue.Queue = queue.Queue()
        self._rules_from_config = False
        self._pending_window_geometry: Optional[str] = None
        self._geometry_save_after_id: Optional[str] = None
        self._path_to_tree_iid: Dict[str, str] = {}

        self.config_path = Path(__file__).with_name("mass_bitrate_gui_config.json")

        self.input_folder_var = tk.StringVar()
        self.output_folder_var = tk.StringVar()
        self.output_beside_source_var = tk.BooleanVar(value=False)
        self._last_manual_output_folder: str = ""
        self.recursive_var = tk.BooleanVar(value=True)
        self.only_lower_var = tk.BooleanVar(value=True)
        self.audio_mode_var = tk.StringVar(value="copy")
        self.codec_var = tk.StringVar(value="libx264")
        self.suffix_var = tk.StringVar(value="_bitrate")
        self.output_mp4_var = tk.BooleanVar(value=False)
        self.strip_autobitrate_suffix_var = tk.BooleanVar(value=False)
        self.rename_only_video_var = tk.BooleanVar(value=True)
        self.post_success_action_var = tk.StringVar(value="keep")
        self.preset_name_var = tk.StringVar(value="Standard")
        self.new_preset_name_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.progress_var = tk.DoubleVar(value=0.0)
        self.jobs_text_var = tk.StringVar()

        self.custom_presets: Dict[str, Dict[int, int]] = {}
        self.rule_vars: Dict[int, tk.StringVar] = {
            threshold: tk.StringVar(value=str(BUILTIN_PRESETS["Standard"][threshold])) for threshold in RULE_ORDER
        }
        self._load_settings()
        self.status_var.set(tr(self._lang(), "status_ready"))
        self._refresh_jobs_label()

        self._build_ui()
        self._refresh_preset_combobox()
        if not self._rules_from_config:
            self._apply_selected_preset(show_status=False)
        self._restore_window_geometry()
        self.root.bind("<Configure>", self._on_root_configure)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(150, self._poll_queue)

    def _lang(self) -> str:
        v = (self.lang_var.get() or LANG_DE).strip().lower()
        return v if v in LANG_CODES else LANG_DE

    def _refresh_jobs_label(self) -> None:
        self.jobs_text_var.set(tr(self._lang(), "jobs_fmt", cur=self._jobs_cur, tot=self._jobs_tot))

    def _on_language_change(self) -> None:
        self._apply_ui_language()
        self._refresh_jobs_label()
        self.status_var.set(tr(self._lang(), "status_ready"))
        self._save_settings()

    def _apply_ui_language(self) -> None:
        L = self._lang()
        self.root.title(tr(L, "app_title"))
        u = self._ui
        u["lf_folders"].configure(text=tr(L, "lf_folders"))
        u["lbl_input"].configure(text=tr(L, "lbl_input_folder"))
        u["lbl_output"].configure(text=tr(L, "lbl_output_folder"))
        u["btn_in"].configure(text=tr(L, "btn_browse"))
        u["btn_out"].configure(text=tr(L, "btn_browse"))
        u["btn_auto"].configure(text=tr(L, "btn_auto_output"))
        u["chk_beside"].configure(text=tr(L, "chk_output_beside_source"))
        u["lf_rename"].configure(text=tr(L, "lf_rename"))
        u["btn_preview"].configure(text=tr(L, "btn_preview"))
        u["btn_rename"].configure(text=tr(L, "btn_rename"))
        u["chk_rename_vid"].configure(text=tr(L, "chk_rename_video_only"))
        u["lf_opts"].configure(text=tr(L, "lf_options"))
        u["lbl_lang"].configure(text=tr(L, "lbl_language"))
        u["rb_lang_de"].configure(text=tr(L, "lang_de"))
        u["rb_lang_en"].configure(text=tr(L, "lang_en"))
        u["chk_recursive"].configure(text=tr(L, "chk_recursive"))
        u["chk_only_lower"].configure(text=tr(L, "chk_only_lower"))
        u["lbl_vcodec"].configure(text=tr(L, "lbl_video_codec"))
        u["lbl_audio"].configure(text=tr(L, "lbl_audio"))
        u["lbl_suffix"].configure(text=tr(L, "lbl_suffix"))
        u["chk_mp4"].configure(text=tr(L, "chk_output_mp4"))
        u["chk_strip"].configure(text=tr(L, "chk_strip_bitrate"))
        u["lbl_post"].configure(text=tr(L, "lbl_after_success"))
        u["lf_rules"].configure(text=tr(L, "lf_rules"))
        u["lbl_preset"].configure(text=tr(L, "lbl_preset"))
        u["btn_load_preset"].configure(text=tr(L, "btn_load_preset"))
        u["lbl_newpreset"].configure(text=tr(L, "lbl_new_preset"))
        u["btn_save_preset"].configure(text=tr(L, "btn_save_preset"))
        for t in RULE_ORDER:
            kb_key = f"lbl_kbps_{t}"
            if kb_key in u:
                u[kb_key].configure(text=tr(L, "lbl_rule_kbps"))
        for th, key in (
            ("file", "th_file"),
            ("resolution", "th_resolution"),
            ("source", "th_source"),
            ("rule", "th_rule"),
            ("target", "th_target"),
            ("est_out_mb", "th_est_out"),
            ("save_mb", "th_save"),
            ("save_pct", "th_save_pct"),
            ("action", "th_action"),
            ("reason", "th_reason"),
        ):
            self.tree.heading(th, text=tr(L, key))
        self.tree_menu.entryconfigure(0, label=tr(L, "mnu_explorer_file"))
        self.tree_menu.entryconfigure(1, label=tr(L, "mnu_explorer_folder"))
        u["btn_start"].configure(text=tr(L, "btn_start"))
        u["btn_stop"].configure(text=tr(L, "btn_stop"))
        busy = False
        try:
            busy = self.scan_worker is not None and self.scan_worker.is_alive()
        except Exception:
            pass
        self._set_scan_ui_busy(busy)

    def _build_ui(self) -> None:
        self._ui.clear()
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        folder_frame = ttk.LabelFrame(outer, text="", padding=10)
        self._ui["lf_folders"] = folder_frame
        folder_frame.pack(fill=tk.X)
        folder_frame.columnconfigure(1, weight=1)
        folder_frame.columnconfigure(3, weight=1)

        lbl_in = ttk.Label(folder_frame, text="")
        self._ui["lbl_input"] = lbl_in
        lbl_in.grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(folder_frame, textvariable=self.input_folder_var).grid(row=0, column=1, sticky="ew", pady=4)
        btn_in = ttk.Button(folder_frame, text="", command=self._choose_input_folder)
        self._ui["btn_in"] = btn_in
        btn_in.grid(row=0, column=2, padx=6, pady=4)

        lbl_out = ttk.Label(folder_frame, text="")
        self._ui["lbl_output"] = lbl_out
        lbl_out.grid(row=1, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(folder_frame, textvariable=self.output_folder_var).grid(row=1, column=1, sticky="ew", pady=4)
        btn_out = ttk.Button(folder_frame, text="", command=self._choose_output_folder)
        self._ui["btn_out"] = btn_out
        btn_out.grid(row=1, column=2, padx=6, pady=4)
        btn_auto = ttk.Button(folder_frame, text="", command=self._set_default_output)
        self._ui["btn_auto"] = btn_auto
        btn_auto.grid(row=1, column=3, sticky="w", pady=4)
        chk_beside = ttk.Checkbutton(
            folder_frame,
            text="",
            variable=self.output_beside_source_var,
            command=self._on_output_beside_source_toggle,
        )
        self._ui["chk_beside"] = chk_beside
        chk_beside.grid(row=1, column=4, sticky="w", padx=(12, 4), pady=4)
        ttk.Button(folder_frame, text="(i)", width=3, command=self._show_output_beside_source_hint).grid(
            row=1, column=5, sticky="w", pady=4
        )

        rename_frame = ttk.LabelFrame(outer, text="", padding=10)
        self._ui["lf_rename"] = rename_frame
        rename_frame.pack(fill=tk.X, pady=(10, 0))
        rename_frame.columnconfigure(2, weight=1)
        btn_preview = ttk.Button(rename_frame, text="", command=self._preview_bitrate_renames)
        self._ui["btn_preview"] = btn_preview
        btn_preview.grid(row=0, column=0, sticky="w")
        btn_rename = ttk.Button(rename_frame, text="", command=self._apply_bitrate_renames)
        self._ui["btn_rename"] = btn_rename
        btn_rename.grid(row=0, column=1, sticky="w", padx=(8, 0))
        chk_rename_vid = ttk.Checkbutton(rename_frame, text="", variable=self.rename_only_video_var)
        self._ui["chk_rename_vid"] = chk_rename_vid
        chk_rename_vid.grid(row=0, column=2, sticky="w", padx=(16, 0))
        ttk.Button(rename_frame, text="(i)", width=3, command=self._show_bitrate_rename_hint).grid(
            row=0, column=3, sticky="w", padx=(8, 0)
        )

        opts_frame = ttk.LabelFrame(outer, text="", padding=10)
        self._ui["lf_opts"] = opts_frame
        opts_frame.pack(fill=tk.X, pady=(10, 0))
        opts_frame.columnconfigure(5, weight=1)

        lang_row = ttk.Frame(opts_frame)
        lang_row.grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))
        lbl_lang = ttk.Label(lang_row, text="")
        self._ui["lbl_lang"] = lbl_lang
        lbl_lang.pack(side=tk.LEFT)
        rb_de = ttk.Radiobutton(lang_row, text="", value=LANG_DE, variable=self.lang_var, command=self._on_language_change)
        self._ui["rb_lang_de"] = rb_de
        rb_de.pack(side=tk.LEFT, padx=(10, 0))
        rb_en = ttk.Radiobutton(lang_row, text="", value=LANG_EN, variable=self.lang_var, command=self._on_language_change)
        self._ui["rb_lang_en"] = rb_en
        rb_en.pack(side=tk.LEFT, padx=(10, 0))

        chk_recursive = ttk.Checkbutton(opts_frame, text="", variable=self.recursive_var)
        self._ui["chk_recursive"] = chk_recursive
        chk_recursive.grid(row=1, column=0, sticky="w", padx=(0, 12))
        chk_only_lower = ttk.Checkbutton(opts_frame, text="", variable=self.only_lower_var)
        self._ui["chk_only_lower"] = chk_only_lower
        chk_only_lower.grid(row=1, column=1, sticky="w", padx=(0, 12))
        lbl_vcodec = ttk.Label(opts_frame, text="")
        self._ui["lbl_vcodec"] = lbl_vcodec
        lbl_vcodec.grid(row=1, column=2, sticky="w")
        ttk.Combobox(
            opts_frame,
            values=["libx264", "libx265", "h264_nvenc", "hevc_nvenc", "libvpx-vp9"],
            textvariable=self.codec_var,
            state="readonly",
            width=14,
        ).grid(row=1, column=3, sticky="w", padx=(6, 12))
        lbl_audio = ttk.Label(opts_frame, text="")
        self._ui["lbl_audio"] = lbl_audio
        lbl_audio.grid(row=1, column=4, sticky="w")
        ttk.Combobox(
            opts_frame,
            values=["copy", "aac_128k"],
            textvariable=self.audio_mode_var,
            state="readonly",
            width=12,
        ).grid(row=1, column=5, sticky="w", padx=(6, 0))
        lbl_suffix = ttk.Label(opts_frame, text="")
        self._ui["lbl_suffix"] = lbl_suffix
        lbl_suffix.grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(opts_frame, width=16, textvariable=self.suffix_var).grid(row=2, column=1, sticky="w", pady=(8, 0))
        ttk.Button(opts_frame, text="(i)", width=3, command=self._show_suffix_hint).grid(
            row=2, column=2, sticky="w", padx=(6, 0), pady=(8, 0)
        )
        chk_mp4 = ttk.Checkbutton(opts_frame, text="", variable=self.output_mp4_var)
        self._ui["chk_mp4"] = chk_mp4
        chk_mp4.grid(row=2, column=3, sticky="w", padx=(12, 8), pady=(8, 0))
        chk_strip = ttk.Checkbutton(
            opts_frame,
            text="",
            variable=self.strip_autobitrate_suffix_var,
        )
        self._ui["chk_strip"] = chk_strip
        chk_strip.grid(row=2, column=4, columnspan=2, sticky="w", padx=(12, 0), pady=(8, 0))
        lbl_post = ttk.Label(opts_frame, text="")
        self._ui["lbl_post"] = lbl_post
        lbl_post.grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            opts_frame,
            values=["keep", "move_to_backup", "delete_original"],
            textvariable=self.post_success_action_var,
            state="readonly",
            width=18,
        ).grid(row=3, column=1, sticky="w", pady=(8, 0))
        ttk.Button(opts_frame, text="(i)", width=3, command=self._show_post_success_hint).grid(
            row=3, column=2, sticky="w", padx=(6, 0), pady=(8, 0)
        )

        rules_frame = ttk.LabelFrame(outer, text="", padding=10)
        self._ui["lf_rules"] = rules_frame
        rules_frame.pack(fill=tk.X, pady=(10, 0))
        rules_frame.columnconfigure(6, weight=1)

        lbl_preset = ttk.Label(rules_frame, text="")
        self._ui["lbl_preset"] = lbl_preset
        lbl_preset.grid(row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 8))
        self.preset_combo = ttk.Combobox(
            rules_frame,
            textvariable=self.preset_name_var,
            state="readonly",
            width=22,
        )
        self.preset_combo.grid(row=0, column=1, columnspan=2, sticky="w", pady=(0, 8))
        self.preset_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_selected_preset(show_status=True))
        btn_load_preset = ttk.Button(rules_frame, text="", command=lambda: self._apply_selected_preset(show_status=True))
        self._ui["btn_load_preset"] = btn_load_preset
        btn_load_preset.grid(row=0, column=3, sticky="w", padx=(0, 12), pady=(0, 8))

        lbl_newpreset = ttk.Label(rules_frame, text="")
        self._ui["lbl_newpreset"] = lbl_newpreset
        lbl_newpreset.grid(row=0, column=4, sticky="e", padx=(0, 6), pady=(0, 8))
        ttk.Entry(rules_frame, width=20, textvariable=self.new_preset_name_var).grid(
            row=0, column=5, sticky="w", pady=(0, 8)
        )
        btn_save_preset = ttk.Button(rules_frame, text="", command=self._save_custom_preset)
        self._ui["btn_save_preset"] = btn_save_preset
        btn_save_preset.grid(row=0, column=6, sticky="w", padx=(6, 0), pady=(0, 8))

        entries = [
            (2160, ">= 2160p"),
            (1440, ">= 1440p"),
            (1080, ">= 1080p"),
            (720, ">= 720p"),
            (480, ">= 480p"),
            (360, ">= 360p"),
            (0, "< 360p"),
        ]
        # Stable 2-column grid prevents cramped/shifted controls on smaller widths.
        for idx, (threshold, label) in enumerate(entries):
            col_group = idx // 4  # 0 => left block, 1 => right block
            r = 1 + (idx % 4)
            c = col_group * 3
            ttk.Label(rules_frame, text=label).grid(row=r, column=c, sticky="w", padx=(0, 6), pady=4)
            ttk.Entry(rules_frame, width=8, textvariable=self.rule_vars[threshold]).grid(row=r, column=c + 1, pady=4)
            lbl_kbps = ttk.Label(rules_frame, text="")
            lbl_kbps.grid(row=r, column=c + 2, sticky="w", padx=(4, 20), pady=4)
            self._ui[f"lbl_kbps_{threshold}"] = lbl_kbps

        action_frame = ttk.Frame(outer)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        self._btn_scan = ttk.Button(action_frame, text="", command=self.scan_folder)
        self._btn_scan.pack(side=tk.LEFT)
        self._ui["btn_scan"] = self._btn_scan
        btn_start = ttk.Button(action_frame, text="", command=self.start_conversion)
        self._ui["btn_start"] = btn_start
        btn_start.pack(side=tk.LEFT, padx=(8, 0))
        btn_stop = ttk.Button(action_frame, text="", command=self.stop_conversion)
        self._ui["btn_stop"] = btn_stop
        btn_stop.pack(side=tk.LEFT, padx=(8, 0))

        columns = ("file", "resolution", "source", "rule", "target", "est_out_mb", "save_mb", "save_pct", "action", "reason")
        table_frame = ttk.Frame(outer)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        widths = {
            "file": 290,
            "resolution": 95,
            "source": 110,
            "rule": 90,
            "target": 90,
            "est_out_mb": 95,
            "save_mb": 100,
            "save_pct": 95,
            "action": 90,
            "reason": 250,
        }
        for col in columns:
            self.tree.heading(col, text="")
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=y_scroll.set)
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="", command=self._explorer_select_current_file)
        self.tree_menu.add_command(label="", command=self._explorer_open_current_folder)
        self._apply_tree_row_styles()

        bottom = ttk.Frame(outer)
        bottom.pack(fill=tk.X, pady=(10, 0))
        bottom.grid_columnconfigure(0, weight=1)
        ttk.Progressbar(bottom, maximum=100, variable=self.progress_var).grid(row=0, column=0, sticky="ew")

        bottom_row = ttk.Frame(bottom)
        bottom_row.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        bottom_row.grid_columnconfigure(0, weight=1)

        ttk.Label(bottom_row, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(bottom_row, textvariable=self.jobs_text_var).grid(row=0, column=1, sticky="e")

        self._apply_ui_language()

    def _choose_input_folder(self) -> None:
        folder = filedialog.askdirectory(title=tr(self._lang(), "dlg_input_title"))
        if not folder:
            return
        self.input_folder_var.set(folder)
        if self.output_beside_source_var.get():
            self._sync_output_with_source_if_enabled()
        elif not self.output_folder_var.get().strip():
            self._set_default_output()

    def _choose_output_folder(self) -> None:
        folder = filedialog.askdirectory(title=tr(self._lang(), "dlg_output_title"))
        if folder:
            self.output_folder_var.set(folder)
            self._last_manual_output_folder = folder
            if self.output_beside_source_var.get():
                self.output_beside_source_var.set(False)

    def _set_default_output(self) -> None:
        inp = self.input_folder_var.get().strip()
        if not inp:
            return
        if self.output_beside_source_var.get():
            self._sync_output_with_source_if_enabled()
            return
        self.output_folder_var.set(str(Path(inp) / "_converted"))

    def _show_suffix_hint(self) -> None:
        L = self._lang()
        messagebox.showinfo(tr(L, "dlg_suffix_title"), tr(L, "dlg_suffix_body"))

    def _show_bitrate_rename_hint(self) -> None:
        L = self._lang()
        messagebox.showinfo(tr(L, "dlg_rename_title"), tr(L, "dlg_rename_body"))

    def _show_output_beside_source_hint(self) -> None:
        L = self._lang()
        messagebox.showinfo(tr(L, "dlg_output_beside_title"), tr(L, "dlg_output_beside_body"))

    def _on_output_beside_source_toggle(self) -> None:
        if self.output_beside_source_var.get():
            cur = self.output_folder_var.get().strip()
            if cur and not self._same_folder(Path(cur), Path(self.input_folder_var.get().strip() or ".")):
                self._last_manual_output_folder = cur
            self._sync_output_with_source_if_enabled()
        else:
            if self._last_manual_output_folder.strip():
                self.output_folder_var.set(self._last_manual_output_folder.strip())
            else:
                self._set_default_output()
        self._save_settings()

    def _sync_output_with_source_if_enabled(self) -> None:
        if not self.output_beside_source_var.get():
            return
        inp = self.input_folder_var.get().strip()
        if inp:
            self.output_folder_var.set(inp)

    def _show_post_success_hint(self) -> None:
        L = self._lang()
        messagebox.showinfo(tr(L, "dlg_post_title"), tr(L, "dlg_post_body"))

    def _apply_tree_row_styles(self) -> None:
        """Pastel row backgrounds via ttk.Treeview tags (requires a theme that honors Treeview maps)."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", rowheight=26)
        # Base row
        style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", foreground="#1a1a1a")
        style.map("Treeview", background=[("selected", "#4a90d9")], foreground=[("selected", "#ffffff")])

        self.tree.tag_configure("pending", background="#e3f4fb", foreground="#1a1a1a")
        self.tree.tag_configure("skip", background="#f4f4f4", foreground="#555555")
        self.tree.tag_configure("done", background="#d8f0e0", foreground="#14321f")
        self.tree.tag_configure("fail", background="#f8e4e4", foreground="#4a1515")

    def _get_rule_map(self) -> Optional[Dict[int, int]]:
        L = self._lang()
        dlg = tr(L, "dlg_rule_error")
        result: Dict[int, int] = {}
        for threshold, var in self.rule_vars.items():
            raw = var.get().strip()
            if not raw:
                messagebox.showerror(dlg, tr(L, "err_rule_empty", threshold=threshold))
                return None
            try:
                value = int(raw)
            except ValueError:
                messagebox.showerror(dlg, tr(L, "err_rule_invalid", threshold=threshold, raw=raw))
                return None
            if value <= 0:
                messagebox.showerror(dlg, tr(L, "err_rule_positive", threshold=threshold))
                return None
            result[threshold] = value
        return result

    def _preset_values(self) -> Dict[str, Dict[int, int]]:
        all_presets = dict(BUILTIN_PRESETS)
        all_presets.update(self.custom_presets)
        return all_presets

    def _refresh_preset_combobox(self) -> None:
        values = list(BUILTIN_PRESETS.keys()) + sorted(self.custom_presets.keys(), key=str.lower)
        self.preset_combo.configure(values=values)
        if self.preset_name_var.get().strip() not in values:
            self.preset_name_var.set("Standard")

    def _apply_selected_preset(self, show_status: bool) -> None:
        name = self.preset_name_var.get().strip()
        preset = self._preset_values().get(name)
        if not preset:
            return
        for threshold in RULE_ORDER:
            self.rule_vars[threshold].set(str(preset[threshold]))
        if show_status:
            self.status_var.set(tr(self._lang(), "status_preset_loaded", name=name))
        self._save_settings()

    def _save_custom_preset(self) -> None:
        name = self.new_preset_name_var.get().strip()
        L = self._lang()
        dlg = tr(L, "dlg_preset")
        if not name:
            messagebox.showerror(dlg, tr(L, "err_preset_name_empty"))
            return
        if name in BUILTIN_PRESETS:
            messagebox.showerror(dlg, tr(L, "err_preset_builtin"))
            return
        rules = self._get_rule_map()
        if rules is None:
            return
        self.custom_presets[name] = rules
        self.preset_name_var.set(name)
        self._refresh_preset_combobox()
        self.new_preset_name_var.set("")
        self.status_var.set(tr(self._lang(), "status_preset_saved", name=name))
        self._save_settings()

    def _load_settings(self) -> None:
        if not self.config_path.exists():
            return
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            return

        lg = str(payload.get("language", LANG_DE)).strip().lower()
        if lg in LANG_CODES:
            self.lang_var.set(lg)

        self.input_folder_var.set(str(payload.get("input_folder", "")))
        self.output_folder_var.set(str(payload.get("output_folder", "")))
        self.output_beside_source_var.set(bool(payload.get("output_beside_source", False)))
        self.recursive_var.set(bool(payload.get("recursive", True)))
        self.only_lower_var.set(bool(payload.get("only_lower", True)))
        self.audio_mode_var.set(str(payload.get("audio_mode", "copy")))
        self.codec_var.set(str(payload.get("codec", "libx264")))
        self.suffix_var.set(str(payload.get("suffix", "_bitrate")))
        self.output_mp4_var.set(bool(payload.get("output_mp4", False)))
        self.strip_autobitrate_suffix_var.set(bool(payload.get("strip_autobitrate_suffix", False)))
        self.rename_only_video_var.set(bool(payload.get("rename_only_video", True)))
        self.post_success_action_var.set(str(payload.get("post_success_action", "keep")))
        self.preset_name_var.set(str(payload.get("preset_name", "Standard")))
        geom = str(payload.get("window_geometry", "")).strip()
        if geom:
            self._pending_window_geometry = geom

        if self.output_beside_source_var.get():
            self._sync_output_with_source_if_enabled()

        raw_custom = payload.get("custom_presets", {})
        custom: Dict[str, Dict[int, int]] = {}
        if isinstance(raw_custom, dict):
            for name, values in raw_custom.items():
                if not isinstance(name, str) or not isinstance(values, dict):
                    continue
                try:
                    normalized = {int(k): int(v) for k, v in values.items()}
                except Exception:
                    continue
                if all(t in normalized for t in RULE_ORDER):
                    custom[name] = normalized
        self.custom_presets = custom

        raw_rules = payload.get("rule_values", {})
        if isinstance(raw_rules, dict):
            for threshold in RULE_ORDER:
                if str(threshold) in raw_rules:
                    self.rule_vars[threshold].set(str(raw_rules[str(threshold)]))
                    self._rules_from_config = True

    def _save_settings(self) -> None:
        try:
            existing: dict = {}
            if self.config_path.exists():
                try:
                    existing = json.loads(self.config_path.read_text(encoding="utf-8"))
                    if not isinstance(existing, dict):
                        existing = {}
                except Exception:
                    existing = {}

            rule_values = {str(k): self.rule_vars[k].get().strip() for k in RULE_ORDER}
            custom_serialized = {
                name: {str(k): int(v) for k, v in values.items()} for name, values in self.custom_presets.items()
            }
            geom = ""
            try:
                if int(self.root.winfo_viewable()) == 1:
                    g = self.root.winfo_geometry()
                    if re.match(r"^\d+x\d+\+\d+\+\d+$", g or ""):
                        _w, _h = map(int, g.split("+", 1)[0].split("x", 1))
                        if _w >= 200 and _h >= 200:
                            geom = g
            except Exception:
                geom = ""

            payload = dict(existing)
            payload.update(
                {
                    "language": self._lang(),
                    "input_folder": self.input_folder_var.get().strip(),
                    "output_folder": self.output_folder_var.get().strip(),
                    "output_beside_source": self.output_beside_source_var.get(),
                    "recursive": self.recursive_var.get(),
                    "only_lower": self.only_lower_var.get(),
                    "audio_mode": self.audio_mode_var.get().strip(),
                    "codec": self.codec_var.get().strip(),
                    "suffix": self.suffix_var.get(),
                    "output_mp4": self.output_mp4_var.get(),
                    "strip_autobitrate_suffix": self.strip_autobitrate_suffix_var.get(),
                    "rename_only_video": self.rename_only_video_var.get(),
                    "post_success_action": self.post_success_action_var.get().strip(),
                    "preset_name": self.preset_name_var.get().strip(),
                    "rule_values": rule_values,
                    "custom_presets": custom_serialized,
                }
            )
            if geom:
                payload["window_geometry"] = geom
            self.config_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            # Settings persistence should never crash the tool.
            pass

    def _on_close(self) -> None:
        self._save_settings()
        self.root.destroy()

    _GEOM_RE = re.compile(r"^(\d+)x(\d+)\+(\d+)\+(\d+)$")

    def _parse_geometry(self, geom: str) -> Optional[Tuple[int, int, int, int]]:
        m = self._GEOM_RE.match(geom.strip())
        if not m:
            return None
        return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))

    def _is_geometry_on_screen(self, w: int, h: int, x: int, y: int) -> bool:
        try:
            vx = int(self.root.winfo_vrootx())
            vy = int(self.root.winfo_vrooty())
            vw = int(self.root.winfo_vrootwidth())
            vh = int(self.root.winfo_vrootheight())
        except Exception:
            return True
        margin = 80
        if w < 200 or h < 200 or w > vw + 200 or h > vh + 200:
            return False
        if x + w < vx + margin or x > vx + vw - margin:
            return False
        if y + h < vy + margin or y > vy + vh - margin:
            return False
        return True

    def _center_window_on_screen(self) -> None:
        self.root.update_idletasks()
        w = max(self.root.winfo_width(), self.root.winfo_reqwidth(), 1180)
        h = max(self.root.winfo_height(), self.root.winfo_reqheight(), 800)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _restore_window_geometry(self) -> None:
        geom = self._pending_window_geometry
        self._pending_window_geometry = None
        if not geom:
            self._center_window_on_screen()
            return
        parsed = self._parse_geometry(geom)
        if not parsed:
            self._center_window_on_screen()
            return
        w, h, x, y = parsed
        try:
            min_w, min_h = self.root.minsize()
        except Exception:
            min_w, min_h = 1080, 760
        w = max(w, min_w)
        h = max(h, min_h)
        if not self._is_geometry_on_screen(w, h, x, y):
            self._center_window_on_screen()
            return
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _on_root_configure(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return
        if self._geometry_save_after_id is not None:
            try:
                self.root.after_cancel(self._geometry_save_after_id)
            except Exception:
                pass
        self._geometry_save_after_id = self.root.after(400, self._flush_geometry_save)

    def _flush_geometry_save(self) -> None:
        self._geometry_save_after_id = None
        self._save_settings()

    @staticmethod
    def _pick_rule_for_height(height: int, rules: Dict[int, int]) -> int:
        for threshold in sorted(rules.keys(), reverse=True):
            if height >= threshold:
                return rules[threshold]
        return rules[min(rules.keys())]

    def _iter_video_files(self, folder: Path, recursive: bool) -> List[Path]:
        pattern = "**/*" if recursive else "*"
        files = []
        for p in folder.glob(pattern):
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:
                files.append(p)
        files.sort()
        return files

    def _get_selected_video_path(self) -> Optional[Path]:
        selected = self.tree.selection()
        if not selected:
            return None
        item = selected[0]
        item_index = self.tree.index(item)
        if item_index < 0 or item_index >= len(self.video_rows):
            return None
        return self.video_rows[item_index].path

    def _on_tree_right_click(self, event: tk.Event) -> None:
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        self.tree.focus(row_id)
        self.tree_menu.tk_popup(event.x_root, event.y_root)

    def _explorer_select_current_file(self) -> None:
        path = self._get_selected_video_path()
        if not path:
            return
        if not path.exists():
            L = self._lang()
            messagebox.showerror(tr(L, "dlg_explorer"), tr(L, "err_file_not_found"))
            return
        subprocess.Popen(["explorer", "/select,", str(path)])

    def _explorer_open_current_folder(self) -> None:
        path = self._get_selected_video_path()
        if not path:
            return
        folder = path.parent
        if not folder.exists():
            L = self._lang()
            messagebox.showerror(tr(L, "dlg_explorer"), tr(L, "err_folder_not_found"))
            return
        subprocess.Popen(["explorer", str(folder)])

    def _analyze_single_file(self, file_path: Path, rules: Dict[int, int], only_lower: bool, lang: str) -> VideoInfo:
        width, height, source_kbps = run_ffprobe(file_path)
        if not width or not height:
            return VideoInfo(
                path=file_path,
                width=0,
                height=0,
                source_size_bytes=file_path.stat().st_size if file_path.exists() else None,
                source_kbps=None,
                target_rule_kbps=None,
                effective_target_kbps=None,
                estimated_output_bytes=None,
                estimated_saved_bytes=None,
                estimated_saved_pct=None,
                action="skip",
                reason=tr(lang, "reason_resolution"),
            )

        source_size = file_path.stat().st_size if file_path.exists() else None
        rule = self._pick_rule_for_height(height, rules)
        if source_kbps is None:
            return VideoInfo(
                path=file_path,
                width=width,
                height=height,
                source_size_bytes=source_size,
                source_kbps=None,
                target_rule_kbps=rule,
                effective_target_kbps=None,
                estimated_output_bytes=None,
                estimated_saved_bytes=None,
                estimated_saved_pct=None,
                action="skip",
                reason=tr(lang, "reason_bitrate_unknown"),
            )

        effective_target = min(source_kbps, rule)
        est_out = None
        est_save = None
        est_save_pct = None
        if source_size is not None:
            est_out, est_save, est_save_pct = estimate_sizes(source_size, source_kbps, effective_target)
        if only_lower and effective_target >= source_kbps:
            action = "skip"
            reason = tr(lang, "reason_no_gain")
        else:
            action = "convert"
            reason = tr(lang, "reason_reduce")

        return VideoInfo(
            path=file_path,
            width=width,
            height=height,
            source_size_bytes=source_size,
            source_kbps=source_kbps,
            target_rule_kbps=rule,
            effective_target_kbps=effective_target,
            estimated_output_bytes=est_out,
            estimated_saved_bytes=est_save,
            estimated_saved_pct=est_save_pct,
            action=action,
            reason=reason,
        )

    def _drain_msg_queue(self) -> None:
        """Drop pending UI messages so e.g. old row_state cannot repaint a freshly scanned tree."""
        while True:
            try:
                self.msg_queue.get_nowait()
            except queue.Empty:
                break

    def _cancel_scan_render(self) -> None:
        if self._scan_render_after_id is not None:
            try:
                self.root.after_cancel(self._scan_render_after_id)
            except Exception:
                pass
            self._scan_render_after_id = None

    def _set_scan_ui_busy(self, busy: bool) -> None:
        try:
            L = self._lang()
            self._btn_scan.configure(
                state=("disabled" if busy else "normal"),
                text=(tr(L, "btn_scan_busy") if busy else tr(L, "btn_scan")),
            )
        except Exception:
            pass

    def _scan_worker_job(self, scan_id: int, in_path: Path, files: List[Path], rules: Dict[int, int], lang: str) -> None:
        workers = min(8, max(2, (os.cpu_count() or 4)))
        rows_map: Dict[Path, VideoInfo] = {}
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                future_map = {
                    pool.submit(self._analyze_single_file, file_path, rules, self.only_lower_var.get(), lang): file_path
                    for file_path in files
                }
                processed = 0
                total_files = len(files)
                for future in as_completed(future_map):
                    file_path = future_map[future]
                    try:
                        rows_map[file_path] = future.result()
                    except Exception:
                        rows_map[file_path] = VideoInfo(
                            path=file_path,
                            width=0,
                            height=0,
                            source_size_bytes=file_path.stat().st_size if file_path.exists() else None,
                            source_kbps=None,
                            target_rule_kbps=None,
                            effective_target_kbps=None,
                            estimated_output_bytes=None,
                            estimated_saved_bytes=None,
                            estimated_saved_pct=None,
                            action="skip",
                            reason=tr(lang, "reason_scan_error"),
                        )
                    processed += 1
                    if processed % 16 == 0 or processed == total_files:
                        self.msg_queue.put(("scan_progress", (scan_id, processed, total_files)))

            video_rows = [rows_map[p] for p in files]
            self.msg_queue.put(("scan_done", (scan_id, in_path, video_rows)))
        except Exception as ex:
            self.msg_queue.put(("scan_error", (scan_id, str(ex))))

    def _schedule_scan_rows_render(self, scan_id: int, in_path: Path, rows: List[VideoInfo], start_idx: int, lang: str) -> None:
        self._cancel_scan_render()

        def tick(idx: int) -> None:
            if scan_id != self._scan_generation:
                return
            end = min(len(rows), idx + 40)
            for i in range(idx, end):
                row = rows[i]
                resolution = f"{row.width or '?'}x{row.height or '?'}"
                iid = str(i)
                self._path_to_tree_iid[str(row.path.resolve())] = iid
                tags = ("skip",) if row.action == "skip" else ("pending",)
                self.tree.insert(
                    "",
                    tk.END,
                    iid=iid,
                    tags=tags,
                    values=(
                        str(row.path.relative_to(in_path)) if row.path.is_relative_to(in_path) else str(row.path),
                        resolution,
                        row.source_kbps if row.source_kbps is not None else "-",
                        row.target_rule_kbps if row.target_rule_kbps is not None else "-",
                        row.effective_target_kbps if row.effective_target_kbps is not None else "-",
                        fmt_mb_from_bytes(row.estimated_output_bytes),
                        fmt_mb_from_bytes(row.estimated_saved_bytes),
                        f"{row.estimated_saved_pct:.1f}%" if row.estimated_saved_pct is not None else "-",
                        tr(lang, "tbl_action_" + row.action),
                        row.reason,
                    ),
                )

            if end >= len(rows):
                self._scan_render_after_id = None
                convert_count = sum(1 for r in rows if r.action == "convert")
                skip_count = len(rows) - convert_count
                total_source = sum((r.source_size_bytes or 0) for r in rows)
                total_est_out = 0
                for r in rows:
                    if r.action == "convert" and r.estimated_output_bytes is not None:
                        total_est_out += r.estimated_output_bytes
                    else:
                        total_est_out += r.source_size_bytes or 0
                total_saved = max(0, total_source - total_est_out)
                total_saved_pct = (total_saved / total_source * 100.0) if total_source > 0 else 0.0
                self.progress_var.set(100.0)
                self.status_var.set(
                    tr(
                        lang,
                        "scan_done_summary",
                        files=len(rows),
                        conv=convert_count,
                        skip=skip_count,
                        mb=fmt_mb_from_bytes(total_saved),
                        pct=total_saved_pct,
                    )
                )
                self._set_scan_ui_busy(False)
                return

            self.progress_var.set(min(99.0, (end / max(1, len(rows))) * 100.0))
            self._scan_render_after_id = self.root.after(1, lambda: tick(end))

        self._scan_render_after_id = self.root.after(1, lambda: tick(start_idx))

    def scan_folder(self) -> None:
        self._save_settings()
        if self.output_beside_source_var.get():
            self._sync_output_with_source_if_enabled()
        input_folder = self.input_folder_var.get().strip()
        output_folder = self.output_folder_var.get().strip()
        L = self._lang()
        err_title = tr(L, "dlg_error")
        if not input_folder:
            messagebox.showerror(err_title, tr(L, "err_input_required"))
            return
        if not output_folder:
            messagebox.showerror(err_title, tr(L, "err_output_required"))
            return
        in_path = Path(input_folder)
        out_path = Path(output_folder)
        if not in_path.exists():
            messagebox.showerror(err_title, tr(L, "err_input_missing"))
            return
        out_path.mkdir(parents=True, exist_ok=True)

        rules = self._get_rule_map()
        if rules is None:
            return

        if self.scan_worker and self.scan_worker.is_alive():
            messagebox.showinfo(tr(L, "dlg_busy"), tr(L, "info_scan_running"))
            return

        self._drain_msg_queue()
        self._scan_generation += 1
        scan_id = self._scan_generation
        self._scan_in_path = in_path
        self._cancel_scan_render()

        self.status_var.set(tr(L, "status_scanning"))
        self.progress_var.set(0)

        files = self._iter_video_files(in_path, self.recursive_var.get())
        self.video_rows = []
        self._path_to_tree_iid.clear()
        self.tree.delete(*self.tree.get_children())

        if not files:
            self.status_var.set(tr(L, "status_no_videos"))
            self.progress_var.set(0.0)
            return

        scan_lang = self._lang()
        self._set_scan_ui_busy(True)
        self.scan_worker = threading.Thread(
            target=self._scan_worker_job,
            args=(scan_id, in_path, files, rules, scan_lang),
            daemon=True,
        )
        self.scan_worker.start()

    def start_conversion(self) -> None:
        self._save_settings()
        L = self._lang()
        if self.output_beside_source_var.get():
            self._sync_output_with_source_if_enabled()
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(tr(L, "dlg_busy"), tr(L, "info_convert_running"))
            return
        if not self.video_rows:
            messagebox.showerror(tr(L, "dlg_error"), tr(L, "err_scan_first"))
            return

        out_path = Path(self.output_folder_var.get().strip())
        out_path.mkdir(parents=True, exist_ok=True)
        self.stop_flag.clear()
        self.progress_var.set(0)
        self.status_var.set(tr(L, "status_convert_start"))
        convert_total = sum(1 for r in self.video_rows if r.action == "convert" and r.effective_target_kbps)
        self._jobs_cur = 0
        self._jobs_tot = convert_total
        self._refresh_jobs_label()

        self.worker = threading.Thread(target=self._worker_convert, daemon=True)
        self.worker.start()

    def stop_conversion(self) -> None:
        self.stop_flag.set()
        self.status_var.set(tr(self._lang(), "status_stop_requested"))

    def _build_ffmpeg_cmd(self, src: Path, dst: Path, target_kbps: int) -> List[str]:
        codec = self.codec_var.get().strip() or "libx264"
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-i",
            str(src),
            "-c:v",
            codec,
            "-b:v",
            f"{target_kbps}k",
            "-maxrate",
            f"{target_kbps}k",
            "-bufsize",
            f"{target_kbps * 2}k",
        ]
        if codec in {"h264_nvenc", "hevc_nvenc"}:
            # NVENC defaults: balanced quality/speed for batch jobs.
            cmd.extend(
                [
                    "-rc:v",
                    "vbr",
                    "-cq:v",
                    "23",
                    "-preset",
                    "p5",
                    "-profile:v",
                    "high" if codec == "h264_nvenc" else "main",
                ]
            )

        if self.audio_mode_var.get() == "aac_128k":
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.extend(["-c:a", "copy"])

        if dst.suffix.lower() in {".mp4", ".m4v", ".mov"}:
            cmd.extend(["-movflags", "+faststart"])
        cmd.append(str(dst))
        return cmd

    @staticmethod
    def _same_folder(a: Path, b: Path) -> bool:
        try:
            return a.resolve() == b.resolve()
        except Exception:
            return str(a).lower() == str(b).lower()

    def _effective_suffix(self, input_root: Path, output_root: Path, source: Path, planned_out: Path) -> str:
        raw = self.suffix_var.get().strip()
        if raw:
            return raw
        if self._same_folder(input_root, output_root):
            # Same-folder safety: avoid accidental in-place overwrite when names would collide.
            # If container/extension changes (e.g. .flv -> .mp4), an empty suffix is OK.
            try:
                if source.name.lower() != planned_out.name.lower():
                    return ""
            except Exception:
                return "_bitrate"
            return "_bitrate"
        return ""

    def _is_valid_output(self, path: Path) -> bool:
        if not path.exists():
            return False
        if path.stat().st_size <= 0:
            return False
        w, h, _ = run_ffprobe(path)
        return bool(w and h)

    def _move_original_to_backup(self, source: Path, input_root: Path, output_root: Path) -> bool:
        backup_root = output_root / "_original_backup"
        rel = source.relative_to(input_root) if source.is_relative_to(input_root) else Path(source.name)
        target = backup_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target.with_name(f"{target.stem}_dup{target.suffix}")
        shutil.move(str(source), str(target))
        return True

    @staticmethod
    def _paths_conflict(a: Path, b: Path) -> bool:
        try:
            return a.resolve() == b.resolve()
        except Exception:
            return str(a).lower() == str(b).lower()

    def _finalize_encoded_output(self, source: Path, work_out: Path, final_out: Path) -> None:
        if self._paths_conflict(work_out, final_out):
            return
        if final_out.exists():
            final_out.unlink()
        shutil.move(str(work_out), str(final_out))

    def _maybe_strip_autobitrate_suffix(self, final_out: Path, lang: str) -> Path:
        if not self.strip_autobitrate_suffix_var.get():
            return final_out
        configured = self.suffix_var.get().strip()
        if configured and configured != "_bitrate":
            return final_out
        stem = final_out.stem
        if not stem.endswith("_bitrate"):
            return final_out
        new_stem = stem[: -len("_bitrate")]
        if not new_stem:
            return final_out
        target = final_out.with_name(f"{new_stem}{final_out.suffix}")
        if target.exists():
            self.msg_queue.put(("status", tr(lang, "status_rename_skip", name=target.name)))
            return final_out
        final_out.rename(target)
        return target

    def _iter_rename_candidates(self, root: Path) -> List[Path]:
        pattern = "**/*" if self.recursive_var.get() else "*"
        files: List[Path] = []
        for p in root.glob(pattern):
            if not p.is_file():
                continue
            if self.rename_only_video_var.get() and p.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            files.append(p)
        files.sort()
        return files

    def _bitrate_rename_pair(self, path: Path) -> Optional[Tuple[Path, Path]]:
        stem = path.stem
        if not stem.endswith("_bitrate"):
            return None
        new_stem = stem[: -len("_bitrate")]
        if not new_stem:
            return None
        target = path.with_name(f"{new_stem}{path.suffix}")
        if self._paths_conflict(path, target):
            return None
        if target.exists():
            return None
        return path, target

    def _collect_bitrate_rename_pairs(self, root: Path) -> Tuple[List[Tuple[Path, Path]], int, int]:
        conflicts = 0
        pairs: List[Tuple[Path, Path]] = []
        candidates = self._iter_rename_candidates(root)
        scanned = len(candidates)
        for p in candidates:
            if not p.stem.endswith("_bitrate"):
                continue
            pair = self._bitrate_rename_pair(p)
            if pair is None:
                conflicts += 1
                continue
            pairs.append(pair)
        return pairs, conflicts, scanned

    def _format_rename_preview(self, pairs: List[Tuple[Path, Path]], conflicts: int, scanned: int, lang: str) -> str:
        lines: List[str] = [
            tr(lang, "preview_scanned", n=scanned),
            tr(lang, "preview_renamable", n=len(pairs)),
            tr(lang, "preview_skipped", n=conflicts),
            "",
        ]
        max_lines = 25
        for old, new in pairs[:max_lines]:
            try:
                rel_old = str(old.relative_to(Path(self.input_folder_var.get().strip())))
            except Exception:
                rel_old = str(old)
            try:
                rel_new = str(new.relative_to(Path(self.input_folder_var.get().strip())))
            except Exception:
                rel_new = str(new)
            lines.append(f"{rel_old}  ->  {rel_new}")
        if len(pairs) > max_lines:
            lines.append(tr(lang, "preview_more", n=len(pairs) - max_lines))
        return "\n".join(lines)

    def _preview_bitrate_renames(self) -> None:
        L = self._lang()
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(tr(L, "dlg_busy"), tr(L, "info_wait_convert"))
            return
        root_txt = self.input_folder_var.get().strip()
        if not root_txt:
            messagebox.showerror(tr(L, "dlg_error"), tr(L, "err_input_set"))
            return
        root = Path(root_txt)
        if not root.exists():
            messagebox.showerror(tr(L, "dlg_error"), tr(L, "err_input_missing"))
            return
        pairs, conflicts, scanned = self._collect_bitrate_rename_pairs(root)
        preview = self._format_rename_preview(pairs, conflicts, scanned, L)
        messagebox.showinfo(tr(L, "dlg_preview_title"), preview)

    def _apply_bitrate_renames(self) -> None:
        L = self._lang()
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(tr(L, "dlg_busy"), tr(L, "info_wait_convert"))
            return
        if self.rename_worker and self.rename_worker.is_alive():
            messagebox.showinfo(tr(L, "dlg_busy"), tr(L, "info_rename_running"))
            return
        root_txt = self.input_folder_var.get().strip()
        if not root_txt:
            messagebox.showerror(tr(L, "dlg_error"), tr(L, "err_input_set"))
            return
        root = Path(root_txt)
        if not root.exists():
            messagebox.showerror(tr(L, "dlg_error"), tr(L, "err_input_missing"))
            return

        pairs, conflicts, scanned = self._collect_bitrate_rename_pairs(root)
        preview = self._format_rename_preview(pairs, conflicts, scanned, L)
        if not pairs:
            messagebox.showinfo(tr(L, "dlg_rename_none"), tr(L, "info_rename_none_body"))
            return
        if not messagebox.askyesno(
            tr(L, "dlg_rename_confirm_title"),
            preview + tr(L, "dlg_rename_confirm_body"),
        ):
            return

        def _run() -> None:
            lang = self._lang()
            ok = 0
            err = 0
            total = len(pairs)
            for idx, (old, new) in enumerate(pairs, start=1):
                try:
                    old.rename(new)
                    ok += 1
                except Exception:
                    try:
                        shutil.move(str(old), str(new))
                        ok += 1
                    except Exception:
                        err += 1
                if idx == 1 or idx % 25 == 0 or idx == total:
                    self.msg_queue.put(("status", tr(lang, "status_rename_progress", cur=idx, total=total)))
            self.msg_queue.put(
                ("status", tr(lang, "status_rename_done", ok=ok, err=err, conflicts=conflicts))
            )

        self.rename_worker = threading.Thread(target=_run, daemon=True)
        self.rename_worker.start()

    def _worker_convert(self) -> None:
        lang = self._lang()
        input_root = Path(self.input_folder_var.get().strip())
        output_root = Path(self.output_folder_var.get().strip())
        post_action = (self.post_success_action_var.get() or "keep").strip()
        jobs = [r for r in self.video_rows if r.action == "convert" and r.effective_target_kbps]
        total = len(jobs)
        if total == 0:
            self.msg_queue.put(("jobs", (0, 0)))
            self.msg_queue.put(("done", tr(lang, "done_no_convert")))
            return

        self.msg_queue.put(("jobs", (0, total)))

        done = 0
        failed = 0
        moved = 0
        deleted = 0
        post_failed = 0
        for row in jobs:
            if self.stop_flag.is_set():
                processed = min(total, done + failed)
                self.msg_queue.put(("jobs", (processed, total)))
                self.msg_queue.put(
                    ("done", tr(lang, "done_aborted", done=done, failed=failed, moved=moved, deleted=deleted))
                )
                return

            rel = row.path.relative_to(input_root) if row.path.is_relative_to(input_root) else Path(row.path.name)
            out_file = output_root / rel
            out_file.parent.mkdir(parents=True, exist_ok=True)
            planned_ext = ".mp4" if self.output_mp4_var.get() else rel.suffix
            planned_out = (out_file.parent / rel.name).with_suffix(planned_ext)
            suffix = self._effective_suffix(input_root, output_root, row.path, planned_out)
            out_file = out_file.parent / f"{rel.stem}{suffix}{planned_ext}"

            work_out = out_file
            if self._paths_conflict(row.path, out_file):
                work_out = out_file.with_name(f"{out_file.stem}.partial{out_file.suffix}")

            cmd = self._build_ffmpeg_cmd(row.path, work_out, row.effective_target_kbps or 1)
            self.msg_queue.put(
                ("status", tr(lang, "status_converting", name=row.path.name, kbps=row.effective_target_kbps or 0))
            )
            completed = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if completed.returncode != 0:
                failed += 1
                err = (completed.stderr or "").strip().splitlines()
                short_err = err[-1] if err else tr(lang, "err_unknown_ffmpeg")
                self.msg_queue.put(("status", tr(lang, "status_err_file", name=row.path.name, detail=short_err)))
                self.msg_queue.put(("row_state", (str(row.path.resolve()), "fail")))
                try:
                    if work_out.exists() and not self._paths_conflict(work_out, out_file):
                        work_out.unlink()
                except Exception:
                    pass
            else:
                if not self._is_valid_output(work_out):
                    failed += 1
                    self.msg_queue.put(("status", tr(lang, "status_verify_fail", name=row.path.name)))
                    self.msg_queue.put(("row_state", (str(row.path.resolve()), "fail")))
                    try:
                        if work_out.exists() and not self._paths_conflict(work_out, out_file):
                            work_out.unlink()
                    except Exception:
                        pass
                else:
                    try:
                        self._finalize_encoded_output(row.path, work_out, out_file)
                        out_file = self._maybe_strip_autobitrate_suffix(out_file, lang)
                        if post_action == "move_to_backup":
                            self._move_original_to_backup(row.path, input_root, output_root)
                            moved += 1
                        elif post_action == "delete_original":
                            if row.path.exists():
                                row.path.unlink()
                                deleted += 1
                        done += 1
                        self.msg_queue.put(("row_state", (str(row.path.resolve()), "done")))
                    except Exception as ex:
                        failed += 1
                        post_failed += 1
                        self.msg_queue.put(("status", tr(lang, "status_post_fail", name=row.path.name, detail=ex)))
                        self.msg_queue.put(("row_state", (str(row.path.resolve()), "fail")))
                        try:
                            if work_out.exists() and not self._paths_conflict(work_out, out_file):
                                work_out.unlink()
                        except Exception:
                            pass

            self.msg_queue.put(("progress", ((done + failed) / total) * 100.0))
            self.msg_queue.put(("jobs", (done + failed, total)))

        self.msg_queue.put(("jobs", (total, total)))
        self.msg_queue.put(
            (
                "done",
                tr(lang, "done_summary", done=done, failed=failed, moved=moved, deleted=deleted, post_failed=post_failed),
            )
        )

    def _poll_queue(self) -> None:
        while True:
            try:
                kind, payload = self.msg_queue.get_nowait()
            except queue.Empty:
                break

            if kind == "status":
                self.status_var.set(str(payload))
            elif kind == "jobs":
                cur, tot = payload
                self._jobs_cur = int(cur)
                self._jobs_tot = int(tot)
                self._refresh_jobs_label()
            elif kind == "row_state":
                path_key, state = payload
                iid = self._path_to_tree_iid.get(path_key)
                if iid and state in {"done", "fail"}:
                    self.tree.item(iid, tags=(state,))
            elif kind == "progress":
                self.progress_var.set(float(payload))
            elif kind == "scan_progress":
                sid, processed, total = payload
                if sid != self._scan_generation:
                    continue
                self.progress_var.set((processed / max(1, total)) * 95.0)
                self.status_var.set(tr(self._lang(), "status_scan_progress", cur=processed, total=total))
            elif kind == "scan_done":
                sid, in_path, rows = payload
                if sid != self._scan_generation:
                    continue
                self.video_rows = rows
                self.status_var.set(tr(self._lang(), "status_building_list", n=len(rows)))
                self.progress_var.set(96.0)
                self._schedule_scan_rows_render(sid, in_path, rows, 0, self._lang())
            elif kind == "scan_error":
                sid, err = payload
                if sid != self._scan_generation:
                    continue
                self._cancel_scan_render()
                self.status_var.set(tr(self._lang(), "status_scan_error", detail=err))
                self.progress_var.set(0.0)
                self._set_scan_ui_busy(False)
            elif kind == "done":
                self.status_var.set(str(payload))
                self.progress_var.set(100.0)
                if self.stop_flag.is_set():
                    self.stop_flag.clear()

        self.root.after(150, self._poll_queue)


def main() -> None:
    if not is_tool_available("ffprobe") or not is_tool_available("ffmpeg"):
        import locale as _locale

        try:
            loc = (_locale.getdefaultlocale()[0] or "").lower()
        except Exception:
            loc = ""
        boot_lang = LANG_DE if loc.startswith("de") else LANG_EN
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            tr(boot_lang, "dlg_ffmpeg_missing_title"),
            tr(boot_lang, "dlg_ffmpeg_missing_body"),
        )
        root.destroy()
        return

    root = tk.Tk()
    app = BitrateChangerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
