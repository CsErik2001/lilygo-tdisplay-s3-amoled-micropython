/*
 * pcf85063.c - PCF85063-compatible external RTC at I2C address 0x51.
 */

#include "pcf85063.h"
#include "amoled_i2c.h"

#define PCF85063_ADDR          0x51
#define PCF85063_REG_SECONDS   0x04
#define PCF85063_DATETIME_LEN  7

static uint8_t bcd_to_bin(uint8_t value)
{
    return (uint8_t)(((value >> 4) * 10) + (value & 0x0f));
}

static uint8_t bin_to_bcd(uint8_t value)
{
    return (uint8_t)(((value / 10) << 4) | (value % 10));
}

static bool datetime_valid_range(const pcf85063_datetime_t *dt)
{
    return dt->year >= 2000 && dt->year <= 2099 &&
           dt->month >= 1 && dt->month <= 12 &&
           dt->day >= 1 && dt->day <= 31 &&
           dt->weekday <= 6 &&
           dt->hour <= 23 &&
           dt->minute <= 59 &&
           dt->second <= 59;
}

esp_err_t pcf85063_init(void)
{
    uint8_t seconds;
    esp_err_t err = amoled_i2c_init();
    if (err != ESP_OK) {
        return err;
    }
    return amoled_i2c_read_reg(PCF85063_ADDR, PCF85063_REG_SECONDS, &seconds, 1);
}

bool pcf85063_is_valid(void)
{
    uint8_t seconds;
    if (amoled_i2c_read_reg(PCF85063_ADDR, PCF85063_REG_SECONDS, &seconds, 1) != ESP_OK) {
        return false;
    }
    return (seconds & 0x80) == 0;
}

bool pcf85063_get_datetime(pcf85063_datetime_t *dt)
{
    uint8_t buf[PCF85063_DATETIME_LEN];
    if (dt == NULL ||
        amoled_i2c_read_reg(PCF85063_ADDR, PCF85063_REG_SECONDS, buf, sizeof(buf)) != ESP_OK) {
        return false;
    }

    dt->second = bcd_to_bin(buf[0] & 0x7f);
    dt->minute = bcd_to_bin(buf[1] & 0x7f);
    dt->hour = bcd_to_bin(buf[2] & 0x3f);
    dt->day = bcd_to_bin(buf[3] & 0x3f);
    dt->weekday = buf[4] & 0x07;
    dt->month = bcd_to_bin(buf[5] & 0x1f);
    dt->year = 2000 + bcd_to_bin(buf[6]);
    return true;
}

esp_err_t pcf85063_set_datetime(const pcf85063_datetime_t *dt)
{
    if (dt == NULL || !datetime_valid_range(dt)) {
        return ESP_ERR_INVALID_ARG;
    }

    uint8_t buf[PCF85063_DATETIME_LEN] = {
        bin_to_bcd(dt->second),
        bin_to_bcd(dt->minute),
        bin_to_bcd(dt->hour),
        bin_to_bcd(dt->day),
        (uint8_t)(dt->weekday & 0x07),
        bin_to_bcd(dt->month),
        bin_to_bcd((uint8_t)(dt->year - 2000)),
    };
    return amoled_i2c_write_regs(PCF85063_ADDR, PCF85063_REG_SECONDS, buf, sizeof(buf));
}
