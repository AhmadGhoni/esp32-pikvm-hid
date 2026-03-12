#ifndef USB_DESCRIPTORS_H
#define USB_DESCRIPTORS_H

#include <stdint.h>

#define REPORT_ID_MOUSE    1
#define REPORT_ID_KEYBOARD 2
#define REPORT_ID_CONSUMER 3

// USB HID report structures sent to the host
// (without Report ID - TinyUSB adds it automatically)

typedef struct __attribute__((packed)) {
    uint8_t buttons;    // bit0=Left, bit1=Right, bit2=Middle, bit3=Back, bit4=Forward
    int16_t x;          // Relative movement X (-32767 … +32767)
    int16_t y;          // Relative movement Y
    int8_t  wheel;      // Vertical scroll  (-127 … +127)
    int8_t  pan;        // Horizontal scroll (-127 … +127)
} mouse_report_t;       // 7 bytes

_Static_assert(sizeof(mouse_report_t) == 7, "Mouse report must be 7 bytes");

typedef struct __attribute__((packed)) {
    uint8_t modifiers;  // Bitmap: b0=LCtrl b1=LShift b2=LAlt b3=LGUI
                        //         b4=RCtrl b5=RShift b6=RAlt b7=RGUI
    uint8_t reserved;   // Always 0x00
    uint8_t keycodes[6];// Up to 6 simultaneous keys (HID Usage ID)
} keyboard_report_t;    // 8 bytes

_Static_assert(sizeof(keyboard_report_t) == 8, "Keyboard report must be 8 bytes");

typedef struct __attribute__((packed)) {
    uint16_t usage_id;  // Consumer Usage ID (0x0C page), 0 = release
} consumer_report_t;    // 2 bytes

_Static_assert(sizeof(consumer_report_t) == 2, "Consumer report must be 2 bytes");

// USB descriptors (defined in usb_descriptors.c)
#include "tusb.h"
extern tusb_desc_device_t s_device_descriptor;
extern const uint8_t s_configuration_descriptor[];
extern const char *s_string_descriptors[];
extern uint8_t usb_string_descriptor_count;

/**
 * Build string descriptor table and device descriptor indices
 * based on Kconfig. Must be called before tinyusb_driver_install().
 */
void usb_descriptors_init(void);

#endif
