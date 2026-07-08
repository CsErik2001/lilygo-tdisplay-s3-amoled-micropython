#pragma once
#include <stdint.h>
#include "esp_err.h"

// Init the RM67162 panel over classic SPI + DC pin. Must be called once
// before any drawing calls.
esp_err_t rm67162_init(void);

// Set MADCTL-based rotation. The default LilyGO orientation is rotation 0:
// 536x240 landscape, matching the CST816 touch coordinate system.
void rm67162_set_rotation(uint8_t r);
uint16_t rm67162_get_width(void);
uint16_t rm67162_get_height(void);

// Set the active drawing window (inclusive coordinates).
void rm67162_set_window(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1);

// Push `len` RGB565 pixels starting at the current window cursor. Call
// rm67162_set_window first.
void rm67162_push_pixels(const uint16_t *data, uint32_t len);

// Convenience: fill a rectangle with a single RGB565 color.
void rm67162_fill_rect(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1, uint16_t color);

void rm67162_draw_pixel(int16_t x, int16_t y, uint16_t color);
void rm67162_draw_line(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t color);
void rm67162_draw_rect(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t color);
void rm67162_draw_text(int16_t x, int16_t y, const char *text, uint16_t color, uint8_t scale, int32_t bg);

// Write Display Brightness Control register (0x00-0xFF).
void rm67162_set_brightness(uint8_t level);

void rm67162_sleep(void);
void rm67162_wake(void);

#define RM67162_WIDTH  536
#define RM67162_HEIGHT 240
