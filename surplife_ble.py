#!/usr/bin/env python3
"""Control Surplife / ZENGGE "IOTWF..." RGB floor lamps over Bluetooth LE — no app, no Wi-Fi, no cloud.

    pip install bleak
    python surplife_ble.py scan
    python surplife_ble.py on  AA:BB:CC:DD:EE:FF
    python surplife_ble.py off AA:BB:CC:DD:EE:FF
    python surplife_ble.py color AA:BB:CC:DD:EE:FF ff7a00
    python surplife_ble.py rainbow AA:BB:CC:DD:EE:FF
    python surplife_ble.py state AA:BB:CC:DD:EE:FF
"""
import asyncio
import colorsys
import json
import sys
import time

from bleak import BleakClient, BleakScanner

SERVICE = "0000ffff-0000-1000-8000-00805f9b34fb"
WRITE = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY = "0000ff02-0000-1000-8000-00805f9b34fb"

# Screen/sRGB colors are gamma-encoded, the lamp's LEDs are linear. Without correction orange
# shows as pale yellow. 2.8 matched a Tuya bulb by eye; applied relative to the brightest channel.
GAMMA = 2.8


class Lamp:
    def __init__(self, address: str):
        self.address = address
        self.client: BleakClient | None = None
        self.seq = 0
        self.last_state: str | None = None

    async def __aenter__(self):
        # Right after another program disconnects, Windows may still be tearing the link down —
        # the first attempt then fails with "operation was canceled", so retry a few times.
        for attempt in range(3):
            try:
                # Windows: the device has to be seen in a scan before connecting by address
                await BleakScanner.find_device_by_address(self.address, timeout=15)
                self.client = BleakClient(self.address, timeout=20)
                await self.client.connect()
                # Required: the lamp (or Windows) ignores writes until notifications are enabled
                await self.client.start_notify(NOTIFY, self._on_notify)
                return self
            except Exception:
                if self.client and self.client.is_connected:
                    await self.client.disconnect()
                if attempt == 2:
                    raise
                await asyncio.sleep(2)

    async def __aexit__(self, *exc):
        await self.client.disconnect()

    def _on_notify(self, _sender, data: bytearray):
        try:
            self.last_state = json.loads(data[8:].decode())["payload"]
        except Exception:
            self.last_state = data.hex()

    def _wrap(self, inner: list[int], kind: int) -> bytes:
        # 00 seq 80 00 00 len len+1 kind | inner     (kind 0x0a = query, 0x0b = command)
        self.seq = (self.seq + 1) & 0xFF
        return bytes([0x00, self.seq, 0x80, 0x00, 0x00, len(inner), len(inner) + 1, kind, *inner])

    async def _send(self, inner: list[int], kind: int = 0x0B):
        await self.client.write_gatt_char(WRITE, self._wrap(inner, kind), response=False)

    async def power(self, on: bool):
        cmd = [0x71, 0x23 if on else 0x24, 0x0F]
        await self._send(cmd + [sum(cmd) & 0xFF])

    async def hsv(self, h: int, s: int, v: int):
        """h 0-359 (lamp resolution 2 degrees), s 0-100, v 1-100."""
        await self._send([0x3B, 0xA1, (h % 360) // 2, s, max(1, v), 0, 0, 0, 0, 0, 0, 0, 0])

    async def rgb(self, r: int, g: int, b: int, gamma: float = GAMMA):
        m = max(r, g, b)
        if m and gamma > 1:
            r, g, b = (round(m * (x / m) ** gamma) for x in (r, g, b))
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        await self.hsv(round(h * 360), round(s * 100), round(v * 100))

    async def state(self) -> str | None:
        self.last_state = None
        await self._send([0x81, 0x8A, 0x8B, 0x96], kind=0x0A)
        await asyncio.sleep(1)
        return self.last_state


async def scan():
    found = await BleakScanner.discover(timeout=10, return_adv=True)
    for dev, adv in found.values():
        name = adv.local_name or dev.name or ""
        if any(0x5A00 <= k <= 0x5AFF for k in adv.manufacturer_data) or name.startswith(("IOTWF", "LEDnetWF")):
            print(f"{dev.address}  {name:<12}  rssi {adv.rssi}")


async def main(argv):
    if len(argv) < 2 or argv[1] not in {"scan", "on", "off", "color", "rainbow", "state"}:
        print(__doc__)
        return
    if argv[1] == "scan":
        return await scan()
    async with Lamp(argv[2]) as lamp:
        if argv[1] in ("on", "off"):
            await lamp.power(argv[1] == "on")
        elif argv[1] == "color":
            hx = argv[3].lstrip("#")
            await lamp.rgb(int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16))
        elif argv[1] == "rainbow":
            t0 = time.perf_counter()
            for n in range(600):  # 10 s at 60 steps/s
                await lamp.hsv(int(n * 360 / 240), 100, 100)
                await asyncio.sleep(max(0, t0 + (n + 1) / 60 - time.perf_counter()))
        elif argv[1] == "state":
            print(await lamp.state())
        await asyncio.sleep(0.3)  # let the last write go out before disconnecting


if __name__ == "__main__":
    asyncio.run(main(sys.argv))
