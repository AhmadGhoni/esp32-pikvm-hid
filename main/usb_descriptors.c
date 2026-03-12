#include "tinyusb.h"
#include "class/hid/hid_device.h"
#include "usb_descriptors.h"

// ═══════════════════════════════════════════════════════════════════
//  HID REPORT DESCRIPTOR - Composite: Mouse (ID=1) + Keyboard (ID=2) + Consumer (ID=3)
// ═══════════════════════════════════════════════════════════════════

static const uint8_t s_hid_report_descriptor[] = {

    // ╔══════════════════════════════════════════════════════════════╗
    // ║                    MOUSE  (Report ID 1)                      ║
    // ║  5 buttons, 16-bit X/Y, 8-bit wheel, 8-bit pan               ║
    // ╚══════════════════════════════════════════════════════════════╝

    HID_USAGE_PAGE ( HID_USAGE_PAGE_DESKTOP      ),
    HID_USAGE      ( HID_USAGE_DESKTOP_MOUSE     ),
    HID_COLLECTION ( HID_COLLECTION_APPLICATION   ),
      HID_REPORT_ID( REPORT_ID_MOUSE              )

      HID_USAGE      ( HID_USAGE_DESKTOP_POINTER  ),
      HID_COLLECTION ( HID_COLLECTION_PHYSICAL     ),

        // ── 5 mouse buttons ────────────────────────────────────────
        HID_USAGE_PAGE  ( HID_USAGE_PAGE_BUTTON    ),
        HID_USAGE_MIN   ( 1                         ),
        HID_USAGE_MAX   ( 5                         ),
        HID_LOGICAL_MIN ( 0                         ),
        HID_LOGICAL_MAX ( 1                         ),
        HID_REPORT_COUNT( 5                         ),
        HID_REPORT_SIZE ( 1                         ),
        HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ),

        // ── 3 padding bits to complete a byte ─────────────────────
        HID_REPORT_COUNT( 1                         ),
        HID_REPORT_SIZE ( 3                         ),
        HID_INPUT       ( HID_CONSTANT              ),

        // ── X, Y: 16-bit relative movement ───────────────────────
        HID_USAGE_PAGE  ( HID_USAGE_PAGE_DESKTOP    ),
        HID_USAGE       ( HID_USAGE_DESKTOP_X       ),
        HID_USAGE       ( HID_USAGE_DESKTOP_Y       ),
        HID_LOGICAL_MIN_N( -32767, 2                ),
        HID_LOGICAL_MAX_N(  32767, 2                ),
        HID_REPORT_SIZE ( 16                         ),
        HID_REPORT_COUNT( 2                          ),
        HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_RELATIVE ),

        // ── Scroll pionowy (wheel): 8-bit ───────────────────────
        HID_USAGE       ( HID_USAGE_DESKTOP_WHEEL   ),
        HID_LOGICAL_MIN ( -127                       ),
        HID_LOGICAL_MAX (  127                       ),
        HID_REPORT_SIZE ( 8                          ),
        HID_REPORT_COUNT( 1                          ),
        HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_RELATIVE ),

        // ── Scroll poziomy (AC Pan): 8-bit ──────────────────────
        HID_USAGE_PAGE  ( HID_USAGE_PAGE_CONSUMER            ),
        HID_USAGE_N     ( HID_USAGE_CONSUMER_AC_PAN, 2       ),
        HID_LOGICAL_MIN ( -127                                ),
        HID_LOGICAL_MAX (  127                                ),
        HID_REPORT_SIZE ( 8                                   ),
        HID_REPORT_COUNT( 1                                   ),
        HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_RELATIVE ),

      HID_COLLECTION_END,
    HID_COLLECTION_END,

    // ╔══════════════════════════════════════════════════════════════╗
    // ║                 KEYBOARD  (Report ID 2)                      ║
    // ║  8 modifiers, 6-key rollover, 5 LEDs                         ║
    // ╚══════════════════════════════════════════════════════════════╝

    HID_USAGE_PAGE ( HID_USAGE_PAGE_DESKTOP       ),
    HID_USAGE      ( HID_USAGE_DESKTOP_KEYBOARD   ),
    HID_COLLECTION ( HID_COLLECTION_APPLICATION    ),
      HID_REPORT_ID( REPORT_ID_KEYBOARD            )

      // ── 8 modifier bits (Ctrl/Shift/Alt/GUI × L+R) ───────
      HID_USAGE_PAGE  ( HID_USAGE_PAGE_KEYBOARD    ),
      HID_USAGE_MIN   ( 0xE0                       ),
      HID_USAGE_MAX   ( 0xE7                       ),
      HID_LOGICAL_MIN ( 0                           ),
      HID_LOGICAL_MAX ( 1                           ),
      HID_REPORT_SIZE ( 1                           ),
      HID_REPORT_COUNT( 8                           ),
      HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ),

      // ── 1 reserved byte (required by spec) ────────────────────
      HID_REPORT_SIZE ( 8                           ),
      HID_REPORT_COUNT( 1                           ),
      HID_INPUT       ( HID_CONSTANT                ),

      // ── 5 LEDs (Num/Caps/Scroll Lock etc.) - OUTPUT from host ──
      HID_USAGE_PAGE  ( HID_USAGE_PAGE_LED          ),
      HID_USAGE_MIN   ( 1                           ),
      HID_USAGE_MAX   ( 5                           ),
      HID_REPORT_SIZE ( 1                           ),
      HID_REPORT_COUNT( 5                           ),
      HID_OUTPUT      ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ),

      // ── 3 padding bits for LEDs ────────────────────────────
      HID_REPORT_SIZE ( 3                           ),
      HID_REPORT_COUNT( 1                           ),
      HID_OUTPUT      ( HID_CONSTANT                ),

      // ── 6 keycodes (6-key rollover) ───────────────────────────
      HID_USAGE_PAGE  ( HID_USAGE_PAGE_KEYBOARD     ),
      HID_USAGE_MIN   ( 0                           ),
      HID_USAGE_MAX_N ( 0xFF, 2                     ),
      HID_LOGICAL_MIN ( 0                           ),
      HID_LOGICAL_MAX_N( 0x00FF, 2                  ),
      HID_REPORT_SIZE ( 8                           ),
      HID_REPORT_COUNT( 6                           ),
      HID_INPUT       ( HID_DATA | HID_ARRAY        ),

    HID_COLLECTION_END,

    // ╔══════════════════════════════════════════════════════════════╗
    // ║              CONSUMER CONTROL  (Report ID 3)                 ║
    // ║  1× 16-bit Usage ID (media, browser, etc.)                   ║
    // ╚══════════════════════════════════════════════════════════════╝

    TUD_HID_REPORT_DESC_CONSUMER( HID_REPORT_ID(REPORT_ID_CONSUMER) ),
};

// ═══════════════════════════════════════════════════════════════════
//  DEVICE DESCRIPTOR
// ═══════════════════════════════════════════════════════════════════

tusb_desc_device_t s_device_descriptor = {
    .bLength            = sizeof(tusb_desc_device_t),
    .bDescriptorType    = TUSB_DESC_DEVICE,
    .bcdUSB             = 0x0200,
    .bDeviceClass       = 0x00,
    .bDeviceSubClass    = 0x00,
    .bDeviceProtocol    = 0x00,
    .bMaxPacketSize0    = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor           = CONFIG_USB_DESC_VID,
    .idProduct          = CONFIG_USB_DESC_PID,
    .bcdDevice          = 0x0100,
    .iManufacturer      = 0,
    .iProduct           = 0,
    .iSerialNumber      = 0,
    .bNumConfigurations = 1,
};

// ═══════════════════════════════════════════════════════════════════
//  CONFIGURATION DESCRIPTOR
// ═══════════════════════════════════════════════════════════════════

#define EPNUM_HID        0x81
#define HID_EP_SIZE      16
#define HID_POLL_INTERVAL 1

#define CONFIG_TOTAL_LEN  (TUD_CONFIG_DESC_LEN + TUD_HID_DESC_LEN)

const uint8_t s_configuration_descriptor[] = {
    TUD_CONFIG_DESCRIPTOR(1, 1, 0, CONFIG_TOTAL_LEN,
                          TUSB_DESC_CONFIG_ATT_REMOTE_WAKEUP, 100),

    TUD_HID_DESCRIPTOR(0, 0, HID_ITF_PROTOCOL_NONE,
                       sizeof(s_hid_report_descriptor),
                       EPNUM_HID, HID_EP_SIZE, HID_POLL_INTERVAL),
};

// ═══════════════════════════════════════════════════════════════════
//  STRING DESCRIPTORS
// ═══════════════════════════════════════════════════════════════════

const char *s_string_descriptors[4];
uint8_t usb_string_descriptor_count;

void usb_descriptors_init(void)
{
    uint8_t idx = 1;
    s_string_descriptors[0] = "\x09\x04"; // Language: English (US)

    if (CONFIG_USB_DESC_MANUFACTURER[0] != '\0') {
        s_string_descriptors[idx] = CONFIG_USB_DESC_MANUFACTURER;
        s_device_descriptor.iManufacturer = idx++;
    }
    if (CONFIG_USB_DESC_PRODUCT[0] != '\0') {
        s_string_descriptors[idx] = CONFIG_USB_DESC_PRODUCT;
        s_device_descriptor.iProduct = idx++;
    }
    if (CONFIG_USB_DESC_SERIAL[0] != '\0') {
        s_string_descriptors[idx] = CONFIG_USB_DESC_SERIAL;
        s_device_descriptor.iSerialNumber = idx++;
    }

    usb_string_descriptor_count = idx;
}

// ═══════════════════════════════════════════════════════════════════
//  TINYUSB CALLBACKS
// ═══════════════════════════════════════════════════════════════════

uint8_t const *tud_hid_descriptor_report_cb(uint8_t instance) {
    (void)instance;
    return s_hid_report_descriptor;
}

uint16_t tud_hid_get_report_cb(uint8_t instance, uint8_t report_id,
                                hid_report_type_t report_type,
                                uint8_t *buffer, uint16_t reqlen) {
    (void)instance; (void)report_id; (void)report_type;
    (void)buffer;   (void)reqlen;
    return 0;
}

void tud_hid_set_report_cb(uint8_t instance, uint8_t report_id,
                            hid_report_type_t report_type,
                            uint8_t const *buffer, uint16_t bufsize) {
    (void)instance;
    if (report_id == REPORT_ID_KEYBOARD && report_type == HID_REPORT_TYPE_OUTPUT) {
        if (bufsize >= 1) {
            uint8_t leds = buffer[0];
            // leds: bit0=NumLock, bit1=CapsLock, bit2=ScrollLock
            // TODO: Could send UDP back to server or light up an LED on the board
            (void)leds;
        }
    }
}
