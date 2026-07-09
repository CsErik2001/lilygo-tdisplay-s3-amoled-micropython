#pragma once
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

esp_err_t amoled_i2c_init(void);
void amoled_i2c_deinit(void);

esp_err_t amoled_i2c_read_reg(uint8_t addr, uint8_t reg, uint8_t *buf, size_t len);
esp_err_t amoled_i2c_write_reg(uint8_t addr, uint8_t reg, uint8_t value);
esp_err_t amoled_i2c_write_regs(uint8_t addr, uint8_t reg, const uint8_t *data, size_t len);
uint32_t amoled_i2c_scan(uint8_t *out, uint32_t max_addrs);
