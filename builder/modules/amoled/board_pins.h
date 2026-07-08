/*
 * board_pins.h - T-Display-S3 AMOLED Plus (touch) pin mapping.
 *
 * The Plus/touch board is the LilyGO BOARD_AMOLED_191_SPI variant:
 * RM67162 over classic SPI, plus CST816T touch, RTC and PMU on the
 * shared I2C bus. The non-Plus 1.91" touch board is the QSPI variant,
 * which uses GPIO48/GPIO5 as D2/D3. Do not use that mapping here.
 */

#pragma once

// ---- Board power gate ----
#define BOARD_PIN_POWER_EN    38   // LilyGO PMICEnPins; enables AMOLED/touch power

// ---- RM67162 AMOLED display, classic SPI ----
#define AMOLED_PIN_CS         6    // DISP_CS
#define AMOLED_PIN_SCK        47   // DISP_SCK
#define AMOLED_PIN_MOSI       18   // DISP_MOSI
#define AMOLED_PIN_DC         7    // DISP_DC
#define AMOLED_PIN_RESET      17   // DISP_Reset
#define AMOLED_PIN_TE         9    // DISP_TE

#define AMOLED_LCD_WIDTH      240
#define AMOLED_LCD_HEIGHT     536

// ---- Közös I2C busz: Touch + RTC + PMU ----
#define BOARD_I2C_SDA         3    // IO03 - Touch_SDA / RTC_SDA / PMU_SDA
#define BOARD_I2C_SCL         2    // IO02 - Touch_SCL / RTC_SCL / PMU_SCL

// ---- Touch controller ----
#define TOUCH_PIN_INT         21   // Touch_IRQ
#define TOUCH_I2C_ADDR        0x15

// ---- PMU / RTC (közös busz, más címeken - ha később kellenek) ----
#define PMU_PIN_IRQ           1    // PMU_IRQ
#define RTC_PIN_INT           15   // RTC_INT

// ---- SD kártya (SPI, külön busz a kijelzőtől) ----
#define SD_PIN_MISO           13
#define SD_PIN_MOSI           12
#define SD_PIN_SCK            14
#define SD_PIN_CS             11
