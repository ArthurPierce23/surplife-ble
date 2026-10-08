# surplife-ble

Control **Surplife / ZENGGE RGB floor lamps** (the round 360° "ring" floor lamps sold on Ozon/AliExpress that advertise as `IOTWF…` over Bluetooth) directly from a PC — **no app, no Wi-Fi setup, no cloud**.

Useful if the Surplife app is unavailable for your phone (region-locked or 64-bit only) or if you want to drive the lamps from your own software, e.g. screen-color ambient lighting.

*По-русски — ниже.*

## What works

| Feature | Status |
|---|---|
| Power on / off | ✅ |
| Static color (HSV) | ✅ instant, no fade of its own |
| Fast updates | ✅ ~60 commands/s without backlog (Windows, built-in BT 5.0 adapter) |
| State query | ✅ reports power and the effect chosen with the IR remote |
| Built-in effects (select by number) | ❌ the documented `0x38` / `0x42` / `0x61` commands are ignored on this model |

Works out of the box: the lamp does **not** need to be added to the app or connected to Wi-Fi first.

## Quick start

```bash
pip install bleak
python surplife_ble.py scan
python surplife_ble.py color AA:BB:CC:DD:EE:FF ff7a00
python surplife_ble.py rainbow AA:BB:CC:DD:EE:FF
```

A lamp accepts **one** BLE connection — close the phone app (or turn off phone Bluetooth) first.

## Protocol notes

GATT service `FFFF`: write `FF01` (write without response), notify `FF02`.

Every packet is wrapped:

```
00 <seq> 80 00 00 <len> <len+1> <kind> <inner…>      kind: 0x0a = query, 0x0b = command
```

| Command | Inner bytes |
|---|---|
| Power on | `71 23 0f a3` |
| Power off | `71 24 0f a4` |
| Color | `3b a1 <hue/2> <sat 0-100> <val 1-100> 00 00 00 00 00 00 00 00` |
| State query (kind `0x0a`) | `81 8a 8b 96` |

The state reply arrives on `FF02` as JSON after the 8-byte header:
`{"code":0,"payload":"EA8104007709 23 25 6E 32 F0B4…"}` — byte 6 is power (`23` on / `24` off), then mode (`25` = built-in effect), effect number and speed as set by the IR remote. Colors set over BLE are **not** reflected in the state.

### Gotchas we hit

- **Subscribe to notifications first.** Without `start_notify(FF02)` Windows fails writes with *"The parameter is incorrect"*.
- **Windows needs a scan before connecting by address** (`BleakScanner.find_device_by_address`).
- **Gamma.** The LEDs are linear while screen colors are gamma-encoded, so orange looks pale yellow. Apply gamma ≈ 2.8 relative to the brightest channel (keeps brightness, fixes hue) — see `Lamp.rgb()`.
- **Smoothness is limited by the lamp, not the link**: hue has 2° steps (180 values), brightness 100 steps. Above ~60 commands/s you only resend the same values. The lamp itself switches colors instantly, so smooth transitions = many small steps from your side.
- On Windows the default timer tick is ~15.6 ms — use a high-resolution timer (`timeBeginPeriod(1)`) for an even 60 Hz loop.

Related prior work: [8none1/zengge_lednetwf](https://github.com/8none1/zengge_lednetwf) (ring-light and strip firmwares — the wrapper and `3b` commands match), [flux_led](https://github.com/lightinglibs/flux_led).

---

## По-русски

Управление круглыми RGB-торшерами Surplife / ZENGGE (в Bluetooth видны как `IOTWF…`) с компьютера: без приложения, без Wi-Fi и без облака. Работает сразу из коробки.

- `scan` — найти торшеры, `on` / `off`, `color <hex>`, `rainbow`, `state`.
- Цвет меняется мгновенно, до ~60 команд в секунду, так что плавность делается программно мелкими шагами.
- Встроенные эффекты по Bluetooth включить не удалось — только с ИК-пульта.
- Перед подключением закрой приложение на телефоне: торшер держит одно соединение.
- Для правильных цветов (оранжевый, а не жёлтый) нужна гамма-коррекция ≈ 2.8 — уже встроена.

## License

MIT
