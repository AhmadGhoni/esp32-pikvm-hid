#ifndef TUSB_CONFIG_H
#define TUSB_CONFIG_H

// Role: Device
#define CFG_TUSB_RHPORT0_MODE   OPT_MODE_DEVICE

// Endpoint 0 size
#define CFG_TUD_ENDPOINT0_SIZE  64

// Enabled device classes
#define CFG_TUD_HID             1   // 1 instancja HID (composite via Report ID)
#define CFG_TUD_CDC             0
#define CFG_TUD_MSC             0
#define CFG_TUD_MIDI            0
#define CFG_TUD_VENDOR          0

// HID endpoint buffer
#define CFG_TUD_HID_EP_BUFSIZE  16  // >= max(mouse_report+1, kbd_report+1) = 9

#endif
