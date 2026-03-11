#ifndef HID_TASK_H
#define HID_TASK_H

/**
 * FreeRTOS task: receives events from the queue and sends HID reports
 * over USB using TinyUSB.
 */
void hid_task(void *pvParameters);

#endif
