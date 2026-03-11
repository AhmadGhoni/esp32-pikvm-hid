#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include "esp_err.h"

/**
 * Initializes WiFi in STA mode and connects to the given network.
 * Blocks until an IP address is obtained or retries are exhausted.
 *
 * @return ESP_OK if connected, ESP_FAIL on failure
 */
esp_err_t wifi_manager_init(const char *ssid, const char *password);

#endif
