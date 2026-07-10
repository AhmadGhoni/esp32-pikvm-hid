#include "hid_task.h"

#include <string.h>

#include "class/hid/hid_device.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "usb_descriptors.h"
#include "keymap.h"

extern QueueHandle_t hid_event_queue;

static keyboard_report_t keyboard_report = {0};

static uint8_t mouse_buttons = 0;

static void wait_ready(void)
{
    while (!tud_hid_ready()) {
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}

void hid_release_all(void)
{
    memset(&keyboard_report, 0, sizeof(keyboard_report));

    mouse_buttons = 0;

    mouse_report_t report = {0};

    wait_ready();

    tud_hid_report(
        REPORT_ID_KEYBOARD,
        &keyboard_report,
        sizeof(keyboard_report)
    );

    wait_ready();

    tud_hid_report(
        REPORT_ID_MOUSE,
        &report,
        sizeof(report)
    );
}

void hid_mouse_relative(int8_t dx, int8_t dy)
{
    mouse_report_t report = {
        .buttons = mouse_buttons,
        .x = dx,
        .y = dy,
    };

    wait_ready();

    tud_hid_report(
        REPORT_ID_MOUSE,
        &report,
        sizeof(report)
    );

    report.x = 0;
    report.y = 0;

    wait_ready();

    tud_hid_report(
        REPORT_ID_MOUSE,
        &report,
        sizeof(report)
    );
}

void hid_mouse_absolute(int16_t x,int16_t y)
{
    /* TODO:
       nanti kita implement absolute mode.
       sementara kita abaikan dulu supaya build sukses.
    */

    (void)x;
    (void)y;
}

void hid_mouse_buttons(uint8_t buttons)
{
    mouse_buttons = buttons;

    mouse_report_t report = {
        .buttons = mouse_buttons,
    };

    wait_ready();

    tud_hid_report(
        REPORT_ID_MOUSE,
        &report,
        sizeof(report)
    );
}

void hid_mouse_wheel(int8_t wheel)
{
    mouse_report_t report = {
        .buttons = mouse_buttons,
        .wheel = wheel,
    };

    wait_ready();

    tud_hid_report(
        REPORT_ID_MOUSE,
        &report,
        sizeof(report)
    );

    report.wheel = 0;

    wait_ready();

    tud_hid_report(
        REPORT_ID_MOUSE,
        &report,
        sizeof(report)
    );
}

void hid_task(void *arg)
{
    (void)arg;

    hid_event_t event;

    while (1) {

        if (xQueueReceive(
                hid_event_queue,
                &event,
                portMAX_DELAY
            ) != pdTRUE)
            continue;

        switch (event.type) {

        case HID_EVENT_CLEAR:

            hid_release_all();

            break;

        case HID_EVENT_KEYBOARD:
        {
            uint8_t mcu = event.keyboard.mcu_code;
            uint8_t hid = mcu_to_hid(mcu);

            if (mcu >= 77 && mcu <= 84) {

                if (event.keyboard.pressed)
                    keyboard_report.modifiers |= hid;
                else
                    keyboard_report.modifiers &= ~hid;

            } else {

                if (event.keyboard.pressed) {

                    bool found = false;

                    for (int i = 0; i < 6; i++) {
                        if (keyboard_report.keycodes[i] == hid) {
                            found = true;
                            break;
                        }
                    }

                    if (!found) {
                        for (int i = 0; i < 6; i++) {
                            if (keyboard_report.keycodes[i] == 0) {
                                keyboard_report.keycodes[i] = hid;
                                break;
                            }
                        }
                    }

                } else {

                    for (int i = 0; i < 6; i++) {
                        if (keyboard_report.keycodes[i] == hid)
                            keyboard_report.keycodes[i] = 0;
                    }
                }
            }

            wait_ready();

            tud_hid_report(
                REPORT_ID_KEYBOARD,
                &keyboard_report,
                sizeof(keyboard_report)
            );

            break;
        }

        case HID_EVENT_MOUSE_REL:

            hid_mouse_relative(
                event.mouse_rel.dx,
                event.mouse_rel.dy
            );

            break;

        case HID_EVENT_MOUSE_BUTTON:
        {
            uint8_t main  = event.mouse_button.main;
            uint8_t extra = event.mouse_button.extra;

            // reset semua bit dulu
            mouse_buttons &= ~(0x01 | 0x02 | 0x04 | 0x08 | 0x10);

            if ((main & 0x80) && (main & 0x08))
                mouse_buttons |= 0x01;

            if ((main & 0x40) && (main & 0x04))
                mouse_buttons |= 0x02;

            if ((main & 0x20) && (main & 0x02))
                mouse_buttons |= 0x04;

            if ((extra & 0x80) && (extra & 0x08))
                mouse_buttons |= 0x08;

            if ((extra & 0x40) && (extra & 0x04))
                mouse_buttons |= 0x10;

            hid_mouse_buttons(mouse_buttons);

            break;
        }

        case HID_EVENT_MOUSE_WHEEL:

            hid_mouse_wheel(
                event.mouse_wheel.wheel
            );

            break;

        case HID_EVENT_MOUSE_ABS:

            hid_mouse_absolute(
                event.mouse_abs.x,
                event.mouse_abs.y
            );

            break;

        default:
            break;
        }
    }
}