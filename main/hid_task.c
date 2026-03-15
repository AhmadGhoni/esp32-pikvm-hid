#include "hid_task.h"
#include "protocol.h"
#include "usb_descriptors.h"

#include "class/hid/hid_device.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "tinyusb.h"
#include <string.h>


#define TAG "HID"

extern QueueHandle_t hid_event_queue;

static void wait_for_hid_ready(void) {
    while (!tud_hid_ready()) {
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}

void hid_task(void *pvParameters) {
    (void)pvParameters;

    hid_event_t event;

    while (1) {
        if (xQueueReceive(hid_event_queue, &event, portMAX_DELAY) == pdTRUE) {
            wait_for_hid_ready();

            switch (event.type) {
                case EVENT_TYPE_MOUSE: {
                    mouse_report_t report = {
                        .buttons = event.mouse.buttons,
                        .x       = event.mouse.dx,
                        .y       = event.mouse.dy,
                        .wheel   = event.mouse.wheel,
                        .pan     = event.mouse.pan,
                    };
                    tud_hid_report(REPORT_ID_MOUSE, &report, sizeof(report));
                    break;
                }

                case EVENT_TYPE_KEYBOARD: {
                    keyboard_report_t report = {
                        .modifiers = event.keyboard.modifiers,
                        .reserved  = 0x00,
                    };
                    memcpy(report.keycodes, event.keyboard.keycodes, 6);
                    tud_hid_report(REPORT_ID_KEYBOARD, &report, sizeof(report));
                    break;
                }

                case EVENT_TYPE_CONSUMER: {
                    consumer_report_t report = {
                        .usage_id = event.consumer.usage_id,
                    };
                    tud_hid_report(REPORT_ID_CONSUMER, &report, sizeof(report));
                    break;
                }

                default:
                    break;
            }
        }
    }
}
