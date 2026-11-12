"""
Автокликер с графическим интерфейсом (tkinter + pynput).

Запуск из Python:  python autoclicker_gui.py
Сборка в .exe:     см. build.bat
"""

import random
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from pynput import keyboard, mouse

BUTTONS = {
    "Левая": mouse.Button.left,
    "Правая": mouse.Button.right,
    "Средняя": mouse.Button.middle,
}
HOTKEYS = ["F6", "F7", "F8", "F9", "F10"]
START_DELAY_MS = 2000  # пауза после нажатия кнопки «Старт», чтобы успеть навести курсор


class AutoClicker:
    def __init__(self, root):
        self.root = root
        root.title("Автокликер")
        root.resizable(False, False)

        self.controller = mouse.Controller()
        self.running = threading.Event()
        self.quit = threading.Event()
        self.cfg = None
        self.done = 0

        self.build_ui()
        self.hotkey_var.trace_add("write", lambda *_: self.update_hint())
        self.update_hint()

        threading.Thread(target=self.click_loop, daemon=True).start()
        self.listener = keyboard.Listener(on_press=self.on_key)
        self.listener.daemon = True
        self.listener.start()

        root.protocol("WM_DELETE_WINDOW", self.close)

    # ---------- интерфейс ----------
    def build_ui(self):
        pad = {"padx": 10, "pady": 4}
        frm = ttk.Frame(self.root, padding=12)
        frm.grid()

        ttk.Label(frm, text="Кнопки мыши:").grid(row=0, column=0, sticky="w", **pad)
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=0, column=1, sticky="w", **pad)
        self.button_vars = {}
        for i, name in enumerate(BUTTONS):
            var = tk.BooleanVar(value=(name == "Левая"))
            ttk.Checkbutton(btn_frame, text=name, variable=var).grid(row=0, column=i, padx=(0, 8))
            self.button_vars[name] = var

        ttk.Label(frm, text="Задержка (мс):").grid(row=1, column=0, sticky="w", **pad)
        self.delay_var = tk.StringVar(value="100")
        ttk.Entry(frm, textvariable=self.delay_var, width=10).grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Случайный разброс (мс):").grid(row=2, column=0, sticky="w", **pad)
        self.jitter_var = tk.StringVar(value="0")
        ttk.Entry(frm, textvariable=self.jitter_var, width=10).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Число циклов (0 = ∞):").grid(row=3, column=0, sticky="w", **pad)
        self.count_var = tk.StringVar(value="0")
        ttk.Entry(frm, textvariable=self.count_var, width=10).grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Горячая клавиша:").grid(row=4, column=0, sticky="w", **pad)
        self.hotkey_var = tk.StringVar(value="F6")
        ttk.Combobox(frm, textvariable=self.hotkey_var, values=HOTKEYS,
                     width=8, state="readonly").grid(row=4, column=1, sticky="w", **pad)

        self.topmost_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Поверх всех окон", variable=self.topmost_var,
                        command=lambda: self.root.attributes("-topmost", self.topmost_var.get())
                        ).grid(row=5, column=0, columnspan=2, sticky="w", **pad)

        self.toggle_btn = ttk.Button(frm, text="Старт", command=self.on_button)
        self.toggle_btn.grid(row=6, column=0, columnspan=2, sticky="ew", **pad)

        self.status_var = tk.StringVar(value="Остановлено")
        ttk.Label(frm, textvariable=self.status_var, font=("TkDefaultFont", 10, "bold")
                  ).grid(row=7, column=0, columnspan=2, **pad)

        self.hint_var = tk.StringVar()
        ttk.Label(frm, textvariable=self.hint_var, foreground="gray", wraplength=300
                  ).grid(row=8, column=0, columnspan=2, **pad)

    def update_hint(self):
        self.hint_var.set(
            f"{self.hotkey_var.get()} — старт/стоп из любого окна. "
            f"Кнопка «Старт» запускает клики через {START_DELAY_MS // 1000} с, "
            f"чтобы вы успели навести курсор."
        )

    # ---------- логика ----------
    def read_config(self):
        try:
            delay = float(self.delay_var.get().replace(",", "."))
            jitter = float(self.jitter_var.get().replace(",", "."))
            count = int(self.count_var.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Задержка, разброс и число циклов должны быть числами.")
            return None
        if delay < 1 or jitter < 0 or count < 0:
            messagebox.showerror("Ошибка", "Задержка ≥ 1 мс, разброс и число циклов ≥ 0.")
            return None
        buttons = [BUTTONS[n] for n, v in self.button_vars.items() if v.get()]
        if not buttons:
            messagebox.showerror("Ошибка", "Выберите хотя бы одну кнопку мыши.")
            return None
        return {"buttons": buttons, "delay": delay / 1000, "jitter": jitter / 1000, "count": count}

    def start(self):
        cfg = self.read_config()
        if cfg is None:
            return
        self.cfg = cfg
        self.done = 0
        self.running.set()
        self.toggle_btn.config(text="Стоп")
        self.status_var.set("Работает")

    def stop(self):
        self.running.clear()
        self.toggle_btn.config(text="Старт")
        self.status_var.set("Остановлено")

    def toggle(self):
        if self.running.is_set():
            self.stop()
        else:
            self.start()

    def on_button(self):
        if self.running.is_set():
            self.stop()
        else:
            self.status_var.set(f"Старт через {START_DELAY_MS // 1000} с…")
            self.toggle_btn.config(state="disabled")
            self.root.after(START_DELAY_MS, self.delayed_start)

    def delayed_start(self):
        self.toggle_btn.config(state="normal")
        self.start()
        if not self.running.is_set():
            self.status_var.set("Остановлено")

    def on_key(self, key):
        if key == getattr(keyboard.Key, self.hotkey_var.get().lower(), None):
            self.root.after(0, self.toggle)

    def click_loop(self):
        while not self.quit.is_set():
            if not self.running.wait(timeout=0.1):
                continue
            cfg = self.cfg
            for button in cfg["buttons"]:
                self.controller.click(button)
            self.done += 1
            if cfg["count"] and self.done >= cfg["count"]:
                self.root.after(0, self.stop)
                time.sleep(0.05)
                continue
            time.sleep(cfg["delay"] + random.uniform(0, cfg["jitter"]))

    def close(self):
        self.quit.set()
        self.running.clear()
        self.listener.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    AutoClicker(root)
    root.mainloop()
