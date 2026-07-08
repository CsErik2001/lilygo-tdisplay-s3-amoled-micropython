#pragma once
#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"

typedef struct {
    uint16_t x;
    uint16_t y;
    uint8_t  gesture;   // raw GestureID register value
    uint8_t  event;     // 0=down 1=up 2=contact (per CST816 register map)
} cst816_point_t;

esp_err_t cst816_init(void);
void cst816_deinit(void);
uint32_t cst816_scan(uint8_t *out, uint32_t max_addrs);

// true if the INT line indicates a pending touch (edge-triggered, active low
// on CST816). If TOUCH_PIN_INT isn't wired separately from RST on your
// board, this falls back to always returning true and you poll instead.
bool cst816_touched(void);

// Reads raw CST816 registers starting at 0x00. This is useful for board
// bring-up when coordinates are not yet being decoded as expected.
bool cst816_read_raw(uint8_t *buf, uint32_t len);

// True when the separate CST816 "center/home" touch area is pressed. On the
// 1.91-inch AMOLED board this is the round touch target beside the display.
bool cst816_home_pressed(void);

// Reads current finger position. Returns true and fills `out` if a finger
// is on the panel, false if not touched (out is left untouched).
bool cst816_read(cst816_point_t *out);
