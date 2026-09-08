#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Makeblock MBBTCTR01 从模式 -> 电脑 BLE 直连 -> ViGEm 虚拟 Xbox 手柄

使用前：
  1. 手柄切从模式：同时长按 L1 + 蓝牙键 + R1，直到指示灯变红色闪烁后松开
  2. 安装 ViGEmBus 驱动：https://github.com/nefarius/ViGEmBus/releases/latest
  3. pip install bleak vgamepad

用法：
  python gamepad_ble.py
"""

import asyncio

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


async def find_controller():
    print("扫描手柄（从模式）...")
    devices = await BleakScanner.discover(timeout=8)
    for d in devices:
        if (d.name or "").startswith("MakeblockCTR"):
            print(f"找到手柄: {d.name} ({d.address})")
            return d.address
    return None


def main():
    async def run():
        addr = await find_controller()
        if not addr:
            print("未找到手柄。请先切到从模式（L1+蓝牙键+R1 长按到红灯闪烁）再运行。")
            return

        pad = vg.VX360Gamepad()
        print("虚拟手柄已创建，拨摇杆/按键即可，Ctrl+C 退出")

        pressed = set()
        B = vg.XUSB_BUTTON

        def notify(_sender, data):
            p = parse_frame(data)
            if not p:
                return
            lx, sh, ly, face, rx, dp, ry = p[0], p[1], p[2], p[3], p[4], p[5], p[6]

            pad.left_joystick_float(decode_axis(lx), decode_axis(ly, True))
            pad.right_joystick_float(decode_axis(rx), decode_axis(ry, True))

            # L2 / R2 是肩键，映射成模拟扳机
            pad.left_trigger_float(1.0 if sh & 0x08 else 0.0)
            pad.right_trigger_float(1.0 if sh & 0x02 else 0.0)

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
                cur.add(B.XUSB_GAMEPAD_X)       # 键 1（左）→ X（左）
            if face & 0x08:
                cur.add(B.XUSB_GAMEPAD_Y)       # 键 2（上）→ Y（上）
            if face & 0x02:
                cur.add(B.XUSB_GAMEPAD_A)       # 键 3（下）→ A（下）
            if face & 0x04:
                cur.add(B.XUSB_GAMEPAD_B)       # 键 4（右）→ B（右）
            if sh & 0x04:
                cur.add(B.XUSB_GAMEPAD_LEFT_SHOULDER)    # L1
            if sh & 0x01:
                cur.add(B.XUSB_GAMEPAD_RIGHT_SHOULDER)   # R1
            if sh & 0x20:
                cur.add(B.XUSB_GAMEPAD_LEFT_THUMB)       # 左摇杆按下
            if dp & 0x20:
                cur.add(B.XUSB_GAMEPAD_RIGHT_THUMB)      # 右摇杆按下
            if face & 0x10:
                cur.add(B.XUSB_GAMEPAD_START)            # PLUS
            if dp & 0x10:
                cur.add(B.XUSB_GAMEPAD_BACK)             # MENU
            if sh & 0x10:
                cur.add(B.XUSB_GAMEPAD_GUIDE)            # BT

            for b in cur - pressed:
                pad.press_button(button=b)
            for b in pressed - cur:
                pad.release_button(button=b)
            pressed.clear()
            pressed.update(cur)
            pad.update()

        try:
            async with BleakClient(addr, timeout=15) as client:
                await client.start_notify(FFE2_UUID, notify)
                print("已订阅 FFE2 通知，开始接收手柄数据")
                await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass

    asyncio.run(run())


if __name__ == "__main__":
    main()
