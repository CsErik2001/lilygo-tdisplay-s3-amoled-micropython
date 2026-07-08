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

#include <string.h>
#include "cst816.h"
#include "board_pins.h"
#include "rm67162.h"
#include "driver/i2c.h"
#include "driver/gpio.h"
#include "esp_rom_sys.h"

#define I2C_PORT           I2C_NUM_0
#define I2C_CLK_HZ         (400 * 1000)
#define I2C_TIMEOUT_MS     50

static bool s_installed = false;

static void board_power_on(void)
{
    gpio_config_t io = {
        .pin_bit_mask = (1ULL << BOARD_PIN_POWER_EN),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&io);
    gpio_set_level(BOARD_PIN_POWER_EN, 1);
    esp_rom_delay_us(20 * 1000);
}

static esp_err_t ensure_i2c(void)
{
    if (s_installed) {
        return ESP_OK;
    }

    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = BOARD_I2C_SDA,
        .scl_io_num = BOARD_I2C_SCL,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = I2C_CLK_HZ,
    };
    esp_err_t err = i2c_param_config(I2C_PORT, &conf);
    if (err != ESP_OK) return err;

    err = i2c_driver_install(I2C_PORT, I2C_MODE_MASTER, 0, 0, 0);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) return err;
    s_installed = true;
    return ESP_OK;
}

static esp_err_t reg_read(uint8_t reg, uint8_t *buf, size_t len)
{
    return i2c_master_write_read_device(
        I2C_PORT, TOUCH_I2C_ADDR,
        &reg, 1, buf, len,
        pdMS_TO_TICKS(I2C_TIMEOUT_MS));
}

static esp_err_t reg_write(uint8_t reg, uint8_t value)
{
    uint8_t buf[2] = { reg, value };
    return i2c_master_write_to_device(
        I2C_PORT, TOUCH_I2C_ADDR,
        buf, sizeof(buf),
        pdMS_TO_TICKS(I2C_TIMEOUT_MS));
}

esp_err_t cst816_init(void)
{
    board_power_on();

    esp_err_t err = ensure_i2c();
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
    board_power_on();
    if (ensure_i2c() != ESP_OK) {
        return 0;
    }

    uint32_t count = 0;
    for (uint8_t addr = 1; addr < 0x7f; addr++) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (addr << 1) | I2C_MASTER_WRITE, true);
        i2c_master_stop(cmd);
        esp_err_t err = i2c_master_cmd_begin(I2C_PORT, cmd, pdMS_TO_TICKS(I2C_TIMEOUT_MS));
        i2c_cmd_link_delete(cmd);
        if (err == ESP_OK && count < max_addrs) {
            out[count++] = addr;
        }
    }
    return count;
}

void cst816_deinit(void)
{
    if (s_installed) {
        i2c_driver_delete(I2C_PORT);
        s_installed = false;
    }
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
