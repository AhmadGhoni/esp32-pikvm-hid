"""
Test script - sends simulated HID events to ESP32 over UDP.

Does not require Windows hooks - pure simulation for firmware testing.

Usage:
    python test_client.py --host <ESP32_IP> [--port 4210]

Tests:
    1. Mouse movement (circle)
    2. Mouse button clicks
    3. Vertical scroll
    4. Key press and release (typing "hello")
    5. Modifiers (Ctrl+A)
    6. Rapid-fire (throughput test)
"""

import argparse
import socket
import time
import math

from protocol import (
    UDP_PORT,
    PACKET_SIZE,
    pack_mouse,
    pack_keyboard,
)

seq = 0


def next_seq() -> int:
    global seq
    seq = (seq + 1) & 0xFFFFFFFF
    return seq


def send(sock: socket.socket, target: tuple, pkt: bytes, label: str = ""):
    assert len(pkt) == PACKET_SIZE, f"Bad packet size: {len(pkt)}"
    sock.sendto(pkt, target)
    if label:
        print(f"  → {label}")


def test_mouse_circle(sock, target, radius=100, steps=60):
    """Draws a circle with mouse movement (relative deltas)."""
    print("\n[TEST 1] Mouse movement - circle")
    prev_x, prev_y = 0, 0
    for i in range(steps + 1):
        angle = 2 * math.pi * i / steps
        x = int(radius * math.cos(angle))
        y = int(radius * math.sin(angle))
        dx = x - prev_x
        dy = y - prev_y
        prev_x, prev_y = x, y
        send(sock, target, pack_mouse(next_seq(), 0, dx, dy))
        time.sleep(0.008)  # ~125 Hz
    print(f"  Sent {steps + 1} mouse movement packets")


def test_mouse_buttons(sock, target):
    """Mouse button clicks: L, R, M, Back, Forward."""
    print("\n[TEST 2] Mouse buttons")
    buttons = [
        (0x01, "Left"),
        (0x02, "Right"),
        (0x04, "Middle"),
        (0x08, "Back"),
        (0x10, "Forward"),
    ]
    for mask, name in buttons:
        send(sock, target, pack_mouse(next_seq(), mask, 0, 0),
             f"{name} DOWN (buttons=0x{mask:02X})")
        time.sleep(0.05)
        send(sock, target, pack_mouse(next_seq(), 0, 0, 0),
             f"{name} UP (buttons=0x00)")
        time.sleep(0.1)


def test_scroll(sock, target):
    """Vertical scroll - 5 clicks down and 5 up."""
    print("\n[TEST 3] Vertical scroll")
    for i in range(5):
        send(sock, target, pack_mouse(next_seq(), 0, 0, 0, wheel=-1),
             "Scroll DOWN")
        time.sleep(0.05)
    for i in range(5):
        send(sock, target, pack_mouse(next_seq(), 0, 0, 0, wheel=1),
             "Scroll UP")
        time.sleep(0.05)


def test_keyboard_hello(sock, target):
    """Types 'hello' + Enter."""
    print("\n[TEST 4] Keyboard - typing 'hello' + Enter")
    # HID keycodes: h=0x0B, e=0x08, l=0x0F, o=0x12, Enter=0x28
    keys = [
        (0x0B, "h"),
        (0x08, "e"),
        (0x0F, "l"),
        (0x0F, "l"),
        (0x12, "o"),
        (0x28, "Enter"),
    ]
    for hid_code, name in keys:
        # Key down
        send(sock, target,
             pack_keyboard(next_seq(), 0, bytes([hid_code, 0, 0, 0, 0, 0])),
             f"'{name}' DOWN (HID 0x{hid_code:02X})")
        time.sleep(0.03)
        # Key up
        send(sock, target,
             pack_keyboard(next_seq(), 0, b'\x00' * 6),
             f"'{name}' UP")
        time.sleep(0.03)


def test_ctrl_a(sock, target):
    """Ctrl+A - select all."""
    print("\n[TEST 5] Modifiers - Ctrl+A")
    # LCtrl = modifier bit 0 = 0x01, A = HID 0x04
    send(sock, target,
         pack_keyboard(next_seq(), 0x01, bytes([0x04, 0, 0, 0, 0, 0])),
         "Ctrl+A DOWN")
    time.sleep(0.05)
    send(sock, target,
         pack_keyboard(next_seq(), 0, b'\x00' * 6),
         "Ctrl+A UP (all released)")
    time.sleep(0.1)


def test_rapid_fire(sock, target, count=500, rate=125):
    """Fast throughput test - sends mouse packets at the given rate."""
    print(f"\n[TEST 6] Rapid-fire: {count} packets @ {rate} Hz")
    interval = 1.0 / rate
    t0 = time.perf_counter()
    sent = 0

    for i in range(count):
        dx = int(5 * math.sin(2 * math.pi * i / 100))
        dy = int(5 * math.cos(2 * math.pi * i / 100))
        send(sock, target, pack_mouse(next_seq(), 0, dx, dy))
        sent += 1

        # Maintain constant rate
        elapsed = time.perf_counter() - t0
        expected = (i + 1) * interval
        sleep_time = expected - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

    elapsed = time.perf_counter() - t0
    actual_rate = sent / elapsed if elapsed > 0 else 0
    print(f"  Sent {sent} packets in {elapsed:.2f}s "
          f"(effective: {actual_rate:.0f} Hz)")


def main():
    parser = argparse.ArgumentParser(
        description="ESP32-S3 HID Relay - Test Client"
    )
    parser.add_argument("--host", required=True, help="ESP32 IP address")
    parser.add_argument("--port", type=int, default=UDP_PORT,
                        help=f"UDP port (default: {UDP_PORT})")
    parser.add_argument("--test", type=int, default=0,
                        help="Run specific test (1-6), 0=all")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (args.host, args.port)

    print(f"ESP32-S3 HID Relay - Test Client")
    print(f"Target: {args.host}:{args.port}")
    print(f"{'=' * 50}")

    tests = {
        1: test_mouse_circle,
        2: test_mouse_buttons,
        3: test_scroll,
        4: test_keyboard_hello,
        5: test_ctrl_a,
        6: test_rapid_fire,
    }

    if args.test == 0:
        for test_fn in tests.values():
            test_fn(sock, target)
            time.sleep(0.5)
    elif args.test in tests:
        tests[args.test](sock, target)
    else:
        print(f"ERROR: Unknown test {args.test}. Available: 1-{len(tests)}")
        return

    # Send empty report at the end (release all keys)
    send(sock, target, pack_keyboard(next_seq(), 0, b'\x00' * 6))
    send(sock, target, pack_mouse(next_seq(), 0, 0, 0))

    print(f"\n{'=' * 50}")
    print(f"All tests completed. Sent {seq} packets total.")

    sock.close()


if __name__ == "__main__":
    main()
