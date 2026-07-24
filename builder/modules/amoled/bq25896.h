#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#define BQ25896_CHARGE_CURRENT_MIN_MA        0
#define BQ25896_CHARGE_CURRENT_MAX_MA        1024
#define BQ25896_CHARGE_CURRENT_STEP_MA       64

#define BQ25896_CHARGE_VOLTAGE_MIN_MV        3840
#define BQ25896_CHARGE_VOLTAGE_MAX_MV        4208
#define BQ25896_CHARGE_VOLTAGE_STEP_MV       16

#define BQ25896_INPUT_CURRENT_MIN_MA         100
#define BQ25896_INPUT_CURRENT_MAX_MA         1500
#define BQ25896_INPUT_CURRENT_STEP_MA        50

#define BQ25896_INPUT_VOLTAGE_MIN_MV         3900
#define BQ25896_INPUT_VOLTAGE_MAX_MV         5500
#define BQ25896_INPUT_VOLTAGE_STEP_MV        100

typedef enum {
    BQ25896_SOURCE_NONE = 0,
    BQ25896_SOURCE_USB_SDP = 1,
    BQ25896_SOURCE_ADAPTER = 2,
    BQ25896_SOURCE_OTG = 7,
} bq25896_source_t;

typedef enum {
    BQ25896_CHARGE_NOT_CHARGING = 0,
    BQ25896_CHARGE_PRECHARGE = 1,
    BQ25896_CHARGE_FAST = 2,
    BQ25896_CHARGE_DONE = 3,
} bq25896_charge_status_t;

typedef struct {
    uint8_t raw_status;
    uint8_t source;
    uint8_t charge_status;
    bool power_good;
    bool vbus_present;
    bool thermal_regulation;
    bool input_voltage_limited;
    bool input_current_limited;
    bool vsys_minimum;
} bq25896_power_status_t;

typedef struct {
    uint8_t raw;
    bool watchdog;
    bool boost;
    uint8_t charge;
    bool battery;
    uint8_t ntc;
} bq25896_faults_t;

esp_err_t bq25896_init(void);

esp_err_t bq25896_get_charging(bool *enabled);
esp_err_t bq25896_set_charging(bool enabled);

esp_err_t bq25896_get_charge_current(uint16_t *milliampere);
esp_err_t bq25896_set_charge_current(uint16_t milliampere);
esp_err_t bq25896_get_charge_voltage(uint16_t *millivolt);
esp_err_t bq25896_set_charge_voltage(uint16_t millivolt);
esp_err_t bq25896_get_input_current_limit(uint16_t *milliampere);
esp_err_t bq25896_set_input_current_limit(uint16_t milliampere);
esp_err_t bq25896_get_input_voltage_limit(uint16_t *millivolt);
esp_err_t bq25896_set_input_voltage_limit(uint16_t millivolt);

esp_err_t bq25896_get_battery_voltage(uint16_t *millivolt);
esp_err_t bq25896_get_bus_voltage(uint16_t *millivolt);
esp_err_t bq25896_get_system_voltage(uint16_t *millivolt);
esp_err_t bq25896_get_measured_charge_current(uint16_t *milliampere);

esp_err_t bq25896_get_charge_status(uint8_t *status);
esp_err_t bq25896_get_power_status(bq25896_power_status_t *status);
esp_err_t bq25896_get_faults(bq25896_faults_t *faults);

const char *bq25896_source_name(uint8_t source);
const char *bq25896_charge_status_name(uint8_t status);
const char *bq25896_charge_fault_name(uint8_t fault);
const char *bq25896_ntc_fault_name(uint8_t fault);
