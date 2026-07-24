#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

// Init the RM67162 panel over classic SPI + DC pin. Must be called once
// before any drawing calls.
esp_err_t rm67162_init(void);

// Set MADCTL-based rotation. The default LilyGO orientation is rotation 0:
// 536x240 landscape, matching the CST816 touch coordinate system.
void rm67162_set_rotation(uint8_t r);
uint8_t rm67162_get_rotation(void);
uint16_t rm67162_get_width(void);
uint16_t rm67162_get_height(void);

// Set the active drawing window (inclusive coordinates).
void rm67162_set_window(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1);

// Push `len` RGB565 pixels starting at the current window cursor. Call
// rm67162_set_window first.
void rm67162_push_pixels(const uint16_t *data, uint32_t len);

// Optional RGB565 shadow framebuffer. The backing allocation lives in PSRAM
// and stores pixels in the panel's physical 536x240 coordinate space so its
// contents remain valid when MADCTL rotation changes. Captures are exported
// in the current logical orientation as native-endian (little-endian on
// ESP32-S3) RGB565 pixels.
esp_err_t rm67162_framebuffer_enable(bool enable);
bool rm67162_framebuffer_enabled(void);
size_t rm67162_framebuffer_size(void);
esp_err_t rm67162_capture(void *dest, size_t len);
esp_err_t rm67162_capture_row(uint16_t y, uint16_t *dest, size_t pixels);

// Convenience: fill a rectangle with a single RGB565 color. Coordinates are
// clipped to the visible display; fully off-screen rectangles are ignored.
void rm67162_fill_rect(int32_t x0, int32_t y0, int32_t x1, int32_t y1, uint16_t color);

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
