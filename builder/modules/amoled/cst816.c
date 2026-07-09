/*
 * cst816.c — CST816-family capacitive touch driver over I2C.
 *
 * Shares the board's common I2C bus (BOARD_I2C_SDA/SCL) with the PMU and
 * RTC, per LilyGO's pinout diagram for the T-Display-S3 AMOLED Plus.
 * There's no dedicated touch reset line broken out on this board, so the
 * chip is assumed reset via the board's own power-on sequence (PMU rail).
 *
 * Register map used here matches the commonly-published CST816S/CST816T
 * map (e.g. lewisxhe/SensorLib's CST816_Register.pdf, which LilyGO also
 * links from the AMOLED-Series repo for the touch variant):
 *
 *   0x00  GestureID
 *   0x02  FingerNum
 *   0x03  XposH  (bits[3:0]; bits[7:6] = event flag: 00=down 01=up 10=contact)
 *   0x04  XposL
 *   0x05  YposH  (bits[3:0])
 *   0x06  YposL
 *
 * NOTE: if an I2C scan / chip marking on your actual board says something
 * other than CST816, only this register map + TOUCH_I2C_ADDR need to
 * change — the bus setup and MicroPython glue stay the same.
 */

#include "cst816.h"
#include "amoled_i2c.h"
#include "board_pins.h"
#include "rm67162.h"
#include "driver/gpio.h"

static esp_err_t reg_read(uint8_t reg, uint8_t *buf, size_t len)
{
    return amoled_i2c_read_reg(TOUCH_I2C_ADDR, reg, buf, len);
}

static esp_err_t reg_write(uint8_t reg, uint8_t value)
{
    return amoled_i2c_write_reg(TOUCH_I2C_ADDR, reg, value);
}

esp_err_t cst816_init(void)
{
    esp_err_t err = amoled_i2c_init();
    if (err != ESP_OK) return err;

    // INT pin as input; CST816 pulls it low on new touch data.
    gpio_config_t int_io = {
        .pin_bit_mask = (1ULL << TOUCH_PIN_INT),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
    };
    gpio_config(&int_io);

    // Keep CST816 awake while MicroPython polls it.
    reg_write(0xFE, 0x01);

    return ESP_OK;
}

uint32_t cst816_scan(uint8_t *out, uint32_t max_addrs)
{
    return amoled_i2c_scan(out, max_addrs);
}

void cst816_deinit(void)
{
    amoled_i2c_deinit();
}

bool cst816_touched(void)
{
    return gpio_get_level(TOUCH_PIN_INT) == 0;
}

bool cst816_read_raw(uint8_t *buf, uint32_t len)
{
    if (buf == NULL || len == 0) {
        return false;
    }
    return reg_read(0x00, buf, len) == ESP_OK;
}

static bool decode_point(const uint8_t *buf, uint16_t *x, uint16_t *y)
{
    uint8_t finger_num = buf[2] & 0x0F;
    if (finger_num == 0 || finger_num > 1) {
        return false;
    }
    *x = ((uint16_t)(buf[3] & 0x0F) << 8) | buf[4];
    *y = ((uint16_t)(buf[5] & 0x0F) << 8) | buf[6];
    return true;
}

static bool near_u16(uint16_t value, uint16_t target, uint16_t tolerance)
{
    return value >= target - tolerance && value <= target + tolerance;
}

bool cst816_home_pressed(void)
{
    uint8_t buf[7];
    uint16_t x;
    uint16_t y;
    if (reg_read(0x00, buf, sizeof(buf)) != ESP_OK || !decode_point(buf, &x, &y)) {
        return false;
    }

    // LilyGO/SensorLib documents this area as a CST816 center button. Depending
    // on touch firmware, the raw point is reported as either 120,600 or 600,120.
    return (near_u16(x, 120, 24) && near_u16(y, 600, 24)) ||
           (near_u16(x, 600, 24) && near_u16(y, 120, 24));
}

bool cst816_read(cst816_point_t *out)
{
    uint8_t buf[7];
    if (reg_read(0x00, buf, sizeof(buf)) != ESP_OK) {
        return false;
    }
    uint16_t x;
    uint16_t y;
    if (!decode_point(buf, &x, &y)) {
        return false;
    }
    out->gesture = buf[0];
    out->event   = (buf[3] >> 6) & 0x03;
    out->x = x;
    out->y = y;
    if (out->x >= RM67162_WIDTH || out->y >= RM67162_HEIGHT) {
        return false;
    }
    return true;
}
