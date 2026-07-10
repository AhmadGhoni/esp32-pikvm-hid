#ifndef HID_TASK_H
#define HID_TASK_H

#include "protocol.h"

void hid_task(void *pvParameters);

/* keyboard */
void hid_press_key(uint8_t keycode);
void hid_release_key(uint8_t keycode);
void hid_release_all(void);

/* mouse */
void hid_mouse_relative(int8_t dx, int8_t dy);
void hid_mouse_absolute(int16_t x, int16_t y);
void hid_mouse_buttons(uint8_t buttons);
void hid_mouse_wheel(int8_t wheel);

#endif