#include "network_task.h"
#include "protocol.h"
#include "hid_task.h"
#include "wifi_manager.h"
#include "keymap.h"

#include <errno.h>
#include <string.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/queue.h"
#include "lwip/sockets.h"

#define TAG "NET"

#define RESPONSE_SIZE 4

extern QueueHandle_t hid_event_queue;

static uint8_t response_ok[RESPONSE_SIZE];

static void build_response_ok(void)
{
    response_ok[0] = 0x33;
    response_ok[1] = 0x20;

    uint16_t crc = mcu_crc16(response_ok, 2);

    response_ok[2] = (crc >> 8) & 0xff;
    response_ok[3] = crc & 0xff;
}

static bool packet_valid(const mcu_packet_t *pkt)
{
    if (pkt->magic != MCU_MAGIC)
        return false;

    uint16_t crc =
        ((uint16_t)((uint8_t *)&pkt->crc)[0] << 8) |
         ((uint8_t *)&pkt->crc)[1];

    return crc == mcu_crc16((const uint8_t *)pkt, 6);
}

static int create_socket(void)
{
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);

    if (sock < 0) {
        ESP_LOGE(TAG, "socket() failed");
        return -1;
    }

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_port = htons(UDP_PORT),
        .sin_addr.s_addr = htonl(INADDR_ANY),
    };

    if (bind(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        ESP_LOGE(TAG, "bind() failed");
        close(sock);
        return -1;
    }

    ESP_LOGI(TAG, "Listening UDP %d", UDP_PORT);

    return sock;
}

static void send_ack(
    int sock,
    struct sockaddr_in *from,
    socklen_t fromlen)
{
    sendto(
        sock,
        response_ok,
        sizeof(response_ok),
        0,
        (struct sockaddr *)from,
        fromlen
    );
}

static void queue_event(hid_event_t *event)
{
    xQueueSend(
        hid_event_queue,
        event,
        portMAX_DELAY
    );
}

static void process_packet(const mcu_packet_t *pkt)
{
    hid_event_t event;

    memset(&event, 0, sizeof(event));

    switch (pkt->command) {

    case MCU_CMD_PING:

        return;

    case MCU_CMD_REPEAT:

        return;

    case MCU_CMD_SET_KEYBOARD:

        return;

    case MCU_CMD_SET_MOUSE:

        return;

    case MCU_CMD_CONNECTED:

        return;

    case MCU_CMD_CLEAR:

        event.type = HID_EVENT_CLEAR;
        queue_event(&event);
        return;
    
        case MCU_CMD_KEYBOARD:

        event.type = HID_EVENT_KEYBOARD;

        event.keyboard.mcu_code = pkt->data[0];
        event.keyboard.pressed = pkt->data[1];

        queue_event(&event);

        return;

    case MCU_CMD_MOUSE_REL:

        event.type = HID_EVENT_MOUSE_REL;

        event.mouse_rel.dx = (int8_t)pkt->data[0];
        event.mouse_rel.dy = (int8_t)pkt->data[1];

        queue_event(&event);

        return;

    case MCU_CMD_MOUSE_ABS:

        event.type = HID_EVENT_MOUSE_ABS;

        event.mouse_abs.x =
            (int16_t)(((uint16_t)pkt->data[0] << 8) |
                       pkt->data[1]);

        event.mouse_abs.y =
            (int16_t)(((uint16_t)pkt->data[2] << 8) |
                       pkt->data[3]);

        queue_event(&event);

        return;

    case MCU_CMD_MOUSE_BUTTON:

        event.type = HID_EVENT_MOUSE_BUTTON;

        // Raw PiKVM packet
        event.mouse_button.main = pkt->data[0];
        event.mouse_button.extra = pkt->data[1];

        queue_event(&event);

        return;

    case MCU_CMD_MOUSE_WHEEL:

        event.type = HID_EVENT_MOUSE_WHEEL;

        event.mouse_wheel.wheel = (int8_t)pkt->data[1];

        queue_event(&event);

        return;

    default:

        return;
    }
}

void network_task(void *pvParameters)
{
    (void)pvParameters;

    build_response_ok();

    while (1) {

        xEventGroupWaitBits(
            wifi_event_group,
            WIFI_CONNECTED_BIT,
            pdFALSE,
            pdFALSE,
            portMAX_DELAY
        );

        int sock = create_socket();

        if (sock < 0) {
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }

        while (1) {

            if (!(xEventGroupGetBits(wifi_event_group) &
                  WIFI_CONNECTED_BIT))
                break;

            struct sockaddr_in from;
            socklen_t fromlen = sizeof(from);

            mcu_packet_t pkt;

            int len = recvfrom(
                sock,
                &pkt,
                sizeof(pkt),
                0,
                (struct sockaddr *)&from,
                &fromlen
            );

            if (len != sizeof(pkt))
                continue;
            
                        if (!packet_valid(&pkt))
                continue;

            send_ack(
                sock,
                &from,
                fromlen
            );

            process_packet(&pkt);

        }

        ESP_LOGW(TAG, "WiFi disconnected");

        close(sock);

        vTaskDelay(pdMS_TO_TICKS(500));

    }
}