#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Makeblock MBBTCTR01 手柄 GUI：BLE 直连 -> ViGEm 虚拟 Xbox 手柄

使用前：
  1. 手柄切从模式：同时长按 L1 + 蓝牙键 + R1，直到红灯闪烁
  2. 安装 ViGEmBus 驱动：https://github.com/nefarius/ViGEmBus/releases/latest
"""

import asyncio
import queue
import threading
import tkinter as tk
from tkinter import ttk

import vgamepad as vg
from bleak import BleakClient, BleakScanner

FFE2_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"


def decode_axis(raw, invert=False):
    v = 2 * (raw - 128)
    if invert:
        v = -v
    if v <= -254:
        v = -255
    if v >= 254:
        v = 255
    if abs(v) <= 8:
        v = 0
    return max(-1.0, min(1.0, v / 255.0))


def parse_frame(data):
    if len(data) != 10 or data[0] != 0xFF or data[1] != 0x55:
        return None
    p = data[2:]
    if (sum(p[:7]) & 0xFF) != p[7]:
        return None
    return p


SHOULDER_NAMES = [(0x01, "R1"), (0x02, "R2"), (0x04, "L1"), (0x08, "L2"),
                  (0x10, "BT"), (0x20, "L3")]
FACE_NAMES = [(0x01, "1"), (0x08, "2"), (0x02, "3"), (0x04, "4"), (0x10, "+")]
DPAD_NAMES = [(0x01, "上"), (0x02, "下"), (0x04, "左"), (0x08, "右"),
              (0x10, "MENU"), (0x20, "R3")]


class Bridge:
    """后台 BLE 桥接线程，负责连接手柄并映射到 ViGEm"""

    def __init__(self, q):
        self.q = q
        self.running = False
        self.pad = None
        self.pressed = set()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main())
        except Exception as e:
            self.q.put(("error", str(e)))

    async def _async_main(self):
        self.q.put(("status", "扫描手柄中..."))
        addr = None
        name = ""
        devices = await BleakScanner.discover(timeout=8)
        for d in devices:
            if (d.name or "").startswith("MakeblockCTR"):
                addr = d.address
                name = d.name
                break
        if not addr:
            self.q.put(("error", "未找到手柄。请先切到从模式（L1+蓝牙键+R1 长按到红灯闪烁）"))
            return

        try:
            self.pad = vg.VX360Gamepad()
        except Exception as e:
            self.q.put(("error", f"虚拟手柄初始化失败：{e}\n请确认已安装 ViGEmBus 驱动"))
            return

        self.q.put(("status", f"找到 {name}，连接中..."))
        async with BleakClient(addr, timeout=15) as client:
            await client.start_notify(FFE2_UUID, self._on_notify)
            self.q.put(("connected", name))
            while self.running:
                await asyncio.sleep(0.1)

        self.q.put(("disconnected", "已断开，可重新连接"))
        self._reset_pad()

    def _reset_pad(self):
        if self.pad:
            try:
                for b in self.pressed:
                    self.pad.release_button(button=b)
                self.pressed.clear()
                self.pad.update()
            except Exception:
                pass

    def _on_notify(self, _sender, data):
        p = parse_frame(data)
        if not p:
            return
        lx, sh, ly, face, rx, dp, ry = p[0], p[1], p[2], p[3], p[4], p[5], p[6]

        if self.pad:
            self.pad.left_joystick_float(decode_axis(lx), decode_axis(ly, True))
            self.pad.right_joystick_float(decode_axis(rx), decode_axis(ry, True))
            self.pad.left_trigger_float(1.0 if sh & 0x08 else 0.0)
            self.pad.right_trigger_float(1.0 if sh & 0x02 else 0.0)

            B = vg.XUSB_BUTTON
            cur = set()
            if dp & 0x01:
                cur.add(B.XUSB_GAMEPAD_DPAD_UP)
            if dp & 0x02:
                cur.add(B.XUSB_GAMEPAD_DPAD_DOWN)
            if dp & 0x04:
                cur.add(B.XUSB_GAMEPAD_DPAD_LEFT)
            if dp & 0x08:
                cur.add(B.XUSB_GAMEPAD_DPAD_RIGHT)
            if face & 0x01:
                cur.add(B.XUSB_GAMEPAD_X)
            if face & 0x08:
                cur.add(B.XUSB_GAMEPAD_Y)
            if face & 0x02:
                cur.add(B.XUSB_GAMEPAD_A)
            if face & 0x04:
                cur.add(B.XUSB_GAMEPAD_B)
            if sh & 0x04:
                cur.add(B.XUSB_GAMEPAD_LEFT_SHOULDER)
            if sh & 0x01:
                cur.add(B.XUSB_GAMEPAD_RIGHT_SHOULDER)
            if sh & 0x20:
                cur.add(B.XUSB_GAMEPAD_LEFT_THUMB)
            if dp & 0x20:
                cur.add(B.XUSB_GAMEPAD_RIGHT_THUMB)
            if face & 0x10:
                cur.add(B.XUSB_GAMEPAD_START)
            if dp & 0x10:
                cur.add(B.XUSB_GAMEPAD_BACK)
            if sh & 0x10:
                cur.add(B.XUSB_GAMEPAD_GUIDE)
            for b in cur - self.pressed:
                self.pad.press_button(button=b)
            for b in self.pressed - cur:
                self.pad.release_button(button=b)
            self.pressed.clear()
            self.pressed.update(cur)
            self.pad.update()

        pressed_names = [n for m, n in SHOULDER_NAMES if sh & m]
        pressed_names += [n for m, n in FACE_NAMES if face & m]
        pressed_names += [n for m, n in DPAD_NAMES if dp & m]

        self.q.put(("data", {
            "lx": int(decode_axis(lx) * 255),
            "ly": int(decode_axis(ly, True) * 255),
            "rx": int(decode_axis(rx) * 255),
            "ry": int(decode_axis(ry, True) * 255),
            "buttons": pressed_names,
        }))


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.bridge = Bridge(self.q)

        root.title("Makeblock 手柄 → Xbox 手柄")
        root.geometry("440x400")
        root.resizable(False, False)

        self.status_var = tk.StringVar(value="未连接（请切手柄到从模式）")
        ttk.Label(root, textvariable=self.status_var, font=("", 11)).pack(pady=10)

        self.btn = ttk.Button(root, text="扫描并连接手柄", command=self._on_connect)
        self.btn.pack(pady=4)

        axis_frame = ttk.LabelFrame(root, text="摇杆（上/右为正）")
        axis_frame.pack(fill="x", padx=12, pady=8)
        self.axis_vars = {}
        for i, name in enumerate(["LX", "LY", "RX", "RY"]):
            r, c = i // 2, (i % 2) * 4
            ttk.Label(axis_frame, text=name).grid(row=r, column=c, padx=(8, 4), pady=3, sticky="w")
            var = tk.StringVar(value="0")
            ttk.Label(axis_frame, textvariable=var, width=7, anchor="e").grid(row=r, column=c + 1)
            bar = ttk.Progressbar(axis_frame, length=120, maximum=255, mode="determinate")
            bar.grid(row=r, column=c + 2, padx=6)
            self.axis_vars[name] = (var, bar)

        btn_frame = ttk.LabelFrame(root, text="按键")
        btn_frame.pack(fill="both", expand=True, padx=12, pady=6)
        self.buttons_var = tk.StringVar(value="—")
        ttk.Label(btn_frame, textvariable=self.buttons_var, wraplength=400,
                  justify="left").pack(anchor="nw", padx=8, pady=8)

        ttk.Label(root, text="从模式：L1 + 蓝牙键 + R1 长按到红灯闪烁",
                  foreground="gray").pack(side="bottom", pady=6)

        self._poll()

    def _on_connect(self):
        self.btn.config(state="disabled")
        self.status_var.set("扫描中...")
        self.bridge.start()

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "status":
                    self.status_var.set(msg[1])
                elif kind == "connected":
                    self.status_var.set(f"已连接：{msg[1]}")
                    self.btn.config(state="disabled")
                elif kind == "error":
                    self.status_var.set(msg[1])
                    self.btn.config(state="normal")
                elif kind == "disconnected":
                    self.status_var.set(msg[1])
                    self.btn.config(state="normal")
                elif kind == "data":
                    d = msg[1]
                    for k in ["LX", "LY", "RX", "RY"]:
                        var, bar = self.axis_vars[k]
                        val = d[k.lower()]
                        var.set(str(val))
                        bar["value"] = abs(val)
                    self.buttons_var.set("、".join(d["buttons"]) if d["buttons"] else "—")
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

    def close(self):
        self.bridge.stop()


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.close(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
