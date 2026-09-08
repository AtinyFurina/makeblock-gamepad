#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Makeblock MBBTCTR01 手柄 macOS 版：BLE 读取 + 状态显示

macOS 上 bleak 自动使用 CoreBluetooth 后端，无需额外驱动/权限配置。
手柄切从模式（L1 + 蓝牙键 + R1 长按到红灯闪烁）后运行：

    python gamepad_mac.py

注：macOS 没有类似 ViGEmBus 的通用虚拟游戏手柄驱动，本脚本负责读取并
实时显示手柄数据（两摇杆 + 17 键），可作为数据源进一步接键盘映射等。
"""

import asyncio

from bleak import BleakClient, BleakScanner

FFE2_UUID = "0000ffe2-0000-1000-8000-00805f9b34fb"

SHOULDER = [(0x01, "R2"), (0x02, "R1"), (0x04, "L2"), (0x08, "L1"),
            (0x10, "BT"), (0x20, "L3")]
FACE = [(0x01, "1"), (0x08, "2"), (0x02, "3"), (0x04, "4"), (0x10, "+")]
DPAD = [(0x01, "上"), (0x02, "下"), (0x04, "左"), (0x08, "右"),
        (0x10, "MENU"), (0x20, "R3")]


def decode(raw, invert=False):
    v = 2 * (raw - 128)
    if invert:
        v = -v
    if v <= -254:
        v = -255
    if v >= 254:
        v = 255
    if abs(v) <= 8:
        v = 0
    return v


def parse_frame(data):
    if len(data) != 10 or data[0] != 0xFF or data[1] != 0x55:
        return None
    p = data[2:]
    if (sum(p[:7]) & 0xFF) != p[7]:
        return None
    return p


def fmt(data):
    lx, sh, ly, face, rx, dp, ry = (data[0], data[1], data[2], data[3],
                                    data[4], data[5], data[6])
    btns = ([n for m, n in SHOULDER if sh & m]
            + [n for m, n in FACE if face & m]
            + [n for m, n in DPAD if dp & m])
    return (f"LX={decode(lx):>4} LY={decode(ly, True):>4} "
            f"RX={decode(rx):>4} RY={decode(ry, True):>4}  "
            f"BTN={'+'.join(btns) if btns else '-'}")


def on_notify(_sender, data):
    p = parse_frame(data)
    if p:
        print("\r" + fmt(p), end="", flush=True)


async def main():
    print("扫描手柄（从模式）...")
    addr = None
    devices = await BleakScanner.discover(timeout=8)
    for d in devices:
        if (d.name or "").startswith("MakeblockCTR"):
            addr = d.address
            print(f"找到手柄: {d.name}")
            break
    if not addr:
        print("未找到手柄。请先切从模式（L1+蓝牙键+R1 长按到红灯闪烁）。")
        return

    async with BleakClient(addr, timeout=15) as client:
        await client.start_notify(FFE2_UUID, on_notify)
        print("已连接，拨摇杆/按键即可（Ctrl+C 退出）")
        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n退出")
