# Makeblock Gamepad

把 Makeblock MBBTCTR01 蓝牙遥控器变成 Windows 通用 Xbox 手柄——**无需 ESP32**，手柄切「从模式」后 BLE 直连电脑。

## 原理

手柄从模式下作为 BLE 外设广播自己（名字 `MakeblockCTRxxxxxx`），通过 `FFE2` 通知持续发送 `FF 55` 帧（10 字节：两摇杆 + 17 键 + 校验和）。本工具用 `bleak` 连接手柄、订阅通知、解析帧，再用 `vgamepad`（ViGEm）映射成虚拟 Xbox 360 手柄。

## 快速开始（Windows）

1. 手柄切从模式：**同时长按 `L1` + 蓝牙键 + `R1`**，直到指示灯变红色闪烁
2. 安装 ViGEmBus 驱动（只需一次）：<https://github.com/nefarius/ViGEmBus/releases/latest>
3. 安装依赖：

   ```bash
   pip install bleak vgamepad
   ```

4. 运行 GUI：

   ```bash
   python gamepad_gui.py
   ```

   （命令行版：`python gamepad_ble.py`）

点「扫描并连接手柄」，拨摇杆/按键，游戏里即出现 Xbox 360 手柄。

## 打包成单 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name MakeblockGamepad \
  --add-binary "<python>\Lib\site-packages\vgamepad\win\vigem\client\x64\ViGEmClient.dll;vgamepad\win\vigem\client\x64" \
  gamepad_gui.py
```

产物在 `dist/MakeblockGamepad.exe`。

## 按键映射

| 手柄 | Xbox 虚拟手柄 |
|---|---|
| 左摇杆 LX/LY | 左摇杆 |
| 右摇杆 RX/RY | 右摇杆 |
| 十字键 | DPAD |
| 1 / 2 / 3 / 4 | A / B / X / Y |
| L1 / R1 | LB / RB |
| L2 / R2 | LT / RT |
| 左/右摇杆按下 | L3 / R3 |
| +（PLUS） | START |
| MENU | BACK |
| BT | GUIDE |

## 协议

- 帧：`FF 55` + 8 字节（LX / 肩键掩码 / LY / 键1-4掩码 / RX / 十字键掩码 / RY / 校验和）
- 校验和 = byte2~8 求和 mod 256
- 摇杆中心 `0x80`，`axis = 2*(raw-128)`，Y 轴取反，死区 8

## macOS

macOS 上 `bleak` 走 CoreBluetooth（无需额外驱动），运行：

```bash
python gamepad_mac.py
```

可读取并实时显示手柄数据（两摇杆 + 17 键）。

注意：macOS 没有类似 ViGEmBus 的通用虚拟游戏手柄驱动，系统级虚拟手柄映射需借助第三方方案；如需键盘映射可自行扩展（如 pyautogui）。
