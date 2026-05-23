#!/usr/bin/env python3
from __future__ import annotations   # Python 3.9 compat for | union hints
"""
Input Switcher — MSI 321URX
Switches the active input via DDC/CI. Works on Windows and macOS.
"""
import json
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from pathlib import Path

try:
    from monitorcontrol import get_monitors, InputSource
except ImportError:
    print("Run:  pip install monitorcontrol")
    sys.exit(1)

CONFIG_FILE = Path(__file__).with_name("config.json")

# Known DDC model strings for the MSI 321URX.
# "FALCON" = Windows. The macOS name is learned on first run and saved.
KNOWN_MODELS: set[str] = {"FALCON"}

INPUTS = [
    InputSource.DP1,
    InputSource.DP2,
    InputSource.HDMI1,
    InputSource.HDMI2,
]

INPUT_LABELS = {
    InputSource.DP1:   "DisplayPort 1",
    InputSource.DP2:   "DisplayPort 2",
    InputSource.HDMI1: "HDMI 1",
    InputSource.HDMI2: "HDMI 2",
}


# ------------------------------------------------------------------ helpers --

def load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}


def save_config(data: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def scan_all_monitors() -> list[dict]:
    """Return [{index, model, inputs}] for every DDC-capable monitor."""
    results = []
    for i, mon in enumerate(get_monitors()):
        with mon:
            try:
                caps = mon.get_vcp_capabilities()
                model = caps.get("model", "").strip() or f"Monitor {i + 1}"
                raw_inputs = caps.get("inputs") or []
                inputs = [s.value for s in raw_inputs]
            except Exception:
                model = f"Monitor {i + 1}"
                inputs = []
            results.append({"index": i, "model": model, "inputs": inputs})
    return results


def find_msi(monitors: list[dict], known: set[str]) -> dict | None:
    for m in monitors:
        if m["model"].upper() in known:
            return m
    return None


# ------------------------------------------------------ one-time picker dlg --

class PickerDialog(tk.Toplevel):
    """Shown once on macOS (or any OS) when auto-detection fails."""

    def __init__(self, parent: tk.Tk, monitors: list[dict]):
        super().__init__(parent)
        self.title("Select your MSI 321URX")
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None

        ttk.Label(
            self,
            text="Could not auto-detect the MSI 321URX.\nSelect it from the list below:",
            justify="left",
        ).pack(padx=16, pady=(14, 6), anchor="w")

        self._var = tk.IntVar(value=-1)
        for m in monitors:
            label = f'{m["model"]}  (monitor {m["index"] + 1})'
            ttk.Radiobutton(self, text=label, variable=self._var, value=m["index"]).pack(
                anchor="w", padx=20, pady=2
            )

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=16, pady=(8, 12))
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right", padx=(4, 0))
        self._ok_btn = ttk.Button(bar, text="This is my MSI", command=self._confirm)
        self._ok_btn.pack(side="right")

        self._monitors = monitors
        self._var.trace_add("write", lambda *_: self._ok_btn.config(state="normal"))
        self._ok_btn.config(state="disabled")

        # Center over parent
        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w)//2}+{py + (ph - h)//2}")
        self.wait_window()

    def _confirm(self):
        idx = self._var.get()
        self.result = next((m for m in self._monitors if m["index"] == idx), None)
        self.destroy()


# --------------------------------------------------------------- main window --

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MSI 321URX — Input Switcher")
        self.resizable(False, False)

        self._cfg = load_config()
        # Merge any previously learned model name
        saved_model: str | None = self._cfg.get("model")
        if saved_model:
            KNOWN_MODELS.add(saved_model.upper())

        self._monitor_idx: int | None = None
        self._current: int | None = None
        self._selected = tk.IntVar()

        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        btn_frame = ttk.LabelFrame(outer, text="Input Source", padding=(10, 6))
        btn_frame.pack(fill="x")

        self._radios: list[ttk.Radiobutton] = []
        for src in INPUTS:
            rb = ttk.Radiobutton(
                btn_frame,
                text=INPUT_LABELS[src],
                variable=self._selected,
                value=src.value,
                command=self._on_pick,
                state="disabled",
            )
            rb.pack(anchor="w", pady=3)
            self._radios.append(rb)

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(10, 0))

        self._status_var = tk.StringVar(value="Scanning…")
        ttk.Label(bar, textvariable=self._status_var, foreground="gray").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(bar, text="↺", width=3, command=self._refresh).pack(side="left", padx=(6, 4))
        self._switch_btn = ttk.Button(bar, text="Switch", command=self._switch, state="disabled")
        self._switch_btn.pack(side="right")

    def _set_radios(self, state: str):
        for rb in self._radios:
            rb.config(state=state)

    # ------------------------------------------------------------ scanning --

    def _refresh(self):
        self._set_radios("disabled")
        self._switch_btn.config(state="disabled")
        self._status("Scanning…")
        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self):
        try:
            monitors = scan_all_monitors()
        except Exception as exc:
            self.after(0, self._on_error, f"Scan failed: {exc}")
            return

        found = find_msi(monitors, KNOWN_MODELS)

        if found is None:
            # Ask the user once, on the UI thread
            self.after(0, self._ask_user_pick, monitors)
            return

        self._finish_scan(found["index"])

    def _ask_user_pick(self, monitors: list[dict]):
        if not monitors:
            self._on_error("No DDC-capable monitors found.\nEnable DDC/CI in your monitor's OSD.")
            return

        dlg = PickerDialog(self, monitors)
        if dlg.result is None:
            self._status("Cancelled.")
            return

        chosen = dlg.result
        # Persist the model name so we never ask again
        self._cfg["model"] = chosen["model"]
        save_config(self._cfg)
        KNOWN_MODELS.add(chosen["model"].upper())

        threading.Thread(target=self._finish_scan, args=(chosen["index"],), daemon=True).start()

    def _finish_scan(self, idx: int):
        try:
            monitors = list(get_monitors())
            with monitors[idx] as mon:
                current = mon.get_input_source()
        except Exception as exc:
            self.after(0, self._on_error, f"Could not read input: {exc}")
            return

        self.after(0, self._on_scan_done, idx, current)

    def _on_scan_done(self, idx: int, current: int):
        self._monitor_idx = idx
        self._current = current
        self._selected.set(current)
        self._set_radios("normal")
        self._switch_btn.config(state="disabled")
        try:
            label = INPUT_LABELS[InputSource(current)]
        except ValueError:
            label = f"Source {current}"
        self._status(f"Current: {label}")

    # ----------------------------------------------------------- switching --

    def _on_pick(self):
        can_switch = self._selected.get() != self._current
        self._switch_btn.config(state="normal" if can_switch else "disabled")

    def _switch(self):
        val = self._selected.get()
        self._set_radios("disabled")
        self._switch_btn.config(state="disabled")
        try:
            label = INPUT_LABELS[InputSource(val)]
        except ValueError:
            label = f"Source {val}"
        self._status(f"Switching to {label}…")
        threading.Thread(target=self._do_switch, args=(val,), daemon=True).start()

    def _do_switch(self, val: int):
        try:
            monitors = list(get_monitors())
            with monitors[self._monitor_idx] as mon:
                mon.set_input_source(val)
            self.after(0, self._on_switched, val)
        except Exception as exc:
            self.after(0, self._on_error, f"Switch failed: {exc}")

    def _on_switched(self, val: int):
        self._current = val
        try:
            label = INPUT_LABELS[InputSource(val)]
        except ValueError:
            label = f"Source {val}"
        self._status(f"Switched to {label}.")
        self._refresh()

    # ---------------------------------------------------------------- misc --

    def _on_error(self, msg: str):
        self._status(msg)
        messagebox.showerror("Input Switcher", msg)

    def _status(self, msg: str):
        self._status_var.set(msg)


if __name__ == "__main__":
    App().mainloop()
