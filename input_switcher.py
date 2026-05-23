#!/usr/bin/env python3
from __future__ import annotations
"""
Input Switcher — MSI MAG 321URX
Menu-bar widget on macOS  •  CustomTkinter GUI on Windows / Linux
"""
import json
import re as _re
import shutil as _shutil
import subprocess
import sys
import threading
from pathlib import Path

IS_MAC = sys.platform == "darwin"

# ── platform-specific imports ─────────────────────────────────────────────────
if IS_MAC:
    try:
        import rumps
    except ImportError:
        print("Missing dependency — run:  pip install --user rumps")
        sys.exit(1)
    from enum import IntEnum
    class InputSource(IntEnum):
        DP1   = 15
        DP2   = 16
        HDMI1 = 17
        HDMI2 = 18
else:
    try:
        import customtkinter as ctk
    except ImportError:
        print("Missing dependency — run:  pip install customtkinter")
        sys.exit(1)
    try:
        from monitorcontrol import get_monitors, InputSource
    except ImportError:
        print("Missing dependency — run:  pip install monitorcontrol")
        sys.exit(1)
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

# ── constants ─────────────────────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).with_name("config.json")

# "FALCON" = Windows DDC name  •  "MPG321UX OLED" = macOS/m1ddc name
KNOWN_MODELS: set[str] = {"FALCON", "MPG321UX OLED"}

INPUTS = [InputSource.DP1, InputSource.DP2, InputSource.HDMI1, InputSource.HDMI2]

INPUT_LABELS = {
    InputSource.DP1:   "DisplayPort 1",
    InputSource.DP2:   "DisplayPort 2",
    InputSource.HDMI1: "HDMI 1",
    InputSource.HDMI2: "HDMI 2",
}

if IS_MAC:
    INPUT_SHORT = {
        InputSource.DP1:   "DP1",
        InputSource.DP2:   "DP2",
        InputSource.HDMI1: "HDMI1",
        InputSource.HDMI2: "HDMI2",
    }
else:
    BTN_W, BTN_H = 130, 64
    COLOR_ACTIVE   = ("#1a6fc4", "#1a6fc4")
    COLOR_INACTIVE = ("#2b2b2b", "#2b2b2b")
    COLOR_HOVER_A  = ("#2178d0", "#2178d0")
    COLOR_HOVER_I  = ("#3a3a3a", "#3a3a3a")

# ── macOS DDC backend (m1ddc) ─────────────────────────────────────────────────
_M1DDC = _shutil.which("m1ddc") or "/opt/homebrew/bin/m1ddc"
_DISPLAY_RE = _re.compile(r'^\[(\d+)\]\s+(.+?)\s+\([0-9A-Fa-f-]+\)\s*$')


def _m1ddc(*args: str) -> tuple[str, int]:
    try:
        r = subprocess.run([_M1DDC] + list(args), capture_output=True, text=True, timeout=5)
        return r.stdout.strip(), r.returncode
    except FileNotFoundError:
        raise RuntimeError("m1ddc not found.\n\nInstall with Homebrew:\n  brew install m1ddc")
    except subprocess.TimeoutExpired:
        raise RuntimeError("m1ddc timed out — is DDC/CI enabled in the monitor OSD?")


def scan_monitors_mac() -> list[dict]:
    out, rc = _m1ddc("display", "list")
    if rc != 0 or not out:
        raise RuntimeError(
            "No displays found by m1ddc.\n\n"
            "• Connect the monitor via USB-C / Thunderbolt (not HDMI)\n"
            "• Enable DDC/CI in the monitor OSD"
        )
    results = []
    for line in out.splitlines():
        m = _DISPLAY_RE.match(line.strip())
        if m:
            results.append({"index": int(m.group(1)) - 1, "model": m.group(2).strip(), "inputs": []})
    if not results:
        raise RuntimeError(f"Could not parse m1ddc output:\n{out}")
    return results


def mac_get_input(zero_idx: int) -> int:
    out, rc = _m1ddc("display", str(zero_idx + 1), "get", "input")
    if rc != 0:
        raise RuntimeError(f"m1ddc get input failed: {out}")
    try:
        return int(out)
    except ValueError:
        raise RuntimeError(f"Unexpected m1ddc output: {out!r}")


def mac_set_input(val: int, zero_idx: int) -> None:
    out, rc = _m1ddc("display", str(zero_idx + 1), "set", "input", str(val))
    if rc != 0:
        raise RuntimeError(f"m1ddc set input failed: {out}")


# ── shared helpers ────────────────────────────────────────────────────────────
def load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}


def save_config(data: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def scan_all_monitors() -> list[dict]:
    if IS_MAC:
        return scan_monitors_mac()
    results = []
    for i, mon in enumerate(get_monitors()):
        with mon:
            try:
                caps = mon.get_vcp_capabilities()
                model = caps.get("model", "").strip() or f"Monitor {i + 1}"
                inputs = [s.value for s in (caps.get("inputs") or [])]
            except Exception:
                model, inputs = f"Monitor {i + 1}", []
            results.append({"index": i, "model": model, "inputs": inputs})
    return results


def find_msi(monitors: list[dict], known: set[str]) -> dict | None:
    for m in monitors:
        if m["model"].upper() in known:
            return m
    return None


# ── macOS menu bar app ────────────────────────────────────────────────────────
if IS_MAC:
    _AGENT_LABEL = "com.msi.input-switcher"
    _AGENT_PLIST = Path.home() / f"Library/LaunchAgents/{_AGENT_LABEL}.plist"

    class MenuBarApp(rumps.App):
        def __init__(self):
            self._cfg = load_config()
            self._current: int | None = self._cfg.get("last_input")
            self._monitor_idx: int = 0

            saved = self._cfg.get("model")
            if saved:
                KNOWN_MODELS.add(saved.upper())

            try:
                monitors = scan_all_monitors()
                found = find_msi(monitors, KNOWN_MODELS)
                if found:
                    self._monitor_idx = found["index"]
                    if not self._cfg.get("model"):
                        self._cfg["model"] = found["model"]
                        save_config(self._cfg)
            except Exception:
                pass

            super().__init__("MSI Input", title=self._bar_title(), quit_button="Quit")

            rumps.Timer(self._hide_dock, 0).start()
            self._refresh_menu()

        def _hide_dock(self, _):
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(
                    AppKit.NSApplicationActivationPolicyAccessory
                )
            except Exception:
                pass

        def _bar_title(self) -> str:
            if self._current is None:
                return "🖥"
            try:
                return INPUT_SHORT[InputSource(self._current)]
            except (ValueError, KeyError):
                return "🖥"

        def _refresh_menu(self):
            self.menu.clear()
            for src in INPUTS:
                item = rumps.MenuItem(INPUT_LABELS[src], callback=self._make_cb(src))
                if self._current == src.value:
                    item.state = 1
                self.menu.add(item)
            self.menu.add(rumps.separator)
            login_item = rumps.MenuItem("Open at Login", callback=self._toggle_login)
            login_item.state = 1 if _AGENT_PLIST.exists() else 0
            self.menu.add(login_item)

        def _make_cb(self, src: InputSource):
            def on_click(_):
                try:
                    mac_set_input(src.value, self._monitor_idx)
                except Exception as exc:
                    rumps.notification("Switch failed", "", str(exc), sound=False)
                    return
                self._current = src.value
                self._cfg["last_input"] = src.value
                save_config(self._cfg)
                self.title = INPUT_SHORT[src]
                self._refresh_menu()
            return on_click

        def _toggle_login(self, sender):
            if _AGENT_PLIST.exists():
                subprocess.run(["launchctl", "unload", str(_AGENT_PLIST)], check=False)
                _AGENT_PLIST.unlink(missing_ok=True)
                sender.state = 0
            else:
                self._install_agent()
                sender.state = 1

        def _install_agent(self):
            if getattr(sys, "frozen", False):
                # Bundled .app — launch the bundle binary directly
                program_args = f"<string>{sys.executable}</string>"
            else:
                python = sys.executable
                script = str(Path(__file__).resolve())
                program_args = (
                    f"<string>{python}</string>\n"
                    f"    <string>{script}</string>"
                )
            plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key>             <string>{_AGENT_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    {program_args}
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key>         <true/>
  <key>KeepAlive</key>         <false/>
</dict></plist>
"""
            _AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)
            _AGENT_PLIST.write_text(plist)
            subprocess.run(["launchctl", "load", str(_AGENT_PLIST)], check=False)


# ── Windows / Linux customtkinter app ─────────────────────────────────────────
if not IS_MAC:
    class PickerDialog(ctk.CTkToplevel):
        def __init__(self, parent, monitors: list[dict]):
            super().__init__(parent)
            self.title("Select monitor")
            self.resizable(False, False)
            self.grab_set()
            self.result: dict | None = None
            self._monitors = monitors
            self._var = ctk.IntVar(value=-1)

            ctk.CTkLabel(
                self,
                text="Could not auto-detect the MSI 321URX.\nSelect it from the list below:",
                justify="left",
                font=ctk.CTkFont(size=13),
            ).pack(padx=20, pady=(18, 10), anchor="w")

            for m in monitors:
                ctk.CTkRadioButton(
                    self,
                    text=f'{m["model"]}  (monitor {m["index"] + 1})',
                    variable=self._var,
                    value=m["index"],
                    command=lambda: self._ok_btn.configure(state="normal"),
                ).pack(anchor="w", padx=24, pady=4)

            bar = ctk.CTkFrame(self, fg_color="transparent")
            bar.pack(fill="x", padx=20, pady=(12, 16))
            ctk.CTkButton(bar, text="Cancel", width=90, fg_color="transparent",
                          border_width=1, command=self.destroy).pack(side="right", padx=(6, 0))
            self._ok_btn = ctk.CTkButton(bar, text="This is my MSI", width=130,
                                         state="disabled", command=self._confirm)
            self._ok_btn.pack(side="right")

            self.update_idletasks()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            px, py = parent.winfo_x(), parent.winfo_y()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"+{px + (pw - w)//2}+{py + (ph - h)//2}")
            self.wait_window()

        def _confirm(self):
            idx = self._var.get()
            self.result = next((m for m in self._monitors if m["index"] == idx), None)
            self.destroy()

    class App(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("Input Switcher")
            self.resizable(False, False)

            self._cfg = load_config()
            saved = self._cfg.get("model")
            if saved:
                KNOWN_MODELS.add(saved.upper())

            self._monitor_idx: int | None = None
            self._current: int | None = None
            self._btns: dict[int, ctk.CTkButton] = {}
            self._busy = False

            self._build_ui()
            self._refresh()

        def _build_ui(self):
            ctk.CTkLabel(
                self,
                text="MSI MAG 321URX",
                font=ctk.CTkFont(size=17, weight="bold"),
            ).pack(pady=(22, 2))

            ctk.CTkLabel(
                self,
                text="SELECT INPUT SOURCE",
                font=ctk.CTkFont(size=10),
                text_color="#888888",
            ).pack(pady=(0, 14))

            grid = ctk.CTkFrame(self, fg_color="transparent")
            grid.pack(padx=20)

            for i, src in enumerate(INPUTS):
                row, col = divmod(i, 2)
                btn = ctk.CTkButton(
                    grid,
                    text=INPUT_LABELS[src],
                    width=BTN_W,
                    height=BTN_H,
                    corner_radius=10,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    fg_color=COLOR_INACTIVE,
                    hover_color=COLOR_HOVER_I,
                    state="disabled",
                    command=lambda s=src: self._on_click(s),
                )
                btn.grid(row=row, column=col, padx=6, pady=6)
                self._btns[src.value] = btn

            self._status_var = ctk.StringVar(value="Scanning…")
            ctk.CTkLabel(
                self,
                textvariable=self._status_var,
                font=ctk.CTkFont(size=11),
                text_color="#888888",
            ).pack(pady=(14, 4))

            ctk.CTkButton(
                self,
                text="↺  Refresh",
                width=110,
                height=28,
                corner_radius=6,
                font=ctk.CTkFont(size=11),
                fg_color="transparent",
                border_width=1,
                border_color="#444444",
                hover_color="#2b2b2b",
                command=self._refresh,
            ).pack(pady=(0, 20))

        def _set_state(self, state: str):
            for btn in self._btns.values():
                btn.configure(state=state)

        def _highlight(self, current: int | None):
            for val, btn in self._btns.items():
                if val == current:
                    btn.configure(fg_color=COLOR_ACTIVE, hover_color=COLOR_HOVER_A)
                else:
                    btn.configure(fg_color=COLOR_INACTIVE, hover_color=COLOR_HOVER_I)

        def _refresh(self):
            if self._busy:
                return
            self._busy = True
            self._set_state("disabled")
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
                self.after(0, self._ask_user_pick, monitors)
                return
            self._finish_scan(found["index"])

        def _ask_user_pick(self, monitors: list[dict]):
            if not monitors:
                self._on_error("No DDC-capable monitors found.\nEnable DDC/CI in the monitor OSD.")
                return
            dlg = PickerDialog(self, monitors)
            if dlg.result is None:
                self._busy = False
                self._status("Cancelled.")
                return
            chosen = dlg.result
            self._cfg["model"] = chosen["model"]
            save_config(self._cfg)
            KNOWN_MODELS.add(chosen["model"].upper())
            threading.Thread(target=self._finish_scan, args=(chosen["index"],), daemon=True).start()

        def _finish_scan(self, idx: int):
            try:
                with list(get_monitors())[idx] as mon:
                    current = mon.get_input_source()
            except Exception as exc:
                self.after(0, self._on_error, f"Could not read input: {exc}")
                return
            self.after(0, self._on_scan_done, idx, current)

        def _on_scan_done(self, idx: int, current: int):
            self._monitor_idx = idx
            self._current = current
            self._busy = False
            self._set_state("normal")
            self._highlight(current)
            self._status(f"Active: {self._label(current)}")

        def _on_click(self, src: InputSource):
            if self._busy or src.value == self._current:
                return
            self._busy = True
            self._set_state("disabled")
            self._status(f"Switching to {self._label(src.value)}…")
            threading.Thread(target=self._do_switch, args=(src.value,), daemon=True).start()

        def _do_switch(self, val: int):
            try:
                with list(get_monitors())[self._monitor_idx] as mon:
                    mon.set_input_source(val)
                self.after(0, self._on_switched, val)
            except Exception as exc:
                self.after(0, self._on_error, f"Switch failed: {exc}")

        def _on_switched(self, val: int):
            self._current = val
            self._busy = False
            self._set_state("normal")
            self._highlight(val)
            self._status(f"Active: {self._label(val)}")

        def _label(self, val: int) -> str:
            try:
                return INPUT_LABELS[InputSource(val)]
            except ValueError:
                return f"Source {val}"

        def _on_error(self, msg: str):
            self._busy = False
            self._status(msg)
            from tkinter import messagebox
            messagebox.showerror("Input Switcher", msg)

        def _status(self, msg: str):
            self._status_var.set(msg)


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if IS_MAC:
        MenuBarApp().run()
    else:
        App().mainloop()
