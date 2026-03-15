"""
ESP32-S3 KVM - Server (Windows)

Captures keyboard events (LL Hook) and mouse events (Raw Input + LL Hook)
and sends them as UDP packets to ESP32-S3.

Architecture:
  - WM_INPUT (Raw Input)  → raw mouse deltas (no Windows acceleration)
  - WH_MOUSE_LL           → blocking mouse on Host when KVM active
  - WH_KEYBOARD_LL        → capturing keys + blocking on Host
  - Sender Thread (125Hz) → fixed polling rate, dx/dy accumulation

KVM toggle: Scroll Lock

Usage:
    python server.py --host <ESP32_IP> [--port 4210] [--rate 125]
"""

import argparse
import ctypes
import ctypes.wintypes as wintypes
import socket
import sys
import threading
import time

from protocol import (
    UDP_PORT,
    pack_keyboard,
    pack_mouse,
    pack_consumer,
)
from hid_keymap import VK_MODIFIER_MAP, VK_TO_HID, VK_TO_CONSUMER
from clipboard_typer import read_clipboard_text, text_to_keystrokes

# ═══════════════════════════════════════════════════════════════════
#  WinAPI Constants
# ═══════════════════════════════════════════════════════════════════

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WH_MOUSE_LL    = 14

WM_KEYDOWN     = 0x0100;  WM_KEYUP       = 0x0101
WM_SYSKEYDOWN  = 0x0104;  WM_SYSKEYUP    = 0x0105
WM_LBUTTONDOWN = 0x0201;  WM_LBUTTONUP   = 0x0202
WM_RBUTTONDOWN = 0x0204;  WM_RBUTTONUP   = 0x0205
WM_MBUTTONDOWN = 0x0207;  WM_MBUTTONUP   = 0x0208
WM_MOUSEWHEEL  = 0x020A;  WM_MOUSEHWHEEL = 0x020E
WM_XBUTTONDOWN = 0x020B;  WM_XBUTTONUP   = 0x020C
WM_MOUSEMOVE   = 0x0200

WM_INPUT       = 0x00FF
WM_DESTROY     = 0x0002

VK_SCROLL      = 0x91
WHEEL_DELTA    = 120

# LLKHF_EXTENDED = bit 0 of flags
LLKHF_EXTENDED = 0x01

# Raw Input constants
RID_INPUT             = 0x10000003
RIM_TYPEMOUSE         = 0
RIDEV_INPUTSINK       = 0x00000100
MOUSE_MOVE_RELATIVE   = 0x00

# Raw Input mouse button flags
RI_MOUSE_BUTTON_1_DOWN = 0x0001
RI_MOUSE_BUTTON_1_UP   = 0x0002
RI_MOUSE_BUTTON_2_DOWN = 0x0004
RI_MOUSE_BUTTON_2_UP   = 0x0008
RI_MOUSE_BUTTON_3_DOWN = 0x0010
RI_MOUSE_BUTTON_3_UP   = 0x0020
RI_MOUSE_BUTTON_4_DOWN = 0x0040
RI_MOUSE_BUTTON_4_UP   = 0x0080
RI_MOUSE_BUTTON_5_DOWN = 0x0100
RI_MOUSE_BUTTON_5_UP   = 0x0200
RI_MOUSE_WHEEL         = 0x0400
RI_MOUSE_HWHEEL        = 0x0800

# Window class constants
CS_HREDRAW     = 0x0002
HWND_MESSAGE   = wintypes.HWND(-3)

# ═══════════════════════════════════════════════════════════════════
#  WinAPI Structures
# ═══════════════════════════════════════════════════════════════════

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode",      wintypes.DWORD),
        ("scanCode",    wintypes.DWORD),
        ("flags",       wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt",          POINT),
        ("mouseData",   wintypes.DWORD),
        ("flags",       wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_long,      # LRESULT
    ctypes.c_int,       # nCode
    wintypes.WPARAM,    # wParam
    wintypes.LPARAM,    # lParam
)

# ── Raw Input Structures ─────────────────────────────────────────

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort),
        ("usUsage",     ctypes.c_ushort),
        ("dwFlags",     wintypes.DWORD),
        ("hwndTarget",  wintypes.HWND),
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType",  wintypes.DWORD),
        ("dwSize",  wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam",  wintypes.WPARAM),
    ]

class RAWMOUSE_BUTTONS(ctypes.Structure):
    _fields_ = [
        ("usButtonFlags", ctypes.c_ushort),
        ("usButtonData",  ctypes.c_ushort),
    ]

class RAWMOUSE_UNION(ctypes.Union):
    _fields_ = [
        ("ulButtons", wintypes.ULONG),
        ("buttons",   RAWMOUSE_BUTTONS),
    ]

class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags",            ctypes.c_ushort),
        ("_buttons",           RAWMOUSE_UNION),
        ("ulRawButtons",       wintypes.ULONG),
        ("lLastX",             ctypes.c_long),
        ("lLastY",             ctypes.c_long),
        ("ulExtraInformation", wintypes.ULONG),
    ]

class RAWINPUT_MOUSE(ctypes.Structure):
    """Simplified RAWINPUT structure - header + mouse only."""
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("mouse",  RAWMOUSE),
    ]

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize",        wintypes.UINT),
        ("style",         wintypes.UINT),
        ("lpfnWndProc",   ctypes.c_void_p),
        ("cbClsExtra",    ctypes.c_int),
        ("cbWndExtra",    ctypes.c_int),
        ("hInstance",     wintypes.HINSTANCE),
        ("hIcon",         wintypes.HICON),
        ("hCursor",       wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName",  wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm",       wintypes.HICON),
    ]

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long,      # LRESULT
    wintypes.HWND,      # hWnd
    wintypes.UINT,      # uMsg
    wintypes.WPARAM,    # wParam
    wintypes.LPARAM,    # lParam
)

# ── WinAPI function prototypes ───────────────────────────────────

user32.RegisterRawInputDevices.argtypes = [
    ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT
]
user32.RegisterRawInputDevices.restype = wintypes.BOOL

user32.GetRawInputData.argtypes = [
    wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p,
    ctypes.POINTER(wintypes.UINT), wintypes.UINT
]
user32.GetRawInputData.restype = wintypes.UINT

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD
]
user32.SetWindowsHookExW.restype = ctypes.c_void_p

user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
]
user32.CallNextHookEx.restype = ctypes.c_long

user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.ATOM

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.DefWindowProcW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
user32.DefWindowProcW.restype = ctypes.c_long

# ═══════════════════════════════════════════════════════════════════
#  Shared State
# ═══════════════════════════════════════════════════════════════════

class InputState:
    """Thread-safe input state - updated by hooks and Raw Input."""

    def __init__(self):
        self.lock = threading.Lock()
        self.sequence: int = 0

        # KVM toggle
        self.kvm_active: bool = False

        # Mouse (accumulated by Raw Input, reset by sender)
        self.mouse_buttons: int = 0
        self.mouse_dx: int = 0
        self.mouse_dy: int = 0
        self.mouse_wheel: int = 0
        self.mouse_pan: int = 0
        self.mouse_buttons_prev: int = 0  # For change detection

        # Keyboard
        self.modifiers: int = 0
        self.pressed_keys: set[int] = set()
        self.kbd_dirty: bool = False  # Keyboard state change flag

        # Consumer (multimedia / browser)
        self.consumer_usage: int = 0  # Currently pressed consumer usage (0 = none)
        self.consumer_dirty: bool = False

        # Clipboard paste
        self.pasting: bool = False
        self.paste_chars: list[tuple[int, int]] = []  # (hid_keycode, modifiers)
        self.paste_index: int = 0
        self.paste_phase: int = 0  # 0=press, 1=release
        self.paste_tick_counter: int = 0  # To pace typing

    def next_seq(self) -> int:
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        return self.sequence


state = InputState()

# ═══════════════════════════════════════════════════════════════════
#  Raw Input Handler (WM_INPUT)
# ═══════════════════════════════════════════════════════════════════

def process_raw_input(lParam: int):
    """Processes raw mouse data from WM_INPUT."""
    dwSize = wintypes.UINT(0)
    user32.GetRawInputData(
        wintypes.HANDLE(lParam), RID_INPUT, None,
        ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER)
    )

    if dwSize.value == 0:
        return

    raw = RAWINPUT_MOUSE()
    result = user32.GetRawInputData(
        wintypes.HANDLE(lParam), RID_INPUT, ctypes.byref(raw),
        ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER)
    )

    if result == ctypes.c_uint(-1).value:
        return

    if raw.header.dwType != RIM_TYPEMOUSE:
        return

    mouse = raw.mouse

    with state.lock:
        if not state.kvm_active:
            return

        # Relative movement (skip absolute - tablets etc.)
        if mouse.usFlags == MOUSE_MOVE_RELATIVE:
            state.mouse_dx += mouse.lLastX
            state.mouse_dy += mouse.lLastY

        # Buttons
        flags = mouse._buttons.buttons.usButtonFlags

        if flags & RI_MOUSE_BUTTON_1_DOWN:
            state.mouse_buttons |= 0x01
        if flags & RI_MOUSE_BUTTON_1_UP:
            state.mouse_buttons &= ~0x01

        if flags & RI_MOUSE_BUTTON_2_DOWN:
            state.mouse_buttons |= 0x02
        if flags & RI_MOUSE_BUTTON_2_UP:
            state.mouse_buttons &= ~0x02

        if flags & RI_MOUSE_BUTTON_3_DOWN:
            state.mouse_buttons |= 0x04
        if flags & RI_MOUSE_BUTTON_3_UP:
            state.mouse_buttons &= ~0x04

        if flags & RI_MOUSE_BUTTON_4_DOWN:
            state.mouse_buttons |= 0x08   # Back
        if flags & RI_MOUSE_BUTTON_4_UP:
            state.mouse_buttons &= ~0x08

        if flags & RI_MOUSE_BUTTON_5_DOWN:
            state.mouse_buttons |= 0x10   # Forward
        if flags & RI_MOUSE_BUTTON_5_UP:
            state.mouse_buttons &= ~0x10

        # Scroll
        if flags & RI_MOUSE_WHEEL:
            delta = ctypes.c_short(mouse._buttons.buttons.usButtonData).value
            state.mouse_wheel += delta // WHEEL_DELTA

        if flags & RI_MOUSE_HWHEEL:
            delta = ctypes.c_short(mouse._buttons.buttons.usButtonData).value
            state.mouse_pan += delta // WHEEL_DELTA

# ═══════════════════════════════════════════════════════════════════
#  Window Procedure (for Raw Input)
# ═══════════════════════════════════════════════════════════════════

def _wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_INPUT:
        process_raw_input(lparam)
        return 0
    if msg == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

# Keep reference (prevents GC)
wnd_proc_cb = WNDPROC(_wnd_proc)

# ═══════════════════════════════════════════════════════════════════
#  Hook Callbacks
# ═══════════════════════════════════════════════════════════════════

def _keyboard_proc(nCode: int, wParam: int, lParam: int) -> int:
    if nCode >= 0:
        kbd = KBDLLHOOKSTRUCT.from_address(lParam)
        vk = kbd.vkCode
        is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
        is_extended = bool(kbd.flags & LLKHF_EXTENDED)

        # Scroll Lock → KVM toggle
        # We handle BOTH DOWN and UP - both are passed to Windows.
        # Toggle KVM only on key-down.
        if vk == VK_SCROLL:
            if is_down:
                with state.lock:
                    state.kvm_active = not state.kvm_active
                    active = state.kvm_active
                    if not active:
                        # Reset state when KVM disabled
                        state.modifiers = 0
                        state.pressed_keys.clear()
                        state.mouse_buttons = 0
                        state.mouse_dx = 0
                        state.mouse_dy = 0
                        state.mouse_wheel = 0
                        state.mouse_pan = 0
                        state.kbd_dirty = True
                        state.consumer_usage = 0
                        state.consumer_dirty = True
                        # Cancel any active paste
                        if state.pasting:
                            state.pasting = False
                            state.paste_chars = []
                            state.paste_index = 0
                status = "ON" if active else "OFF"
                print(f"[KVM] {status}")
            # Pass Scroll Lock to host (don't block DOWN or UP)
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        with state.lock:
            if state.kvm_active:
                # ── Paste: Shift+Insert → paste clipboard ─────
                VK_INSERT = 0x2D
                if vk == VK_INSERT and is_down and (state.modifiers & 0x22):
                    # Release all keys before pasting
                    state.modifiers = 0
                    state.pressed_keys.clear()
                    state.kbd_dirty = True
                    # Read clipboard (quick operation)
                    text = read_clipboard_text()
                    if text:
                        chars = text_to_keystrokes(text)
                        if chars:
                            state.paste_chars = chars
                            state.paste_index = 0
                            state.paste_phase = 0
                            state.paste_tick_counter = 0
                            state.pasting = True
                            print(f"[PASTE] {len(chars)} keystroke(s) queued")
                        else:
                            print("[PASTE] No typeable characters in clipboard")
                    else:
                        print("[PASTE] Clipboard empty or no text")
                    return 1

                # ── During paste: block keys, Esc cancels ─────
                if state.pasting:
                    if vk == 0x1B and is_down:  # Escape
                        done = state.paste_index
                        total = len(state.paste_chars)
                        state.pasting = False
                        state.paste_chars = []
                        state.paste_index = 0
                        state.paste_tick_counter = 0
                        state.kbd_dirty = True  # Release any paste key
                        print(f"[PASTE] Cancelled ({done}/{total})")
                    return 1  # Block all keys during paste

                # Numpad Enter: VK_RETURN + extended → HID 0x58 (Keypad Enter)
                if vk == 0x0D and is_extended:
                    hid_code = 0x58
                    if is_down:
                        state.pressed_keys.add(hid_code)
                    else:
                        state.pressed_keys.discard(hid_code)
                    state.kbd_dirty = True
                elif vk in VK_MODIFIER_MAP:
                    bit = VK_MODIFIER_MAP[vk]
                    if is_down:
                        state.modifiers |= (1 << bit)
                    else:
                        state.modifiers &= ~(1 << bit)
                    state.kbd_dirty = True
                elif vk in VK_TO_CONSUMER:
                    usage = VK_TO_CONSUMER[vk]
                    if is_down:
                        state.consumer_usage = usage
                    else:
                        # Release only if this was the active consumer key
                        if state.consumer_usage == usage:
                            state.consumer_usage = 0
                    state.consumer_dirty = True
                else:
                    hid_code = VK_TO_HID.get(vk)
                    if hid_code is not None:
                        if is_down:
                            state.pressed_keys.add(hid_code)
                        else:
                            state.pressed_keys.discard(hid_code)
                        state.kbd_dirty = True

                # Block keys on Host (don't propagate)
                return 1

    return user32.CallNextHookEx(None, nCode, wParam, lParam)


def _mouse_proc(nCode: int, wParam: int, lParam: int) -> int:
    if nCode >= 0:
        with state.lock:
            if state.kvm_active:
                # Block all mouse events on Host
                return 1

    return user32.CallNextHookEx(None, nCode, wParam, lParam)


# Keep references to callbacks (prevents GC)
keyboard_proc_cb = HOOKPROC(_keyboard_proc)
mouse_proc_cb    = HOOKPROC(_mouse_proc)

# ═══════════════════════════════════════════════════════════════════
#  Sender Thread (fixed polling rate)
# ═══════════════════════════════════════════════════════════════════

def sender_thread(host: str, port: int, rate: int,
                  stop_event: threading.Event):
    """Thread that sends UDP packets to ESP32 at a fixed rate."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (host, port)
    interval = 1.0 / rate

    print(f"[SENDER] Target: {host}:{port} @ {rate}Hz (interval {interval*1000:.1f}ms)")

    while not stop_event.is_set():
        t0 = time.perf_counter()

        with state.lock:
            active = state.kvm_active
            mouse_changed = False

            # ── Keyboard (always - needed for "release all") ──
            kbd_dirty = state.kbd_dirty
            if kbd_dirty:
                modifiers = state.modifiers
                keys_list = list(state.pressed_keys)[:6]
                if len(state.pressed_keys) > 6:
                    keycodes = bytes([0x01] * 6)  # Phantom state
                else:
                    keycodes = bytes(
                        keys_list + [0] * (6 - len(keys_list))
                    )
                state.kbd_dirty = False

            # ── Consumer (multimedia / browser) ──────────────
            con_dirty = state.consumer_dirty
            if con_dirty:
                consumer_usage = state.consumer_usage
                state.consumer_dirty = False

            if active:
                # ── Mouse ────────────────────────────────────────
                dx = state.mouse_dx
                dy = state.mouse_dy
                wheel = state.mouse_wheel
                pan = state.mouse_pan
                buttons = state.mouse_buttons
                buttons_prev = state.mouse_buttons_prev

                # Reset accumulators
                state.mouse_dx = 0
                state.mouse_dy = 0
                state.mouse_wheel = 0
                state.mouse_pan = 0
                state.mouse_buttons_prev = buttons

                mouse_changed = (
                    dx != 0 or dy != 0 or
                    wheel != 0 or pan != 0 or
                    buttons != buttons_prev
                )

                # Clamp to int16/int8 range
                dx = max(-32767, min(32767, dx))
                dy = max(-32767, min(32767, dy))
                wheel = max(-127, min(127, wheel))
                pan = max(-127, min(127, pan))

            # ── Sending ─────────────────────────────────────────
            if active:
                if mouse_changed:
                    seq = state.next_seq()
                    pkt = pack_mouse(seq, buttons, dx, dy, wheel, pan)
                    sock.sendto(pkt, target)

                if kbd_dirty:
                    seq = state.next_seq()
                    pkt = pack_keyboard(seq, modifiers, keycodes)
                    sock.sendto(pkt, target)
                elif state.pasting:
                    # Paste mode: type one phase per sender cycle, with pacing
                    # skip 1 tick (8ms @ 125Hz) between phases to allow USB polling and ESP32 queue processing
                    PASTE_TICK_SKIP = 1

                    if state.paste_tick_counter > 0:
                        state.paste_tick_counter -= 1
                    else:
                        idx = state.paste_index
                        if idx < len(state.paste_chars):
                            hid_code, mods = state.paste_chars[idx]
                            if state.paste_phase == 0:
                                # Key press
                                seq = state.next_seq()
                                kc = bytes([hid_code, 0, 0, 0, 0, 0])
                                pkt = pack_keyboard(seq, mods, kc)
                                sock.sendto(pkt, target)
                                state.paste_phase = 1
                                state.paste_tick_counter = PASTE_TICK_SKIP
                            else:
                                # Key release
                                seq = state.next_seq()
                                pkt = pack_keyboard(seq, 0, bytes(6))
                                sock.sendto(pkt, target)
                                state.paste_phase = 0
                                state.paste_index += 1
                                state.paste_tick_counter = PASTE_TICK_SKIP
                        else:
                            count = len(state.paste_chars)
                            state.pasting = False
                            state.paste_chars = []
                            state.paste_index = 0
                            state.paste_tick_counter = 0
                            print(f"[PASTE] Done ({count} chars)")

                if con_dirty:
                    seq = state.next_seq()
                    pkt = pack_consumer(seq, consumer_usage)
                    sock.sendto(pkt, target)
            elif kbd_dirty or con_dirty:
                # KVM just disabled - send "release all" reports
                if kbd_dirty:
                    seq = state.next_seq()
                    pkt = pack_keyboard(seq, modifiers, keycodes)
                    sock.sendto(pkt, target)
                if con_dirty:
                    seq = state.next_seq()
                    pkt = pack_consumer(seq, consumer_usage)
                    sock.sendto(pkt, target)

        # Precise timing (busy-wait for the last µs)
        elapsed = time.perf_counter() - t0
        remaining = interval - elapsed
        if remaining > 0.001:
            time.sleep(remaining - 0.0005)
        while time.perf_counter() - t0 < interval:
            pass

    sock.close()
    print("[SENDER] Stopped")

# ═══════════════════════════════════════════════════════════════════
#  Raw Input Setup
# ═══════════════════════════════════════════════════════════════════

def create_raw_input_window() -> wintypes.HWND:
    """Creates a hidden message-only window to receive WM_INPUT."""
    hInstance = kernel32.GetModuleHandleW(None)
    class_name = "ESP32_RawInput_Class"

    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.style = 0
    wc.lpfnWndProc = ctypes.cast(wnd_proc_cb, ctypes.c_void_p)
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = hInstance
    wc.hIcon = None
    wc.hCursor = None
    wc.hbrBackground = None
    wc.lpszMenuName = None
    wc.lpszClassName = class_name
    wc.hIconSm = None

    atom = user32.RegisterClassExW(ctypes.byref(wc))
    if not atom:
        raise RuntimeError(f"RegisterClassExW failed: {ctypes.GetLastError()}")

    hwnd = user32.CreateWindowExW(
        0, class_name, "ESP32 Raw Input", 0,
        0, 0, 0, 0,
        HWND_MESSAGE, None, hInstance, None
    )
    if not hwnd:
        raise RuntimeError(f"CreateWindowExW failed: {ctypes.GetLastError()}")

    return hwnd


def register_raw_input(hwnd: wintypes.HWND):
    """Registers Raw Input for mouse on the given window."""
    rid = RAWINPUTDEVICE()
    rid.usUsagePage = 0x01      # Generic Desktop
    rid.usUsage = 0x02          # Mouse
    rid.dwFlags = RIDEV_INPUTSINK  # Receive even when window is not active
    rid.hwndTarget = hwnd

    if not user32.RegisterRawInputDevices(
        ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)
    ):
        raise RuntimeError(
            f"RegisterRawInputDevices failed: {ctypes.GetLastError()}"
        )

# ═══════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="ESP32-S3 KVM Server (KVM via Scroll Lock)"
    )
    parser.add_argument("--host", required=True, help="ESP32 IP address")
    parser.add_argument("--port", type=int, default=UDP_PORT,
                        help=f"UDP port (default: {UDP_PORT})")
    parser.add_argument("--rate", type=int, default=125,
                        help="Polling rate in Hz (default: 125)")
    args = parser.parse_args()

    if not (60 <= args.rate <= 1000):
        print("ERROR: --rate must be between 60 and 1000", file=sys.stderr)
        sys.exit(1)

    stop_event = threading.Event()

    # 1. Hidden window for Raw Input
    print("[INIT] Creating Raw Input window...")
    hwnd = create_raw_input_window()
    register_raw_input(hwnd)
    print("[INIT] Raw Input registered for mouse")

    # 2. Sender thread
    sender = threading.Thread(
        target=sender_thread,
        args=(args.host, args.port, args.rate, stop_event),
        daemon=True,
    )
    sender.start()

    # 3. Install LL hooks
    kbd_hook = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL, keyboard_proc_cb,
        kernel32.GetModuleHandleW(None), 0
    )
    mouse_hook = user32.SetWindowsHookExW(
        WH_MOUSE_LL, mouse_proc_cb,
        kernel32.GetModuleHandleW(None), 0
    )

    if not kbd_hook:
        print(f"ERROR: Failed to install keyboard hook (err={ctypes.GetLastError()})", file=sys.stderr)
        sys.exit(1)
    if not mouse_hook:
        print(f"ERROR: Failed to install mouse hook (err={ctypes.GetLastError()})", file=sys.stderr)
        user32.UnhookWindowsHookEx(kbd_hook)
        sys.exit(1)

    print("[HOOKS] Keyboard LL + Mouse LL hooks installed")
    print("[KVM]   Press Scroll Lock to toggle KVM mode")
    print("[KVM]   OFF (input goes to Host PC)")

    # 4. Windows message loop (handles LL hooks + WM_INPUT)
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        print("\n[MAIN] Shutting down...")

    # 5. Cleanup
    stop_event.set()
    user32.UnhookWindowsHookEx(kbd_hook)
    user32.UnhookWindowsHookEx(mouse_hook)
    user32.DestroyWindow(hwnd)
    sender.join(timeout=2)
    print("[MAIN] Done")


if __name__ == "__main__":
    main()
