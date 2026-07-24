/*
 * bq25896.c - TI BQ25896 charger/PMU driver for the AMOLED Plus board.
 */

#include "bq25896.h"
#include "amoled_i2c.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define BQ25896_ADDR                  0x6b

#define REG_INPUT_CURRENT             0x00
#define REG_ADC_CONTROL               0x02
#define REG_POWER_CONTROL             0x03
#define REG_CHARGE_CURRENT            0x04
#define REG_CHARGE_VOLTAGE            0x06
#define REG_STATUS                    0x0b
#define REG_FAULT                     0x0c
#define REG_INPUT_VOLTAGE             0x0d
#define REG_BATTERY_VOLTAGE           0x0e
#define REG_SYSTEM_VOLTAGE            0x0f
#define REG_BUS_VOLTAGE               0x11
#define REG_MEASURED_CHARGE_CURRENT   0x12
#define REG_DPM_STATUS                0x13
#define REG_DEVICE                    0x14

#define ADC_CONV_START                0x80
#define ADC_CONV_RATE                 0x40
#define CHARGE_ENABLE                 0x10
#define FORCE_VINDPM                  0x80

#define ADC_TIMEOUT_MS                1200
#define ADC_POLL_MS                   10
#define ADC_CACHE_MS                  900

static bool s_adc_sample_valid;
static TickType_t s_last_adc_sample;

static esp_err_t read_u8(uint8_t reg, uint8_t *value)
{
    if (value == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    return amoled_i2c_read_reg(BQ25896_ADDR, reg, value, 1);
}

static esp_err_t prepare_adc_sample(void)
{
    TickType_t now = xTaskGetTickCount();
    if (s_adc_sample_valid &&
        now - s_last_adc_sample < pdMS_TO_TICKS(ADC_CACHE_MS)) {
        return ESP_OK;
    }

    uint8_t control;
    esp_err_t err = read_u8(REG_ADC_CONTROL, &control);
    if (err != ESP_OK) {
        return err;
    }

    if ((control & ADC_CONV_RATE) != 0) {
        s_adc_sample_valid = true;
        s_last_adc_sample = now;
        return ESP_OK;
    }

    err = amoled_i2c_update_reg(
        BQ25896_ADDR, REG_ADC_CONTROL,
        ADC_CONV_START | ADC_CONV_RATE, ADC_CONV_START);
    if (err != ESP_OK) {
        return err;
    }

    TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(ADC_TIMEOUT_MS);
    do {
        vTaskDelay(pdMS_TO_TICKS(ADC_POLL_MS));
        err = read_u8(REG_ADC_CONTROL, &control);
        if (err != ESP_OK) {
            return err;
        }
        if ((control & ADC_CONV_START) == 0) {
            s_adc_sample_valid = true;
            s_last_adc_sample = xTaskGetTickCount();
            return ESP_OK;
        }
    } while ((int32_t)(deadline - xTaskGetTickCount()) > 0);

    return ESP_ERR_TIMEOUT;
}

esp_err_t bq25896_init(void)
{
    esp_err_t err = amoled_i2c_init();
    if (err != ESP_OK) {
        return err;
    }

    uint8_t device;
    err = read_u8(REG_DEVICE, &device);
    if (err != ESP_OK) {
        return err;
    }
    if ((device & 0x38) != 0 || (device & 0x03) != 0x02) {
        return ESP_ERR_NOT_FOUND;
    }
    return ESP_OK;
}

esp_err_t bq25896_get_charging(bool *enabled)
{
    if (enabled == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t value;
    esp_err_t err = read_u8(REG_POWER_CONTROL, &value);
    if (err == ESP_OK) {
        *enabled = (value & CHARGE_ENABLE) != 0;
    }
    return err;
}

esp_err_t bq25896_set_charging(bool enabled)
{
    return amoled_i2c_update_reg(
        BQ25896_ADDR, REG_POWER_CONTROL, CHARGE_ENABLE,
        enabled ? CHARGE_ENABLE : 0);
}

esp_err_t bq25896_get_charge_current(uint16_t *milliampere)
{
    if (milliampere == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t value;
    esp_err_t err = read_u8(REG_CHARGE_CURRENT, &value);
    if (err == ESP_OK) {
        uint16_t current = (uint16_t)(value & 0x7f) * BQ25896_CHARGE_CURRENT_STEP_MA;
        *milliampere = current > 3008 ? 3008 : current;
    }
    return err;
}

esp_err_t bq25896_set_charge_current(uint16_t milliampere)
{
    if (milliampere > BQ25896_CHARGE_CURRENT_MAX_MA ||
        milliampere % BQ25896_CHARGE_CURRENT_STEP_MA != 0) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t code = (uint8_t)(milliampere / BQ25896_CHARGE_CURRENT_STEP_MA);
    return amoled_i2c_update_reg(BQ25896_ADDR, REG_CHARGE_CURRENT, 0x7f, code);
}

esp_err_t bq25896_get_charge_voltage(uint16_t *millivolt)
{
    if (millivolt == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t value;
    esp_err_t err = read_u8(REG_CHARGE_VOLTAGE, &value);
    if (err == ESP_OK) {
        uint8_t code = (value >> 2) & 0x3f;
        if (code > 48) {
            code = 48;
        }
        *millivolt = BQ25896_CHARGE_VOLTAGE_MIN_MV +
                     (uint16_t)code * BQ25896_CHARGE_VOLTAGE_STEP_MV;
    }
    return err;
}

esp_err_t bq25896_set_charge_voltage(uint16_t millivolt)
{
    if (millivolt < BQ25896_CHARGE_VOLTAGE_MIN_MV ||
        millivolt > BQ25896_CHARGE_VOLTAGE_MAX_MV ||
        (millivolt - BQ25896_CHARGE_VOLTAGE_MIN_MV) % BQ25896_CHARGE_VOLTAGE_STEP_MV != 0) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t code = (uint8_t)((millivolt - BQ25896_CHARGE_VOLTAGE_MIN_MV) /
                             BQ25896_CHARGE_VOLTAGE_STEP_MV);
    return amoled_i2c_update_reg(
        BQ25896_ADDR, REG_CHARGE_VOLTAGE, 0xfc, (uint8_t)(code << 2));
}

esp_err_t bq25896_get_input_current_limit(uint16_t *milliampere)
{
    if (milliampere == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t value;
    esp_err_t err = read_u8(REG_INPUT_CURRENT, &value);
    if (err == ESP_OK) {
        *milliampere = BQ25896_INPUT_CURRENT_MIN_MA +
                       (uint16_t)(value & 0x3f) * BQ25896_INPUT_CURRENT_STEP_MA;
    }
    return err;
}

esp_err_t bq25896_set_input_current_limit(uint16_t milliampere)
{
    if (milliampere < BQ25896_INPUT_CURRENT_MIN_MA ||
        milliampere > BQ25896_INPUT_CURRENT_MAX_MA ||
        (milliampere - BQ25896_INPUT_CURRENT_MIN_MA) % BQ25896_INPUT_CURRENT_STEP_MA != 0) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t code = (uint8_t)((milliampere - BQ25896_INPUT_CURRENT_MIN_MA) /
                             BQ25896_INPUT_CURRENT_STEP_MA);
    return amoled_i2c_update_reg(BQ25896_ADDR, REG_INPUT_CURRENT, 0x3f, code);
}

esp_err_t bq25896_get_input_voltage_limit(uint16_t *millivolt)
{
    if (millivolt == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t value;
    esp_err_t err = read_u8(REG_INPUT_VOLTAGE, &value);
    if (err == ESP_OK) {
        uint16_t voltage = 2600 + (uint16_t)(value & 0x7f) * BQ25896_INPUT_VOLTAGE_STEP_MV;
        *millivolt = voltage < BQ25896_INPUT_VOLTAGE_MIN_MV ?
                     BQ25896_INPUT_VOLTAGE_MIN_MV : voltage;
    }
    return err;
}

esp_err_t bq25896_set_input_voltage_limit(uint16_t millivolt)
{
    if (millivolt < BQ25896_INPUT_VOLTAGE_MIN_MV ||
        millivolt > BQ25896_INPUT_VOLTAGE_MAX_MV ||
        (millivolt - BQ25896_INPUT_VOLTAGE_MIN_MV) % BQ25896_INPUT_VOLTAGE_STEP_MV != 0) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t code = (uint8_t)((millivolt - 2600) / BQ25896_INPUT_VOLTAGE_STEP_MV);
    return amoled_i2c_update_reg(
        BQ25896_ADDR, REG_INPUT_VOLTAGE, 0xff, (uint8_t)(FORCE_VINDPM | code));
}

static esp_err_t read_adc_voltage(uint8_t reg, uint16_t offset,
                                  uint16_t step, uint16_t *millivolt)
{
    if (millivolt == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    esp_err_t err = prepare_adc_sample();
    if (err != ESP_OK) {
        return err;
    }
    uint8_t value;
    err = read_u8(reg, &value);
    if (err == ESP_OK) {
        uint8_t code = value & 0x7f;
        *millivolt = code == 0 ? 0 : offset + (uint16_t)code * step;
    }
    return err;
}

esp_err_t bq25896_get_battery_voltage(uint16_t *millivolt)
{
    return read_adc_voltage(REG_BATTERY_VOLTAGE, 2304, 20, millivolt);
}

esp_err_t bq25896_get_system_voltage(uint16_t *millivolt)
{
    return read_adc_voltage(REG_SYSTEM_VOLTAGE, 2304, 20, millivolt);
}

esp_err_t bq25896_get_bus_voltage(uint16_t *millivolt)
{
    if (millivolt == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    esp_err_t err = prepare_adc_sample();
    if (err != ESP_OK) {
        return err;
    }
    uint8_t value;
    err = read_u8(REG_BUS_VOLTAGE, &value);
    if (err == ESP_OK) {
        *millivolt = (value & 0x80) == 0 ? 0 :
                     2600 + (uint16_t)(value & 0x7f) * 100;
    }
    return err;
}

esp_err_t bq25896_get_measured_charge_current(uint16_t *milliampere)
{
    if (milliampere == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    esp_err_t err = prepare_adc_sample();
    if (err != ESP_OK) {
        return err;
    }
    uint8_t value;
    err = read_u8(REG_MEASURED_CHARGE_CURRENT, &value);
    if (err == ESP_OK) {
        *milliampere = (uint16_t)(value & 0x7f) * 50;
    }
    return err;
}

esp_err_t bq25896_get_charge_status(uint8_t *status)
{
    if (status == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t value;
    esp_err_t err = read_u8(REG_STATUS, &value);
    if (err == ESP_OK) {
        *status = (value >> 3) & 0x03;
    }
    return err;
}

esp_err_t bq25896_get_power_status(bq25896_power_status_t *status)
{
    if (status == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t main_status;
    uint8_t battery_status;
    uint8_t bus_status;
    uint8_t dpm_status;
    esp_err_t err = read_u8(REG_STATUS, &main_status);
    if (err != ESP_OK) {
        return err;
    }
    err = read_u8(REG_BATTERY_VOLTAGE, &battery_status);
    if (err != ESP_OK) {
        return err;
    }
    err = read_u8(REG_BUS_VOLTAGE, &bus_status);
    if (err != ESP_OK) {
        return err;
    }
    err = read_u8(REG_DPM_STATUS, &dpm_status);
    if (err != ESP_OK) {
        return err;
    }

    status->raw_status = main_status;
    status->source = (main_status >> 5) & 0x07;
    status->charge_status = (main_status >> 3) & 0x03;
    status->power_good = (main_status & 0x04) != 0;
    status->vbus_present = (bus_status & 0x80) != 0;
    status->thermal_regulation = (battery_status & 0x80) != 0;
    status->input_voltage_limited = (dpm_status & 0x80) != 0;
    status->input_current_limited = (dpm_status & 0x40) != 0;
    status->vsys_minimum = (main_status & 0x01) != 0;
    return ESP_OK;
}

esp_err_t bq25896_get_faults(bq25896_faults_t *faults)
{
    if (faults == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    uint8_t value;
    esp_err_t err = read_u8(REG_FAULT, &value);
    if (err == ESP_OK) {
        faults->raw = value;
        faults->watchdog = (value & 0x80) != 0;
        faults->boost = (value & 0x40) != 0;
        faults->charge = (value >> 4) & 0x03;
        faults->battery = (value & 0x08) != 0;
        faults->ntc = value & 0x07;
    }
    return err;
}

const char *bq25896_source_name(uint8_t source)
{
    switch (source) {
        case BQ25896_SOURCE_NONE: return "no_input";
        case BQ25896_SOURCE_USB_SDP: return "usb_host_sdp";
        case BQ25896_SOURCE_ADAPTER: return "adapter";
        case BQ25896_SOURCE_OTG: return "otg";
        default: return "unknown";
    }
}

const char *bq25896_charge_status_name(uint8_t status)
{
    switch (status) {
        case BQ25896_CHARGE_NOT_CHARGING: return "not_charging";
        case BQ25896_CHARGE_PRECHARGE: return "precharge";
        case BQ25896_CHARGE_FAST: return "fast_charging";
        case BQ25896_CHARGE_DONE: return "done";
        default: return "unknown";
    }
}

const char *bq25896_charge_fault_name(uint8_t fault)
{
    switch (fault) {
        case 0: return "normal";
        case 1: return "input";
        case 2: return "thermal_shutdown";
        case 3: return "safety_timer";
        default: return "unknown";
    }
}

const char *bq25896_ntc_fault_name(uint8_t fault)
{
    switch (fault) {
        case 0: return "normal";
        case 2: return "warm";
        case 3: return "cool";
        case 5: return "cold";
        case 6: return "hot";
        default: return "unknown";
    }
}
