"""Bridge to VB-Audio Voicemeeter Remote API for automatic virtual routing."""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
from typing import Optional


VOICEMEETER_DIR = r"C:\Program Files (x86)\VB\Voicemeeter"
REMOTE_DLL_64 = os.path.join(VOICEMEETER_DIR, "VoicemeeterRemote64.dll")
VM_BANANA_EXE = os.path.join(VOICEMEETER_DIR, "voicemeeterpro_x64.exe")
VM_BANANA_EXE_32 = os.path.join(VOICEMEETER_DIR, "voicemeeterpro.exe")
VM_STD_EXE = os.path.join(VOICEMEETER_DIR, "voicemeeter_x64.exe")


class VoicemeeterBridge:
    """Controls Voicemeeter via VoicemeeterRemote64.dll when available."""

    def __init__(self) -> None:
        self._dll: Optional[ctypes.CDLL] = None
        self._logged_in = False
        self._saved_hw_routing: Optional[tuple[float, float]] = None
        self._load_dll()

    def _load_dll(self) -> None:
        if not os.path.isfile(REMOTE_DLL_64):
            return
        try:
            dll = ctypes.WinDLL(REMOTE_DLL_64)
            dll.VBVMR_Login.restype = ctypes.c_long
            dll.VBVMR_Logout.restype = ctypes.c_long
            dll.VBVMR_IsParametersDirty.restype = ctypes.c_long
            dll.VBVMR_GetVoicemeeterType.argtypes = [ctypes.POINTER(ctypes.c_long)]
            dll.VBVMR_GetVoicemeeterType.restype = ctypes.c_long
            dll.VBVMR_SetParameterFloat.argtypes = [ctypes.c_char_p, ctypes.c_float]
            dll.VBVMR_SetParameterFloat.restype = ctypes.c_long
            dll.VBVMR_GetParameterFloat.argtypes = [
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_float),
            ]
            dll.VBVMR_GetParameterFloat.restype = ctypes.c_long
            self._dll = dll
        except OSError:
            self._dll = None

    def is_installed(self) -> bool:
        return self._dll is not None

    def _ensure_login(self) -> bool:
        if self._dll is None:
            return False
        if not self._logged_in:
            res = self._dll.VBVMR_Login()
            # 0 = OK, 1 = OK (Voicemeeter not launched yet)
            if res in (0, 1):
                self._logged_in = True
                time.sleep(0.25)
                self._dll.VBVMR_IsParametersDirty()
        return self._logged_in

    def get_voicemeeter_type(self) -> int:
        """Returns 1=Standard, 2=Banana, 3=Potato, or 0 if not running."""
        if not self._ensure_login() or self._dll is None:
            return 0
        vm_type = ctypes.c_long(0)
        res = self._dll.VBVMR_GetVoicemeeterType(ctypes.byref(vm_type))
        if res == 0:
            return int(vm_type.value)
        return 0

    def is_running(self) -> bool:
        return self.get_voicemeeter_type() > 0

    def _virtual_strip_index(self, vm_type: int, device_name: str) -> Optional[int]:
        name_lower = device_name.lower()
        if "voicemeeter" not in name_lower:
            return None
        if vm_type == 1:
            return 2
        if vm_type == 2:
            return 4 if "aux" in name_lower else 3
        if "vaio3" in name_lower:
            return 7
        if "aux" in name_lower:
            return 6
        return 5

    def launch_and_route(
        self,
        output_device_name: str = "",
        monitor_device_name: str = "",
        input_device_name: str = "",
        bypass_raw_mic_on_b1: bool = True,
    ) -> tuple[bool, str]:
        """Launches Voicemeeter if closed, then configures clean B1 mic + AUX speaker routing."""
        vm_type = self.get_voicemeeter_type()
        if vm_type == 0:
            exe = None
            for candidate in (VM_BANANA_EXE, VM_BANANA_EXE_32, VM_STD_EXE):
                if os.path.isfile(candidate):
                    exe = candidate
                    break
            if not exe:
                return False, "برنامج فويس ميتر مو مثبت على جهازك."
            try:
                subprocess.Popen([exe], cwd=VOICEMEETER_DIR)
            except OSError as exc:
                return False, f"ما قدر يشغّل فويس ميتر: {exc}"

            for _ in range(25):
                time.sleep(0.25)
                vm_type = self.get_voicemeeter_type()
                if vm_type > 0:
                    break

        if vm_type == 0 or self._dll is None:
            return False, "شغّلنا فويس ميتر بس لسا ما رد، انتظر ثانية وجرب مرة ثانية."

        self._dll.VBVMR_IsParametersDirty()

        out_strip = self._virtual_strip_index(vm_type, output_device_name)
        if out_strip is None:
            out_strip = 2 if vm_type == 1 else (3 if vm_type == 2 else 5)
        mon_strip = self._virtual_strip_index(vm_type, monitor_device_name)

        # Route Labobo virtual output strip -> B1 (Voicemeeter Out B1 mic)
        self._set_param(f"Strip[{out_strip}].Mute", 0.0)
        self._set_param(f"Strip[{out_strip}].B1", 1.0)
        self._set_param(f"Strip[{out_strip}].Gain", 0.0)
        if mon_strip is not None and mon_strip != out_strip:
            # Avoid doubling monitor sound; monitor goes through mon_strip (e.g. AUX Input)
            self._set_param(f"Strip[{out_strip}].A1", 0.0)

        # Route speaker/monitor strip (e.g. Voicemeeter AUX Input) -> A1 only (NO B1 feedback!)
        if mon_strip is not None and mon_strip != out_strip:
            self._set_param(f"Strip[{mon_strip}].Mute", 0.0)
            self._set_param(f"Strip[{mon_strip}].A1", 1.0)
            self._set_param(f"Strip[{mon_strip}].B1", 0.0)
            self._set_param(f"Strip[{mon_strip}].Gain", 0.0)

        # If Labobo captures a physical mic directly, prevent raw mic Strip[0] from doubling onto B1/A1
        if bypass_raw_mic_on_b1 and "voicemeeter" not in input_device_name.lower():
            if self._saved_hw_routing is None:
                prev_a1 = self._get_param("Strip[0].A1", 0.0)
                prev_b1 = self._get_param("Strip[0].B1", 1.0)
                self._saved_hw_routing = (prev_a1, prev_b1)
            self._set_param("Strip[0].B1", 0.0)
            self._set_param("Strip[0].A1", 0.0)

        # Ensure A1 (Bus 0) and B1 (Bus 3 in Banana / Bus 1 in Std) are unmuted and B1 is unity gain
        self._set_param("Bus[0].Mute", 0.0)
        b1_bus = 1 if vm_type == 1 else (3 if vm_type == 2 else 5)
        self._set_param(f"Bus[{b1_bus}].Mute", 0.0)
        self._set_param(f"Bus[{b1_bus}].Gain", 0.0)

        return True, (
            "مضبوط! المايك طالع على B1 وسماعتك AUX شغّالة بدون رجوع صدى."
        )

    def restore_mic_routing(self) -> None:
        """Restores hardware Strip[0] A1/B1 routing when Labobo stops."""
        if self._saved_hw_routing is None or not self.is_running():
            return
        prev_a1, prev_b1 = self._saved_hw_routing
        self._set_param("Strip[0].A1", prev_a1)
        self._set_param("Strip[0].B1", prev_b1 if prev_b1 > 0.0 else 1.0)
        self._saved_hw_routing = None
        time.sleep(0.1)

    def _get_param(self, param: str, default: float = 0.0) -> float:
        if self._dll is None:
            return default
        val = ctypes.c_float(default)
        res = self._dll.VBVMR_GetParameterFloat(param.encode("ascii"), ctypes.byref(val))
        return float(val.value) if res == 0 else default

    def _set_param(self, param: str, value: float) -> None:
        if self._dll is not None:
            self._dll.VBVMR_SetParameterFloat(param.encode("ascii"), ctypes.c_float(value))

    def close(self) -> None:
        self.restore_mic_routing()
        if self._dll is not None and self._logged_in:
            try:
                self._dll.VBVMR_Logout()
            except Exception:
                pass
            self._logged_in = False
