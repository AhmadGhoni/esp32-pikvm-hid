#include "protocol.h"

uint16_t mcu_crc16(const uint8_t *data, uint32_t len)
{
    uint16_t crc = 0xFFFF;

    while (len--) {

        crc ^= *data++;

        for (int i = 0; i < 8; i++) {

            if (crc & 1)
                crc = (crc >> 1) ^ 0xA001;
            else
                crc >>= 1;
        }
    }

    return crc;
}