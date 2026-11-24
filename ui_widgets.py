"""Classic Creative Sound Blaster EAX Advanced HD Console UI widgets."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional


def draw_vgrad(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, c_top: str, c_bot: str) -> None:
    """Draws a smooth vertical gradient rectangle on a Tk Canvas."""
    h = max(1, int(y2 - y1))
    r1, g1, b1 = canvas.winfo_rgb(c_top)
    r2, g2, b2 = canvas.winfo_rgb(c_bot)
    r1, g1, b1 = r1 >> 8, g1 >> 8, b1 >> 8
    r2, g2, b2 = r2 >> 8, g2 >> 8, b2 >> 8
    step = 2 if h > 24 else 1
    for i in range(0, h, step):
        t = i / max(1, h - 1)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        col = f"#{r:02x}{g:02x}{b:02x}"
        canvas.create_rectangle(x1, y1 + i, x2, min(y2, y1 + i + step), fill=col, outline="")


class EAXAmountSlider(tk.Canvas):
    """Replica of the classic EAX Console horizontal slider with cyan fill and '...' pill thumb."""

    def __init__(
        self,
        master,
        width: int = 195,
        height: int = 34,
        bg_color: str = "#f2f2f2",
        initial: float = 100.0,
        command: Optional[Callable[[float], None]] = None,
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            bg=bg_color,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._slider_w = width
        self._slider_h = height
        self._bg = bg_color
        self._value = max(0.0, min(100.0, float(initial)))
        self.command = command
        self._dragging = False

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<MouseWheel>", self._on_wheel)
        self._redraw()

    def get(self) -> float:
        return self._value

    def set(self, val: float) -> None:
        self._value = max(0.0, min(100.0, float(val)))
        self._redraw()

    def _x_to_val(self, x: float) -> float:
        x_min, x_max = 24.0, self._slider_w - 34.0
        frac = (x - x_min) / max(1.0, x_max - x_min)
        return max(0.0, min(100.0, frac * 100.0))

    def _on_press(self, event) -> None:
        self._dragging = True
        self._set_and_emit(self._x_to_val(event.x))

    def _on_drag(self, event) -> None:
        if self._dragging:
            self._set_and_emit(self._x_to_val(event.x))

    def _on_release(self, _event) -> None:
        self._dragging = False

    def _on_wheel(self, event) -> None:
        delta = 5.0 if event.delta > 0 else -5.0
        self._set_and_emit(max(0.0, min(100.0, self._value + delta)))

    def _set_and_emit(self, val: float) -> None:
        if abs(val - self._value) > 0.05:
            self._value = val
            self._redraw()
            if self.command:
                self.command(self._value)

    def _redraw(self) -> None:
        self.delete("all")
        cy = self._slider_h / 2.0
        x_min, x_max = 24.0, self._slider_w - 34.0

        self.create_text(10, cy, text="0", fill="#222222", font=("Tahoma", 9))
        self.create_text(self._slider_w - 15, cy, text="100", fill="#222222", font=("Tahoma", 9))

        # Recessed groove track
        self.create_rectangle(x_min, cy - 3, x_max, cy + 3, fill="#b4b8bf", outline="#7a7f87")
        self.create_line(x_min + 1, cy + 3, x_max, cy + 3, fill="#ffffff")

        # Aqua cyan active bar
        thumb_x = x_min + (self._value / 100.0) * (x_max - x_min)
        if thumb_x > x_min + 2:
            self.create_rectangle(x_min + 1, cy - 2, thumb_x, cy + 2, fill="#38bdf8", outline="")

        # Classic silver pill thumb with 3 dots '...'
        tw, th = 14, 8
        tx1, ty1, tx2, ty2 = thumb_x - tw, cy - th, thumb_x + tw, cy + th
        self.create_rectangle(tx1, ty1, tx2, ty2, fill="#e4e7ec", outline="#6e737d", width=1)
        self.create_line(tx1 + 1, ty1 + 1, tx2 - 1, ty1 + 1, fill="#ffffff")
        self.create_line(tx1 + 1, ty2 - 1, tx2 - 1, ty2 - 1, fill="#b8bec8")
        for dx in (-5, 0, 5):
            self.create_oval(
                thumb_x + dx - 1.2, cy - 1.2, thumb_x + dx + 1.2, cy + 1.2,
                fill="#444851", outline=""
            )
