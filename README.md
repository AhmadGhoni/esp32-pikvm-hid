# ESP32 PiKVM HID Bridge

An ESP32 firmware that allows PiKVM to control a target computer through USB HID over Wi-Fi.

The firmware implements the PiKVM UDP HID protocol and exposes a native TinyUSB composite HID device (Keyboard + Mouse + Consumer Control) to the target machine.

Unlike serial-based HID bridges, this project communicates directly with PiKVM over UDP, providing low latency keyboard and mouse control using an ESP32-S3 with native USB OTG.

---

## Features

- USB HID Keyboard
- USB HID Relative Mouse
- Mouse Wheel
- 5 Mouse Buttons
- Modifier Key Support
- Multi-key Combination (Ctrl+C, Ctrl+V, Ctrl+A, Win, Alt, Shift, etc.)
- TinyUSB Composite HID
- Wi-Fi UDP Communication
- Compatible with PiKVM UDP HID Plugin
- ESP-IDF 5.x

---

## Architecture

```
           PiKVM
              │
      WebSocket HID
              │
        UDP HID Plugin
              │
           Wi-Fi UDP
              │
        ESP32-S2 / ESP32-S3
              │
         TinyUSB Composite HID
              │
          USB OTG Device
              │
         Target Computer
```

---

## Supported HID

### Keyboard

- Standard Keys
- Modifier Keys
    - Left / Right Ctrl
    - Left / Right Shift
    - Left / Right Alt
    - Left / Right GUI (Windows)
- Function Keys
- Navigation Keys
- Numpad
- Scroll Lock
- Caps Lock
- Num Lock

### Mouse

- Relative Movement
- Left Button
- Right Button
- Middle Button
- Back Button
- Forward Button
- Vertical Wheel

---

## Build

Requirements

- ESP-IDF 5.x
- TinyUSB
- ESP32-S2 or ESP32-S3

```bash
idf.py set-target esp32s2
idf.py build
idf.py flash
idf.py monitor
```

---

## PiKVM Configuration

Configure the UDP HID plugin on PiKVM to point to the ESP32 IP address.

Example:

```
host: 192.168.x.x
port: 4210
```

---

## Project Status

Current status:

- Stable Keyboard
- Stable Relative Mouse
- Stable Mouse Wheel
- Stable Modifier Keys
- Stable Multi-key Combination

Planned features:

- Absolute Mouse
- Consumer Control Keys
- OTA Update
- Configuration Web UI

---

## Acknowledgements

This project was originally inspired by:

https://github.com/KMChris/esp32-kvm-ip

The current firmware has been substantially redesigned and rewritten. The HID implementation, USB descriptors, keyboard processing, mouse processing, networking layer, and overall architecture differ significantly from the original project.

---

## License

MIT License