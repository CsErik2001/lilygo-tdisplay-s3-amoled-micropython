/*
 * amoled_i2c.c - shared board I2C bus for touch, RTC and PMU devices.
 */

#include <stdbool.h>
#include <string.h>
#include "amoled_i2c.h"
#include "board_pins.h"
#include "driver/i2c.h"
#include "driver/gpio.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

#define I2C_PORT           I2C_NUM_0
#define I2C_CLK_HZ         (400 * 1000)
#define I2C_TIMEOUT_MS     50

static bool s_installed = false;
static StaticSemaphore_t s_mutex_buffer;
static SemaphoreHandle_t s_mutex = NULL;
static portMUX_TYPE s_mutex_init_lock = portMUX_INITIALIZER_UNLOCKED;

static SemaphoreHandle_t bus_mutex(void)
{
    taskENTER_CRITICAL(&s_mutex_init_lock);
    if (s_mutex == NULL) {
        s_mutex = xSemaphoreCreateMutexStatic(&s_mutex_buffer);
    }
    taskEXIT_CRITICAL(&s_mutex_init_lock);
    return s_mutex;
}

static bool bus_lock(void)
{
    SemaphoreHandle_t mutex = bus_mutex();
    return mutex != NULL && xSemaphoreTake(mutex, portMAX_DELAY) == pdTRUE;
}

static void bus_unlock(void)
{
    xSemaphoreGive(s_mutex);
}

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

static esp_err_t i2c_init_locked(void)
{
    if (s_installed) {
        return ESP_OK;
    }

    board_power_on();
    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = BOARD_I2C_SDA,
        .scl_io_num = BOARD_I2C_SCL,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = I2C_CLK_HZ,
    };
    esp_err_t err = i2c_param_config(I2C_PORT, &conf);
    if (err != ESP_OK) {
        return err;
    }

    err = i2c_driver_install(I2C_PORT, I2C_MODE_MASTER, 0, 0, 0);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }
    s_installed = true;
    return ESP_OK;
}

esp_err_t amoled_i2c_init(void)
{
    if (!bus_lock()) {
        return ESP_ERR_NO_MEM;
    }
    esp_err_t err = i2c_init_locked();
    bus_unlock();
    return err;
}

void amoled_i2c_deinit(void)
{
    if (!bus_lock()) {
        return;
    }
    if (s_installed) {
        i2c_driver_delete(I2C_PORT);
        s_installed = false;
    }
    bus_unlock();
}

esp_err_t amoled_i2c_read_reg(uint8_t addr, uint8_t reg, uint8_t *buf, size_t len)
{
    if (buf == NULL || len == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!bus_lock()) {
        return ESP_ERR_NO_MEM;
    }
    esp_err_t err = i2c_init_locked();
    if (err != ESP_OK) {
        bus_unlock();
        return err;
    }
    err = i2c_master_write_read_device(
        I2C_PORT, addr,
        &reg, 1, buf, len,
        pdMS_TO_TICKS(I2C_TIMEOUT_MS));
    bus_unlock();
    return err;
}

esp_err_t amoled_i2c_write_reg(uint8_t addr, uint8_t reg, uint8_t value)
{
    return amoled_i2c_write_regs(addr, reg, &value, 1);
}

esp_err_t amoled_i2c_write_regs(uint8_t addr, uint8_t reg, const uint8_t *data, size_t len)
{
    uint8_t buf[16];
    if (data == NULL && len != 0) {
        return ESP_ERR_INVALID_ARG;
    }
    if (len + 1 > sizeof(buf)) {
        return ESP_ERR_INVALID_SIZE;
    }

    if (!bus_lock()) {
        return ESP_ERR_NO_MEM;
    }
    esp_err_t err = i2c_init_locked();
    if (err != ESP_OK) {
        bus_unlock();
        return err;
    }

    buf[0] = reg;
    if (len != 0) {
        memcpy(&buf[1], data, len);
    }
    err = i2c_master_write_to_device(
        I2C_PORT, addr,
        buf, len + 1,
        pdMS_TO_TICKS(I2C_TIMEOUT_MS));
    bus_unlock();
    return err;
}

esp_err_t amoled_i2c_update_reg(uint8_t addr, uint8_t reg, uint8_t mask, uint8_t value)
{
    if (!bus_lock()) {
        return ESP_ERR_NO_MEM;
    }
    esp_err_t err = i2c_init_locked();
    if (err != ESP_OK) {
        bus_unlock();
        return err;
    }

    uint8_t current;
    err = i2c_master_write_read_device(
        I2C_PORT, addr,
        &reg, 1, &current, 1,
        pdMS_TO_TICKS(I2C_TIMEOUT_MS));
    if (err == ESP_OK) {
        uint8_t buf[2] = {reg, (uint8_t)((current & ~mask) | (value & mask))};
        err = i2c_master_write_to_device(
            I2C_PORT, addr,
            buf, sizeof(buf),
            pdMS_TO_TICKS(I2C_TIMEOUT_MS));
    }
    bus_unlock();
    return err;
}

uint32_t amoled_i2c_scan(uint8_t *out, uint32_t max_addrs)
{
    if (out == NULL || max_addrs == 0 || !bus_lock()) {
        return 0;
    }
    if (i2c_init_locked() != ESP_OK) {
        bus_unlock();
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
    bus_unlock();
    return count;
}
