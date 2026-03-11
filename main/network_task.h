#ifndef NETWORK_TASK_H
#define NETWORK_TASK_H

/**
 * FreeRTOS task: listens for UDP packets on port 4210,
 * validates them and pushes HID events to the queue.
 */
void network_task(void *pvParameters);

#endif
