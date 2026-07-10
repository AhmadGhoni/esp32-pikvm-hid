#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>
#include <stdbool.h>

#define UDP_PORT            4210

#define MCU_PACKET_SIZE     8

#define MCU_MAGIC           0x33

/* ===========================
 * PiKVM MCU Commands
 * =========================== */

enum {

    MCU_CMD_PING          = 0x01,
    MCU_CMD_REPEAT        = 0x02,

    MCU_CMD_SET_KEYBOARD  = 0x03,
    MCU_CMD_SET_MOUSE     = 0x04,
    MCU_CMD_CONNECTED     = 0x05,

    MCU_CMD_CLEAR         = 0x10,

    MCU_CMD_KEYBOARD      = 0x11,
    MCU_CMD_MOUSE_ABS     = 0x12,
    MCU_CMD_MOUSE_BUTTON  = 0x13,
    MCU_CMD_MOUSE_WHEEL   = 0x14,
    MCU_CMD_MOUSE_REL     = 0x15,
};

/* ===========================
 * HID Events
 * =========================== */

typedef enum {

    HID_EVENT_NONE = 0,

    HID_EVENT_CLEAR,

    HID_EVENT_KEYBOARD,

    HID_EVENT_MOUSE_REL,

    HID_EVENT_MOUSE_ABS,

    HID_EVENT_MOUSE_BUTTON,

    HID_EVENT_MOUSE_WHEEL,

} hid_event_type_t;

typedef struct {

    hid_event_type_t type;

    union {

        struct {

            uint8_t mcu_code;

            bool pressed;

        } keyboard;

        struct {

            int16_t x;

            int16_t y;

        } mouse_abs;

        struct {

            int8_t dx;

            int8_t dy;

        } mouse_rel;

        struct {

            uint8_t main;
            uint8_t extra;

        } mouse_button;
        
        struct {

            int8_t wheel;

        } mouse_wheel;

    };

} hid_event_t;

/* ===========================
 * MCU Packet
 * =========================== */

typedef struct {

    uint8_t magic;

    uint8_t command;

    uint8_t data[4];

    uint16_t crc;

} __attribute__((packed)) mcu_packet_t;

_Static_assert(sizeof(mcu_packet_t) == 8, "Invalid MCU packet size");

/* ===========================
 * CRC16
 * =========================== */

uint16_t mcu_crc16(const uint8_t *data, uint32_t len);

#endif