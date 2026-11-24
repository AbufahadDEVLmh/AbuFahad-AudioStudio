"""Real-time audio I/O manager using PortAudio (sounddevice) with WASAPI/DirectSound support."""

from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
from typing import Callable, List, Optional, Tuple

import numpy as np
import sounddevice as sd

from dsp_engine import AudioDSP


@dataclass
class AudioDeviceInfo:
    index: int
    name: str
    hostapi_name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: int

    @property
    def label(self) -> str:
        short_api = (
            self.hostapi_name.replace("Windows ", "")
            .replace("DirectSound", "DS")
        )
        return f"[{short_api}] {self.name}"


class AudioEngine:
    """Manages real-time microphone capture -> DSP -> virtual output + optional monitor."""

    def __init__(self, dsp: AudioDSP) -> None:
        self.dsp = dsp
        self._lock = threading.Lock()
        self._main_stream: Optional[sd.Stream] = None
        self._monitor_stream: Optional[sd.OutputStream] = None
        self._monitor_enabled = False
        self._monitor_volume = 0.70
        self._monitor_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=12)
        self._running = False
        self._active_samplerate = 48000
        self._on_status: Optional[Callable[[str, bool], None]] = None

    def set_status_callback(self, cb: Callable[[str, bool], None]) -> None:
        self._on_status = cb

    def _emit_status(self, msg: str, is_error: bool = False) -> None:
        if self._on_status:
            self._on_status(msg, is_error)

    @staticmethod
    def list_devices() -> Tuple[List[AudioDeviceInfo], List[AudioDeviceInfo]]:
        """Returns clean (inputs, outputs) prioritizing WASAPI then DirectSound/MME."""
        hostapis = sd.query_hostapis()
        raw_devices = sd.query_devices()

        preferred_apis = ("Windows WASAPI", "Windows DirectSound", "MME")
        inputs: List[AudioDeviceInfo] = []
        outputs: List[AudioDeviceInfo] = []

        for idx, dev in enumerate(raw_devices):
            api_name = hostapis[dev["hostapi"]]["name"]
            if api_name not in preferred_apis:
                continue
            name = str(dev["name"]).strip()
            if not name or name.startswith("Microsoft Sound Mapper") or name.startswith("Primary Sound"):
                continue

            info = AudioDeviceInfo(
                index=idx,
                name=name,
                hostapi_name=api_name,
                max_input_channels=int(dev["max_input_channels"]),
                max_output_channels=int(dev["max_output_channels"]),
                default_samplerate=int(dev["default_samplerate"]),
            )
            if info.max_input_channels > 0:
                inputs.append(info)
            if info.max_output_channels > 0:
                outputs.append(info)

        api_rank = {name: i for i, name in enumerate(preferred_apis)}
        inputs.sort(key=lambda d: (api_rank.get(d.hostapi_name, 99), d.name.lower()))
        outputs.sort(key=lambda d: (api_rank.get(d.hostapi_name, 99), d.name.lower()))
        return inputs, outputs

    @staticmethod
    def pick_default_devices(
        inputs: List[AudioDeviceInfo], outputs: List[AudioDeviceInfo]
    ) -> Tuple[Optional[AudioDeviceInfo], Optional[AudioDeviceInfo], Optional[AudioDeviceInfo]]:
        """Picks (best_mic, best_virtual_output, best_monitor_output)."""
        best_mic = None
        for d in inputs:
            n = d.name.lower()
            if "wasapi" in d.hostapi_name.lower() and "voicemeeter" not in n and "iriun" not in n:
                best_mic = d
                break
        if best_mic is None:
            for d in inputs:
                if "voicemeeter" not in d.name.lower():
                    best_mic = d
                    break
        if best_mic is None and inputs:
            best_mic = inputs[0]

        best_virtual = None
        for keyword in ("voicemeeter input", "cable input", "voicemeeter aux input", "voicemeeter"):
            for d in outputs:
                if "wasapi" in d.hostapi_name.lower() and keyword in d.name.lower():
                    best_virtual = d
                    break
            if best_virtual:
                break
        if best_virtual is None and outputs:
            best_virtual = outputs[0]

        best_monitor = None
        # If Voicemeeter AUX Input is available (and either Windows default playback is AUX Input
        # or Voicemeeter Input is the virtual output while hardware speakers are locked by WDM),
        # prefer [WASAPI] Voicemeeter AUX Input for clean non-exclusive monitoring.
        try:
            default_out_idx = sd.default.device[1]
            default_out_name = (
                str(sd.query_devices(default_out_idx)["name"]).lower()
                if default_out_idx is not None and default_out_idx >= 0
                else ""
            )
        except Exception:
            default_out_name = ""

        if "voicemeeter aux input" in default_out_name or (
            best_virtual is not None and "voicemeeter input" in best_virtual.name.lower()
        ):
            for d in outputs:
                if "wasapi" in d.hostapi_name.lower() and "voicemeeter aux input" in d.name.lower():
                    best_monitor = d
                    break

        if best_monitor is None:
            monitor_priority = (
                lambda n: "fifine" in n or "headphone" in n,
                lambda n: ("speaker" in n or "سماعة" in n) and "digital" not in n and "spdif" not in n,
                lambda n: "realtek" in n and "digital" not in n and "spdif" not in n,
                lambda n: True,
            )
            for rule in monitor_priority:
                for d in outputs:
                    n = d.name.lower()
                    if (
                        "wasapi" in d.hostapi_name.lower()
                        and "voicemeeter" not in n
                        and "cable" not in n
                        and "nvidia" not in n
                        and rule(n)
                    ):
                        best_monitor = d
                        break
                if best_monitor is not None:
                    break
        if best_monitor is None and outputs:
            best_monitor = outputs[0]

        return best_mic, best_virtual, best_monitor

    def is_running(self) -> bool:
        return self._running

    def set_monitor_volume(self, vol: float) -> None:
        self._monitor_volume = max(0.0, min(1.5, float(vol)))

    def start(
        self,
        input_idx: int,
        output_idx: int,
        monitor_enabled: bool = False,
        monitor_idx: Optional[int] = None,
        blocksize: int = 512,
    ) -> bool:
        self.stop()
        with self._lock:
            self._monitor_enabled = monitor_enabled
            in_info = sd.query_devices(input_idx)
            out_info = sd.query_devices(output_idx)
            in_ch = min(2, max(1, int(in_info["max_input_channels"])))
            out_ch = min(2, max(1, int(out_info["max_output_channels"])))

            candidate_rates = []
            for r in (48000, int(in_info["default_samplerate"]), int(out_info["default_samplerate"]), 44100):
                if r > 0 and r not in candidate_rates:
                    candidate_rates.append(r)

            last_err: Optional[Exception] = None
            started = False
            for sr in candidate_rates:
                try:
                    self.dsp.set_sample_rate(sr)
                    self.dsp.reset_buffers()
                    self._active_samplerate = sr

                    def _callback(indata, outdata, frames, time_info, status):
                        processed = self.dsp.process(indata)
                        if out_ch == 1:
                            outdata[:, 0] = 0.5 * (processed[:, 0] + processed[:, 1])
                        else:
                            outdata[:, :2] = processed[:, :2]

                        if self._monitor_enabled:
                            mon_block = (processed * self._monitor_volume).astype(np.float32)
                            try:
                                self._monitor_queue.put_nowait(mon_block)
                            except queue.Full:
                                try:
                                    self._monitor_queue.get_nowait()
                                    self._monitor_queue.put_nowait(mon_block)
                                except queue.Empty:
                                    pass

                    self._main_stream = sd.Stream(
                        device=(input_idx, output_idx),
                        samplerate=sr,
                        blocksize=blocksize,
                        channels=(in_ch, out_ch),
                        dtype="float32",
                        latency="low",
                        callback=_callback,
                    )
                    self._main_stream.start()
                    started = True
                    break
                except Exception as exc:
                    last_err = exc
                    if self._main_stream is not None:
                        try:
                            self._main_stream.close()
                        except Exception:
                            pass
                        self._main_stream = None

            if not started:
                self._emit_status(f"ما قدر يشتغل الكرت: {last_err}", is_error=True)
                return False

            self._running = True
            if monitor_enabled and monitor_idx is not None:
                self._start_monitor_stream(monitor_idx, blocksize)

            self._emit_status(
                f"الكرت شغّال الحين ({self._active_samplerate} Hz) — بدون تأخير",
                is_error=False,
            )
            return True

    def _start_monitor_stream(self, monitor_idx: int, blocksize: int = 512) -> None:
        self._stop_monitor_stream()
        while not self._monitor_queue.empty():
            try:
                self._monitor_queue.get_nowait()
            except queue.Empty:
                break

        try:
            mon_info = sd.query_devices(monitor_idx)
            mon_ch = min(2, max(1, int(mon_info["max_output_channels"])))

            def _mon_cb(outdata, frames, time_info, status):
                try:
                    blk = self._monitor_queue.get_nowait()
                except queue.Empty:
                    outdata.fill(0.0)
                    return

                n = min(frames, len(blk))
                if mon_ch == 1:
                    outdata[:n, 0] = 0.5 * (blk[:n, 0] + blk[:n, 1])
                else:
                    outdata[:n, :2] = blk[:n, :2]
                if n < frames:
                    outdata[n:].fill(0.0)

            self._monitor_stream = sd.OutputStream(
                device=monitor_idx,
                samplerate=self._active_samplerate,
                blocksize=blocksize,
                channels=mon_ch,
                dtype="float32",
                latency="low",
                callback=_mon_cb,
            )
            self._monitor_stream.start()
        except Exception as exc:
            self._monitor_enabled = False
            self._emit_status(f"الكرت شغّال بس السماعة ما اشتغلت للمراقبة: {exc}", is_error=True)

    def _stop_monitor_stream(self) -> None:
        if self._monitor_stream is not None:
            try:
                self._monitor_stream.stop()
                self._monitor_stream.close()
            except Exception:
                pass
            self._monitor_stream = None

    def set_monitor(self, enabled: bool, monitor_idx: Optional[int] = None) -> None:
        with self._lock:
            self._monitor_enabled = enabled
            if not self._running:
                return
            if enabled and monitor_idx is not None:
                self._start_monitor_stream(monitor_idx)
            else:
                self._stop_monitor_stream()

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._monitor_enabled = False
            self._stop_monitor_stream()
            if self._main_stream is not None:
                try:
                    self._main_stream.stop()
                    self._main_stream.close()
                except Exception:
                    pass
                self._main_stream = None
        self._emit_status("واقف الحين — اضغط تشغيل عشان يبدأ", is_error=False)
