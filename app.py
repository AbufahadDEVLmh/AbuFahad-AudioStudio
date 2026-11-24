"""Labobo Virtual Audio Card - Classic EAX Console UI (Casual Arabic + Abu fahad Edition)."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
import sys
import time
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional

from audio_engine import AudioDeviceInfo, AudioEngine
from dsp_engine import AudioDSP, DEFAULT_PRESET_NAME, DSPParams, PRESETS
from ui_widgets import EAXAmountSlider, draw_vgrad
from voicemeeter_bridge import VoicemeeterBridge


if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
DEFAULT_PRESET = DEFAULT_PRESET_NAME


class LaboboApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("كرت الصوت — Abu fahad ©")
        self.geometry("710x485")
        self.minsize(650, 455)
        self.configure(bg="#0084ff")

        self.dsp = AudioDSP(sample_rate=48000)
        self.engine = AudioEngine(self.dsp)
        self.vm_bridge = VoicemeeterBridge()

        self.inputs: List[AudioDeviceInfo] = []
        self.outputs: List[AudioDeviceInfo] = []
        self.input_map: Dict[str, int] = {}
        self.output_map: Dict[str, int] = {}

        self._active_tab = "Effects"
        self._active_preset_name = DEFAULT_PRESET
        self._base_preset_params = DSPParams(**asdict(PRESETS[DEFAULT_PRESET]))
        self._amount_pct = 100.0
        self._start_ts: Optional[float] = None
        self._sliders: Dict[str, ttk.Scale] = {}
        self._slider_labels: Dict[str, tk.Label] = {}
        self._slider_formats: Dict[str, tuple[str, float]] = {}
        self._tab_buttons: Dict[str, tk.Button] = {}
        self._tab_frames: Dict[str, tk.Frame] = {}

        self.engine.set_status_callback(self._on_engine_status)

        self._build_ui()
        self._refresh_devices(initial=True)
        self._load_settings()
        self._sync_ui_from_params()
        self._tick_loop()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        outer = tk.Frame(self, bg="#0084ff", padx=4, pady=4)
        outer.pack(fill="both", expand=True)

        # 1) Top Silver Metallic Header Bar
        self.header_canvas = tk.Canvas(outer, height=44, highlightthickness=0, bd=0)
        self.header_canvas.pack(fill="x")
        self.header_canvas.bind("<Configure>", self._draw_header)

        self.sound_profile_var = tk.StringVar(value="كرت الصوت — Abu fahad")
        self.device_combo = ttk.Combobox(
            self.header_canvas,
            textvariable=self.sound_profile_var,
            values=["كرت الصوت — Abu fahad", "فويس ميتر B1 + AUX", "إعدادات المايك"],
            state="readonly",
            width=24,
            font=("Tahoma", 9),
        )
        self.device_combo.bind("<<ComboboxSelected>>", self._on_header_combo)

        self.help_btn = tk.Button(
            self.header_canvas,
            text="؟",
            font=("Tahoma", 9, "bold"),
            bg="#e6e8ec",
            fg="#1e293b",
            relief="raised",
            bd=1,
            width=3,
            cursor="hand2",
            command=lambda: self._switch_tab("CMSS 3D"),
        )

        # 2) Silver Tab Strip
        tab_strip = tk.Frame(outer, bg="#dfe3ea", height=30)
        tab_strip.pack(fill="x")
        tab_strip.pack_propagate(False)

        tk.Button(
            tab_strip, text="◀", font=("Tahoma", 7), bg="#e6e9ef", relief="raised", bd=1, width=3,
            command=lambda: self._cycle_tab(-1)
        ).pack(side="left", fill="y", padx=(2, 1), pady=2)

        tabs_info = [
            ("Effects", "المؤثرات والصدى"),
            ("Karaoke", "التضخيم والبيس"),
            ("CMSS 3D", "المايك وفويس ميتر"),
            ("Clean-up", "إعدادات الصدى"),
        ]
        for key, label in tabs_info:
            btn = tk.Button(
                tab_strip,
                text=label,
                font=("Tahoma", 9, "bold" if key == "Effects" else "normal"),
                bg="#ffffff" if key == "Effects" else "#e6e9ef",
                fg="#111111",
                activebackground="#ffffff",
                relief="flat" if key == "Effects" else "raised",
                bd=1,
                padx=12,
                cursor="hand2",
                command=lambda k=key: self._switch_tab(k),
            )
            btn.pack(side="left", fill="y", padx=1, pady=(3, 0))
            self._tab_buttons[key] = btn

        tk.Button(
            tab_strip, text="▶", font=("Tahoma", 7), bg="#e6e9ef", relief="raised", bd=1, width=3,
            command=lambda: self._cycle_tab(1)
        ).pack(side="right", fill="y", padx=(1, 2), pady=2)

        # 3) Main White Content Panel
        self.content_wrap = tk.Frame(outer, bg="#ffffff", bd=1, relief="solid")
        self.content_wrap.pack(fill="both", expand=True)

        self._build_effects_tab()
        self._build_karaoke_tab()
        self._build_routing_tab()
        self._build_cleanup_tab()
        self._switch_tab("Effects")

        # 4) Brushed Silver Transport / Recorder Deck
        self.transport_canvas = tk.Canvas(outer, height=40, highlightthickness=0, bd=0)
        self.transport_canvas.pack(fill="x")
        self.transport_canvas.bind("<Configure>", self._draw_transport)
        self._build_transport_controls()

        # 5) Deep Royal-Blue Glossy Bottom Footer (Abu fahad ©)
        self.footer_canvas = tk.Canvas(outer, height=44, highlightthickness=0, bd=0)
        self.footer_canvas.pack(fill="x")
        self.footer_canvas.bind("<Configure>", self._draw_footer)
        self._build_footer_controls()

    def _draw_header(self, event=None) -> None:
        c = self.header_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        c.delete("all")
        draw_vgrad(c, 0, 0, w, h, "#ffffff", "#c4c9d4")
        c.create_line(0, h - 1, w, h - 1, fill="#8a919e")

        # Left Abu fahad EAX emblem
        c.create_rectangle(10, 6, 98, 26, fill="#0b1220", outline="#475569")
        c.create_text(54, 16, text="Abu fahad", fill="#ffffff", font=("Tahoma", 9, "bold"))
        c.create_text(54, 34, text="SOUND CARD", fill="#0078d7", font=("Tahoma", 7, "bold italic"))
        c.create_text(138, 17, text="كرت الصوت", fill="#334155", font=("Tahoma", 10, "bold"))

        c.create_window(w * 0.58, h / 2, window=self.device_combo)
        c.create_window(w - 28, h / 2, window=self.help_btn)

    def _build_effects_tab(self) -> None:
        f = tk.Frame(self.content_wrap, bg="#ffffff", padx=14, pady=8)
        self._tab_frames["Effects"] = f

        tk.Label(
            f,
            text="تضخيم وصدى مباشر على المايك — Abu fahad ©",
            bg="#ffffff",
            fg="#1e1e1e",
            font=("Tahoma", 9, "bold"),
            justify="right",
            anchor="e",
        ).pack(fill="x", pady=(0, 6))

        self.fx_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            f,
            text="شغّل المؤثرات والصدى",
            variable=self.fx_var,
            command=self._on_fx_toggle,
            bg="#ffffff",
            activebackground="#ffffff",
            fg="#111111",
            font=("Tahoma", 9, "bold"),
            cursor="hand2",
        ).pack(anchor="e", pady=(0, 6))

        box = tk.Frame(f, bg="#f2f2f2", bd=1, relief="groove", padx=12, pady=8)
        box.pack(fill="both", expand=True)
        box.grid_columnconfigure(0, weight=1)
        box.grid_columnconfigure(1, weight=2)
        box.grid_columnconfigure(2, weight=2)
        box.grid_rowconfigure(2, weight=1)

        # Column 0: Live status & levels
        tk.Label(box, text="الوضع الحالي", bg="#f2f2f2", fg="#222222", font=("Tahoma", 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=(4, 10)
        )
        env_card = tk.Frame(box, bg="#e9ecf2", bd=1, relief="sunken", padx=8, pady=8)
        env_card.grid(row=1, column=0, rowspan=2, sticky="nsew", padx=(4, 14), pady=(6, 4))

        self.env_status_lbl = tk.Label(
            env_card,
            text="● واقف حالياً\nاضغط ▶ عشان يشتغل",
            bg="#e9ecf2",
            fg="#475569",
            font=("Tahoma", 8, "bold"),
            justify="right",
            anchor="e",
        )
        self.env_status_lbl.pack(fill="x", pady=(0, 6))

        tk.Label(env_card, text="صوت المايك:", bg="#e9ecf2", fg="#333333", font=("Tahoma", 8)).pack(anchor="e")
        self.mic_bar = ttk.Progressbar(env_card, length=110, mode="determinate", maximum=100)
        self.mic_bar.pack(fill="x", pady=(1, 5))

        tk.Label(env_card, text="الخرج ← B1:", bg="#e9ecf2", fg="#333333", font=("Tahoma", 8)).pack(anchor="e")
        self.out_bar = ttk.Progressbar(env_card, length=110, mode="determinate", maximum=100)
        self.out_bar.pack(fill="x", pady=(1, 5))

        self.route_badge = tk.Label(
            env_card,
            text="المايك: B1\nالسماعة: AUX",
            bg="#e9ecf2",
            fg="#0054e3",
            font=("Tahoma", 7, "bold"),
            justify="right",
        )
        self.route_badge.pack(anchor="e", pady=(4, 0))

        # Column 1: Active Preset Listbox
        tk.Label(box, text="الوزنية المختارة", bg="#f2f2f2", fg="#222222", font=("Tahoma", 9, "bold")).grid(
            row=0, column=1, sticky="e"
        )
        self.active_preset_lbl = tk.Label(
            box, text=DEFAULT_PRESET, bg="#f2f2f2", fg="#000000", font=("Tahoma", 10, "bold")
        )
        self.active_preset_lbl.grid(row=1, column=1, sticky="e", pady=(1, 4))

        list_wrap = tk.Frame(box, bg="#ffffff", bd=1, relief="sunken")
        list_wrap.grid(row=2, column=1, sticky="nsew", padx=(0, 14), pady=(0, 4))

        scroll = tk.Scrollbar(list_wrap, orient="vertical")
        self.preset_listbox = tk.Listbox(
            list_wrap,
            yscrollcommand=scroll.set,
            bg="#ffffff",
            fg="#111111",
            selectbackground="#0078d7",
            selectforeground="#ffffff",
            activestyle="none",
            font=("Tahoma", 9),
            justify="right",
            bd=0,
            highlightthickness=0,
            exportselection=False,
        )
        scroll.config(command=self.preset_listbox.yview)
        scroll.pack(side="left", fill="y")
        self.preset_listbox.pack(side="right", fill="both", expand=True)

        for p_name in PRESETS:
            self.preset_listbox.insert("end", p_name)
        self.preset_listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        # Column 2: Effects Amount Slider
        amt_top = tk.Frame(box, bg="#f2f2f2")
        amt_top.grid(row=0, column=2, sticky="w", pady=(0, 2))
        tk.Label(amt_top, text="قوة الصدى والتأثير : ", bg="#f2f2f2", fg="#222222", font=("Tahoma", 9, "bold")).pack(
            side="left"
        )
        self.amount_lbl = tk.Label(amt_top, text="100", bg="#f2f2f2", fg="#0054e3", font=("Tahoma", 9, "bold"))
        self.amount_lbl.pack(side="left")

        self.amount_slider = EAXAmountSlider(
            box, width=195, height=32, bg_color="#f2f2f2", initial=100.0, command=self._on_amount_change
        )
        self.amount_slider.grid(row=1, column=2, sticky="nw", pady=(0, 6))

        quick_box = tk.Frame(box, bg="#f2f2f2")
        quick_box.grid(row=2, column=2, sticky="nsew", pady=(8, 0))
        self.mon_var_chk = tk.BooleanVar(value=False)
        tk.Checkbutton(
            quick_box,
            text="اسمع صوتي بالسماعة (AUX)",
            variable=self.mon_var_chk,
            command=self._on_monitor_toggle,
            bg="#f2f2f2",
            activebackground="#f2f2f2",
            font=("Tahoma", 8, "bold"),
            fg="#1e293b",
            cursor="hand2",
        ).pack(anchor="w", pady=(2, 4))

        tk.Button(
            quick_box,
            text="اضبط فويس ميتر (B1 + AUX)",
            font=("Tahoma", 8, "bold"),
            bg="#e4e7ec",
            fg="#0044aa",
            relief="raised",
            bd=1,
            cursor="hand2",
            command=self._activate_voicemeeter,
        ).pack(anchor="w", pady=2)

    def _build_karaoke_tab(self) -> None:
        f = tk.Frame(self.content_wrap, bg="#ffffff", padx=16, pady=10)
        self._tab_frames["Karaoke"] = f
        tk.Label(
            f,
            text="تضخيم المايك والبيس — وزنيتك الخاصة (Abu fahad ©)",
            bg="#ffffff",
            fg="#0054e3",
            font=("Tahoma", 9, "bold"),
        ).pack(anchor="e", pady=(0, 8))

        grid = tk.Frame(f, bg="#f2f2f2", bd=1, relief="groove", padx=12, pady=10)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(1, weight=1)

        specs = [
            ("preamp_db", "قوة المايك الأساسية (Preamp)", 0.0, 24.0, "{:+.1f} dB", 1.0),
            ("bass_boost_db", "تضخيم البيس العميق (Bass)", 0.0, 20.0, "{:+.1f} dB", 1.0),
            ("body_boost_db", "ثقل وضخامة الصوت (520Hz)", 0.0, 14.0, "{:+.1f} dB", 1.0),
            ("sub_bass", "بيس تحتي إضافي (Sub)", 0.0, 1.5, "{:.0%}", 100.0),
            ("drive", "خشونة وقوة الدفع (Drive)", 1.0, 8.0, "{:.1f}x", 1.0),
            ("presence_db", "وضوح الحروف والكلام", -6.0, 10.0, "{:+.1f} dB", 1.0),
            ("output_gain_db", "الصوت النهائي (Master)", -12.0, 18.0, "{:+.1f} dB", 1.0),
        ]
        for r, (k, lbl, mn, mx, fmt, mult) in enumerate(specs):
            self._add_classic_slider(grid, r, k, lbl, mn, mx, fmt, mult)

    def _build_routing_tab(self) -> None:
        f = tk.Frame(self.content_wrap, bg="#ffffff", padx=16, pady=10)
        self._tab_frames["CMSS 3D"] = f
        tk.Label(
            f,
            text="توجيه المايك والسماعة مع فويس ميتر (B1 + AUX) — Abu fahad ©",
            bg="#ffffff",
            fg="#0054e3",
            font=("Tahoma", 9, "bold"),
        ).pack(anchor="e", pady=(0, 8))

        box = tk.Frame(f, bg="#f2f2f2", bd=1, relief="groove", padx=14, pady=12)
        box.pack(fill="both", expand=True)
        box.grid_columnconfigure(1, weight=1)

        self.in_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.mon_var = tk.StringVar()

        tk.Label(box, text="المايك حقك (المصدر):", bg="#f2f2f2", font=("Tahoma", 9, "bold")).grid(
            row=0, column=0, sticky="w", pady=6, padx=(0, 10)
        )
        self.in_combo = ttk.Combobox(box, textvariable=self.in_var, state="readonly", font=("Tahoma", 9))
        self.in_combo.grid(row=0, column=1, sticky="ew", pady=6)

        tk.Label(box, text="المخرج ← (يروح لـ B1):", bg="#f2f2f2", font=("Tahoma", 9, "bold")).grid(
            row=1, column=0, sticky="w", pady=6, padx=(0, 10)
        )
        self.out_combo = ttk.Combobox(box, textvariable=self.out_var, state="readonly", font=("Tahoma", 9))
        self.out_combo.grid(row=1, column=1, sticky="ew", pady=6)

        tk.Label(box, text="سماعتك / المراقبة (AUX):", bg="#f2f2f2", font=("Tahoma", 9, "bold")).grid(
            row=2, column=0, sticky="w", pady=6, padx=(0, 10)
        )
        self.mon_combo = ttk.Combobox(box, textvariable=self.mon_var, state="readonly", font=("Tahoma", 9))
        self.mon_combo.grid(row=2, column=1, sticky="ew", pady=6)

        tk.Label(box, text="علو صوتك بالسماعة:", bg="#f2f2f2", font=("Tahoma", 9)).grid(
            row=3, column=0, sticky="w", pady=6, padx=(0, 10)
        )
        self.mon_vol_scale = ttk.Scale(
            box, from_=0.0, to=1.2, orient="horizontal", command=self._on_mon_vol_change
        )
        self.mon_vol_scale.set(0.8)
        self.mon_vol_scale.grid(row=3, column=1, sticky="ew", pady=6)

        btn_row = tk.Frame(box, bg="#f2f2f2")
        btn_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        tk.Button(
            btn_row,
            text="شغّل واضبط فويس ميتر (B1 + AUX)",
            font=("Tahoma", 9, "bold"),
            bg="#0078d7",
            fg="#ffffff",
            relief="raised",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._activate_voicemeeter,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_row,
            text="حدّث الأجهزة",
            font=("Tahoma", 9),
            bg="#e4e7ec",
            relief="raised",
            padx=10,
            pady=4,
            cursor="hand2",
            command=lambda: self._refresh_devices(initial=False),
        ).pack(side="left")

    def _build_cleanup_tab(self) -> None:
        f = tk.Frame(self.content_wrap, bg="#ffffff", padx=16, pady=10)
        self._tab_frames["Clean-up"] = f
        tk.Label(
            f,
            text="تفاصيل الصدى وعازل التشويش — اضبط ذيل الصدى على كيفك",
            bg="#ffffff",
            fg="#0054e3",
            font=("Tahoma", 9, "bold"),
        ).pack(anchor="e", pady=(0, 8))

        grid = tk.Frame(f, bg="#f2f2f2", bd=1, relief="groove", padx=12, pady=10)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(1, weight=1)

        specs = [
            ("echo_level", "قوة صوت الصدى", 0.0, 2.0, "{:.0%}", 100.0),
            ("echo_feedback", "تكرار الصدى", 0.0, 0.90, "{:.0%}", 100.0),
            ("echo_delay_ms", "مسافة الصدى", 60.0, 800.0, "{:.0f} ms", 1.0),
            ("reverb_level", "انتشار الصدى", 0.0, 1.5, "{:.0%}", 100.0),
            ("reverb_decay", "طول ذيل الصدى", 0.20, 0.92, "{:.0%}", 100.0),
            ("gate_db", "مانع التشويش (-75 = طافي)", -75.0, -20.0, "{:.0f} dB", 1.0),
        ]
        for r, (k, lbl, mn, mx, fmt, mult) in enumerate(specs):
            self._add_classic_slider(grid, r, k, lbl, mn, mx, fmt, mult)

    def _add_classic_slider(
        self, parent: tk.Frame, row: int, key: str, label: str, mn: float, mx: float, fmt: str, mult: float
    ) -> None:
        tk.Label(parent, text=label, bg="#f2f2f2", fg="#1e1e1e", font=("Tahoma", 8, "bold")).grid(
            row=row, column=0, sticky="w", padx=(0, 10), pady=4
        )
        sc = ttk.Scale(
            parent,
            from_=mn,
            to=mx,
            orient="horizontal",
            command=lambda val, k=key, f=fmt, m=mult: self._on_slider_change(k, float(val), f, m),
        )
        sc.grid(row=row, column=1, sticky="ew", pady=4)
        val_lbl = tk.Label(parent, text="", bg="#f2f2f2", fg="#0054e3", font=("Consolas", 9, "bold"), width=9)
        val_lbl.grid(row=row, column=2, sticky="e", padx=(8, 0), pady=4)

        self._sliders[key] = sc
        self._slider_labels[key] = val_lbl
        self._slider_formats[key] = (fmt, mult)

    def _build_transport_controls(self) -> None:
        c = self.transport_canvas
        self._tr_btns = []

        btn_specs = [
            ("📂", lambda: self._switch_tab("CMSS 3D")),
            ("🔊", self._toggle_monitor_quick),
            ("»", lambda: self._cycle_tab(1)),
        ]
        for txt, cmd in btn_specs:
            b = tk.Button(
                c, text=txt, font=("Segoe UI", 9, "bold"), bg="#e5e8ee", fg="#1e293b",
                relief="raised", bd=1, width=3, cursor="hand2", command=cmd
            )
            self._tr_btns.append(b)

        self.lcd_label = tk.Label(
            c,
            text="00:00:00",
            bg="#ffffff",
            fg="#111111",
            font=("Consolas", 11, "bold"),
            bd=1,
            relief="sunken",
            width=10,
        )

        self.rec_btn = tk.Button(
            c, text="● شغّل", font=("Tahoma", 8, "bold"), bg="#e5e8ee", fg="#dc2626",
            relief="raised", bd=1, width=7, cursor="hand2", command=self._toggle_power
        )
        self.play_btn = tk.Button(
            c, text="▶", font=("Segoe UI", 9, "bold"), bg="#e5e8ee", fg="#0078d7",
            relief="raised", bd=1, width=4, cursor="hand2", command=self._start_card
        )
        self.stop_btn = tk.Button(
            c, text="■", font=("Segoe UI", 9, "bold"), bg="#e5e8ee", fg="#334155",
            relief="raised", bd=1, width=3, cursor="hand2", command=self._stop_card
        )
        self.clear_echo_btn = tk.Button(
            c, text="↺", font=("Segoe UI", 9, "bold"), bg="#e5e8ee", fg="#0078d7",
            relief="raised", bd=1, width=3, cursor="hand2", command=self.dsp.reset_buffers
        )

    def _draw_transport(self, event=None) -> None:
        c = self.transport_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        c.delete("all")
        draw_vgrad(c, 0, 0, w, h, "#f4f6f9", "#c7ccd6")
        c.create_line(0, 0, w, 0, fill="#ffffff")
        c.create_line(0, h - 1, w, h - 1, fill="#8a919e")

        c.create_rectangle(14, 5, w - 14, h - 5, fill="#dfe3ea", outline="#9ba2ae")
        c.create_window(34, h / 2, window=self._tr_btns[0])
        c.create_window(66, h / 2, window=self._tr_btns[1])
        c.create_window(102, h / 2, window=self._tr_btns[2])
        c.create_window(185, h / 2, window=self.lcd_label)
        c.create_window(272, h / 2, window=self.rec_btn)
        c.create_window(334, h / 2, window=self.play_btn)
        c.create_window(378, h / 2, window=self.stop_btn)
        c.create_window(422, h / 2, window=self.clear_echo_btn)

        c.create_text(
            w - 22,
            h / 2,
            anchor="e",
            text="واقف" if not self.engine.is_running() else "شغّال لايف ← B1",
            fill="#059669" if self.engine.is_running() else "#475569",
            font=("Tahoma", 8, "bold"),
        )

    def _build_footer_controls(self) -> None:
        c = self.footer_canvas
        self.default_btn = tk.Button(
            c,
            text="رجّعه افتراضي",
            font=("Tahoma", 8, "bold"),
            bg="#f3f4f6",
            fg="#111111",
            relief="raised",
            bd=1,
            width=12,
            cursor="hand2",
            command=self._reset_default_haunted,
        )
        self.ft_icons = [
            tk.Button(
                c, text="🎚", font=("Segoe UI", 9), bg="#dce3f0", relief="raised", bd=1, width=3,
                cursor="hand2", command=lambda: self._switch_tab("Karaoke")
            ),
            tk.Button(
                c, text="🔊", font=("Segoe UI", 9), bg="#dce3f0", relief="raised", bd=1, width=3,
                cursor="hand2", command=self._toggle_monitor_quick
            ),
            tk.Button(
                c, text="🔌", font=("Segoe UI", 9), bg="#dce3f0", relief="raised", bd=1, width=3,
                cursor="hand2", command=self._activate_voicemeeter
            ),
            tk.Button(
                c, text="📊", font=("Segoe UI", 9), bg="#dce3f0", relief="raised", bd=1, width=3,
                cursor="hand2", command=lambda: self._switch_tab("Clean-up")
            ),
        ]

    def _draw_footer(self, event=None) -> None:
        c = self.footer_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        c.delete("all")
        draw_vgrad(c, 0, 0, w, h, "#0066ee", "#00237a")
        c.create_line(0, 0, w, 0, fill="#60a5fa")

        c.create_window(64, h / 2, window=self.default_btn)
        x = 138
        for b in self.ft_icons:
            c.create_window(x, h / 2, window=b)
            x += 34

        c.create_text(
            w - 18,
            h / 2,
            anchor="e",
            text="Abu fahad ©  •  2026",
            fill="#67e8f9",
            font=("Trebuchet MS", 13, "bold"),
        )

    # ------------------------------------------------------------------ Logic
    def _switch_tab(self, key: str) -> None:
        self._active_tab = key
        for k, fr in self._tab_frames.items():
            if k == key:
                fr.pack(fill="both", expand=True)
            else:
                fr.pack_forget()
        for k, btn in self._tab_buttons.items():
            if k == key:
                btn.configure(bg="#ffffff", relief="flat", font=("Tahoma", 9, "bold"))
            else:
                btn.configure(bg="#e6e9ef", relief="raised", font=("Tahoma", 9, "normal"))

    def _cycle_tab(self, direction: int) -> None:
        keys = ["Effects", "Karaoke", "CMSS 3D", "Clean-up"]
        idx = (keys.index(self._active_tab) + direction) % len(keys)
        self._switch_tab(keys[idx])

    def _on_header_combo(self, _event=None) -> None:
        choice = self.sound_profile_var.get()
        if "فويس ميتر" in choice or "المايك" in choice:
            self._switch_tab("CMSS 3D")

    def _on_listbox_select(self, _event=None) -> None:
        sel = self.preset_listbox.curselection()
        if not sel:
            return
        name = self.preset_listbox.get(sel[0])
        self._apply_preset(name)

    def _apply_preset(self, preset_name: str) -> None:
        if preset_name not in PRESETS:
            return
        self._active_preset_name = preset_name
        self._base_preset_params = DSPParams(**asdict(PRESETS[preset_name]))
        self.active_preset_lbl.configure(text=preset_name)
        self._apply_effects_amount(self._amount_pct)

    def _on_amount_change(self, val: float) -> None:
        self._amount_pct = float(val)
        self.amount_lbl.configure(text=f"{int(round(self._amount_pct))}")
        self._apply_effects_amount(self._amount_pct)

    def _apply_effects_amount(self, pct: float) -> None:
        scale = max(0.0, min(1.0, pct / 100.0))
        b = self._base_preset_params
        self.dsp.update_params(
            enabled=bool(self.fx_var.get()),
            preamp_db=b.preamp_db * (0.35 + 0.65 * scale),
            bass_boost_db=b.bass_boost_db * scale,
            body_boost_db=b.body_boost_db * scale,
            presence_db=b.presence_db * scale,
            sub_bass=b.sub_bass * scale,
            drive=1.0 + (b.drive - 1.0) * scale,
            gate_db=b.gate_db,
            echo_delay_ms=b.echo_delay_ms,
            echo_feedback=b.echo_feedback * scale,
            echo_level=b.echo_level * scale,
            reverb_level=b.reverb_level * scale,
            reverb_decay=0.20 + (b.reverb_decay - 0.20) * scale,
            output_gain_db=b.output_gain_db * scale,
        )
        self._sync_ui_from_params(sync_listbox=False)

    def _reset_default_haunted(self) -> None:
        self.dsp.reset_buffers()
        self.fx_var.set(True)
        self._amount_pct = 100.0
        self.amount_slider.set(100.0)
        self.amount_lbl.configure(text="100")
        self._apply_preset(DEFAULT_PRESET)
        self._select_listbox_preset(DEFAULT_PRESET)

    def _select_listbox_preset(self, name: str) -> None:
        items = self.preset_listbox.get(0, "end")
        if name in items:
            idx = items.index(name)
            self.preset_listbox.selection_clear(0, "end")
            self.preset_listbox.selection_set(idx)
            self.preset_listbox.see(idx)

    def _on_slider_change(self, key: str, val: float, fmt: str, mult: float) -> None:
        self.dsp.update_params(**{key: val})
        if key in self._slider_labels:
            self._slider_labels[key].configure(text=fmt.format(val * mult))

    def _sync_ui_from_params(self, sync_listbox: bool = True) -> None:
        p = asdict(self.dsp.params)
        self.fx_var.set(bool(p["enabled"]))
        for k, sc in self._sliders.items():
            if k in p:
                val = float(p[k])
                sc.set(val)
                fmt, mult = self._slider_formats[k]
                self._slider_labels[k].configure(text=fmt.format(val * mult))
        if sync_listbox:
            self._select_listbox_preset(self._active_preset_name)
            self.active_preset_lbl.configure(text=self._active_preset_name)

    def _on_fx_toggle(self) -> None:
        self.dsp.update_params(enabled=bool(self.fx_var.get()))

    def _toggle_monitor_quick(self) -> None:
        self.mon_var_chk.set(not bool(self.mon_var_chk.get()))
        self._on_monitor_toggle()

    def _on_monitor_toggle(self) -> None:
        mon_idx = self.output_map.get(self.mon_var.get())
        self.engine.set_monitor(bool(self.mon_var_chk.get()), mon_idx)

    def _on_mon_vol_change(self, val: str) -> None:
        self.engine.set_monitor_volume(float(val))

    def _refresh_devices(self, initial: bool = False) -> None:
        self.inputs, self.outputs = AudioEngine.list_devices()
        self.input_map = {d.label: d.index for d in self.inputs}
        self.output_map = {d.label: d.index for d in self.outputs}

        in_labels = [d.label for d in self.inputs] or ["ما فيه مايك"]
        out_labels = [d.label for d in self.outputs] or ["ما فيه مخرج"]

        self.in_combo.configure(values=in_labels)
        self.out_combo.configure(values=out_labels)
        self.mon_combo.configure(values=out_labels)

        if initial or self.in_var.get() not in self.input_map or self.out_var.get() not in self.output_map:
            best_in, best_virt, best_mon = AudioEngine.pick_default_devices(self.inputs, self.outputs)
            if best_in:
                self.in_var.set(best_in.label)
            if best_virt:
                self.out_var.set(best_virt.label)
            if best_mon:
                self.mon_var.set(best_mon.label)

    def _toggle_power(self) -> None:
        if self.engine.is_running():
            self._stop_card()
        else:
            self._start_card()

    def _start_card(self) -> None:
        if self.engine.is_running():
            return
        in_idx = self.input_map.get(self.in_var.get())
        out_idx = self.output_map.get(self.out_var.get())
        mon_idx = self.output_map.get(self.mon_var.get())

        if in_idx is None or out_idx is None:
            self._on_engine_status("اختر المايك والمخرج أول", is_error=True)
            return

        if "voicemeeter" in self.out_var.get().lower() or self.vm_bridge.is_running():
            self.vm_bridge.launch_and_route(self.out_var.get(), self.mon_var.get(), self.in_var.get())

        ok = self.engine.start(
            input_idx=in_idx,
            output_idx=out_idx,
            monitor_enabled=bool(self.mon_var_chk.get()),
            monitor_idx=mon_idx,
        )
        if ok:
            self._start_ts = time.time()
            self.rec_btn.configure(bg="#fee2e2", fg="#b91c1c")
            self.play_btn.configure(bg="#dbeafe", fg="#0054e3")
            self._draw_transport()
            self._save_settings()
        else:
            self.vm_bridge.restore_mic_routing()

    def _stop_card(self) -> None:
        self.engine.stop()
        self.vm_bridge.restore_mic_routing()
        self._start_ts = None
        self.lcd_label.configure(text="00:00:00")
        self.rec_btn.configure(bg="#e5e8ee", fg="#dc2626")
        self.play_btn.configure(bg="#e5e8ee", fg="#0078d7")
        self._draw_transport()

    def _activate_voicemeeter(self) -> None:
        ok, _msg = self.vm_bridge.launch_and_route(self.out_var.get(), self.mon_var.get(), self.in_var.get())
        self.env_status_lbl.configure(
            text="● فويس ميتر مضبوط\nB1 ← مايكك\nAUX ← سماعتك" if ok else "✖ فويس ميتر ما استجاب",
            fg="#059669" if ok else "#dc2626",
        )

    def _on_engine_status(self, msg: str, is_error: bool) -> None:
        def _apply() -> None:
            if is_error:
                self.env_status_lbl.configure(text=f"✖ مشكلة:\n{msg[:36]}", fg="#dc2626")
            elif self.engine.is_running():
                self.env_status_lbl.configure(text="● شغّال لايف\nالصوت طالع على B1", fg="#059669")
            else:
                self.env_status_lbl.configure(text="● واقف حالياً\nاضغط ▶ عشان يشتغل", fg="#475569")

        self.after(0, _apply)

    def _tick_loop(self) -> None:
        in_pct = max(0.0, min(100.0, ((self.dsp.input_level_db + 60.0) / 60.0) * 100.0))
        out_pct = max(0.0, min(100.0, ((self.dsp.output_level_db + 60.0) / 60.0) * 100.0))
        self.mic_bar["value"] = in_pct
        self.out_bar["value"] = out_pct

        if self.engine.is_running() and self._start_ts is not None:
            elapsed = time.time() - self._start_ts
            mins = int(elapsed // 60) % 100
            secs = int(elapsed) % 60
            cs = int((elapsed * 100) % 100)
            self.lcd_label.configure(text=f"{mins:02d}:{secs:02d}:{cs:02d}")

        self.after(45, self._tick_loop)

    def _save_settings(self) -> None:
        data = {
            "dsp": asdict(self.dsp.params),
            "preset_name": self._active_preset_name,
            "effects_amount": self._amount_pct,
            "input_device": self.in_var.get(),
            "output_device": self.out_var.get(),
            "monitor_device": self.mon_var.get(),
            "monitor_enabled": bool(self.mon_var_chk.get()),
            "monitor_volume": float(self.mon_vol_scale.get()),
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _load_settings(self) -> None:
        if not os.path.isfile(SETTINGS_FILE):
            return
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("preset_name"), str) and data["preset_name"] in PRESETS:
                self._active_preset_name = data["preset_name"]
                self._base_preset_params = DSPParams(**asdict(PRESETS[self._active_preset_name]))
            if "effects_amount" in data:
                self._amount_pct = float(data["effects_amount"])
                self.amount_slider.set(self._amount_pct)
                self.amount_lbl.configure(text=f"{int(round(self._amount_pct))}")
            if isinstance(data.get("dsp"), dict):
                self.dsp.update_params(**data["dsp"])
            if data.get("input_device") in self.input_map:
                self.in_var.set(data["input_device"])
            if data.get("output_device") in self.output_map:
                self.out_var.set(data["output_device"])
            if data.get("monitor_device") in self.output_map:
                self.mon_var.set(data["monitor_device"])
            self.mon_var_chk.set(bool(data.get("monitor_enabled", False)))
            vol = float(data.get("monitor_volume", 0.8))
            self.mon_vol_scale.set(vol)
            self.engine.set_monitor_volume(vol)
        except Exception:
            pass

    def _on_close(self) -> None:
        self._save_settings()
        self.engine.stop()
        self.vm_bridge.close()
        self.destroy()


if __name__ == "__main__":
    app = LaboboApp()
    app.mainloop()
