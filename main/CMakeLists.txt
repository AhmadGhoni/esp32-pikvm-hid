idf_component_register(
    SRCS
        "main.c"
        "usb_descriptors.c"
        "wifi_manager.c"
        "network_task.c"
        "hid_task.c"
        "crc16.c"
        "keymap.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES
        nvs_flash
        esp_wifi
        esp_netif
        esp_event
        lwip
)
