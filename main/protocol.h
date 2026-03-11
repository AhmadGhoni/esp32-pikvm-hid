#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

#define PACKET_MAGIC   0xCAFE
#define UDP_PORT       4210
#define PACKET_SIZE    16

typedef enum : uint8_t {
    EVENT_TYPE_MOUSE    = 0x01,
    EVENT_TYPE_KEYBOARD = 0x02,
} event_type_t;

// ── Incoming UDP packet from server ──────────────────────────────
typedef struct __attribute__((packed)) {
    uint16_t magic;         // 0xCAFE
    uint32_t sequence;      // Sequence counter
    uint8_t  type;          // event_type_t
    uint8_t  _reserved;     // Padding

    union {
        struct __attribute__((packed)) {
            uint8_t  buttons;   // 5 buttons
            int16_t  dx;        // Delta X
            int16_t  dy;        // Delta Y
            int8_t   wheel;     // Scroll V
            int8_t   pan;       // Scroll H
            uint8_t  _pad;
        } mouse;                // 8 bytes

        struct __attribute__((packed)) {
            uint8_t modifiers;  // Modifiers
            uint8_t reserved;
            uint8_t keycodes[6];// 6-key rollover
        } keyboard;             // 8 bytes
    };
} udp_packet_t;

_Static_assert(sizeof(udp_packet_t) == PACKET_SIZE,
               "Packet must be exactly 16 bytes");

// ── Internal event (passed via xQueue) ─────────────────────────
typedef struct {
    event_type_t type;
    union {
        struct {
            uint8_t buttons;
            int16_t dx;
            int16_t dy;
            int8_t  wheel;
            int8_t  pan;
        } mouse;
        struct {
            uint8_t modifiers;
            uint8_t keycodes[6];
        } keyboard;
    };
} hid_event_t;

#endif
