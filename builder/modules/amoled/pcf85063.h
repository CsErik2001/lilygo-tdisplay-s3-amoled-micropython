#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

typedef struct {
    uint16_t year;
    uint8_t month;
    uint8_t day;
    uint8_t weekday;
    uint8_t hour;
    uint8_t minute;
    uint8_t second;
} pcf85063_datetime_t;

esp_err_t pcf85063_init(void);
bool pcf85063_is_valid(void);
bool pcf85063_get_datetime(pcf85063_datetime_t *dt);
esp_err_t pcf85063_set_datetime(const pcf85063_datetime_t *dt);
