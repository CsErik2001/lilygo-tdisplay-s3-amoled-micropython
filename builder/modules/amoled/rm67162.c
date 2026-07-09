/*
 * rm67162.c - RM67162 AMOLED panel driver for the LilyGO
 * T-Display-S3 AMOLED Plus touch board.
 *
 * This board is LilyGO's BOARD_AMOLED_191_SPI variant. It uses classic
 * SPI with a DC pin, not the QSPI path used by the older 1.91" touch
 * board. The init sequence and power-enable pin are copied from the
 * official LilyGo-AMOLED-Series RM67162_AMOLED_SPI configuration.
 */

#include <stdbool.h>
#include <string.h>
#include "rm67162.h"
#include "board_pins.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_rom_sys.h"

#define SPI_HOST_USED       SPI3_HOST
#define SPI_FREQUENCY_HZ    (40 * 1000 * 1000)
#define SEND_BUF_PIXELS     (4096)
#define DEFAULT_BRIGHTNESS  0xD0
#define MADCTL_MY           0x80
#define MADCTL_MX           0x40
#define MADCTL_MV           0x20
#define MADCTL_RGB          0x00

static spi_device_handle_t s_spi;
static bool s_initialized;
static uint8_t s_rotation;
static uint8_t s_madctl = MADCTL_MX | MADCTL_MV | MADCTL_RGB;
static uint16_t s_width = RM67162_WIDTH;
static uint16_t s_height = RM67162_HEIGHT;
static uint16_t s_txbuf[SEND_BUF_PIXELS];

typedef struct {
    uint8_t cmd;
    uint8_t data[4];
    uint8_t len;   // bit7 = wait 120ms, bit5 = wait 10ms
} lcd_cmd_t;

static const lcd_cmd_t k_init_seq[] = {
    {0xFE, {0x04}, 0x01},
    {0x6A, {0x00}, 0x01},
    {0xFE, {0x05}, 0x01},
    {0xFE, {0x07}, 0x01},
    {0x07, {0x4F}, 0x01},
    {0xFE, {0x01}, 0x01},
    {0x2A, {0x02}, 0x01},
    {0x2B, {0x73}, 0x01},
    {0xFE, {0x0A}, 0x01},
    {0x29, {0x10}, 0x01},
    {0xFE, {0x00}, 0x01},
    {0x51, {DEFAULT_BRIGHTNESS}, 0x01},
    {0x53, {0x20}, 0x01},
    {0x35, {0x00}, 0x01},
    {0x3A, {0x75}, 0x01},
    {0xC4, {0x80}, 0x01},
    {0x11, {0x00}, 0x81},
    {0x29, {0x00}, 0x81},
};

static inline void cs_low(void)  { gpio_set_level(AMOLED_PIN_CS, 0); }
static inline void cs_high(void) { gpio_set_level(AMOLED_PIN_CS, 1); }
static inline void dc_cmd(void)  { gpio_set_level(AMOLED_PIN_DC, 0); }
static inline void dc_data(void) { gpio_set_level(AMOLED_PIN_DC, 1); }

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

static esp_err_t spi_write(const void *data, size_t len)
{
    if (len == 0) {
        return ESP_OK;
    }

    spi_transaction_t t;
    memset(&t, 0, sizeof(t));
    t.tx_buffer = data;
    t.length = len * 8;
    return spi_device_polling_transmit(s_spi, &t);
}

static inline uint16_t swap16(uint16_t value)
{
    return (uint16_t)((value << 8) | (value >> 8));
}

static esp_err_t reg_write(uint8_t cmd, const uint8_t *data, size_t len)
{
    esp_err_t err;

    cs_low();
    dc_cmd();
    err = spi_write(&cmd, 1);
    cs_high();
    if (err != ESP_OK) {
        return err;
    }

    if (len != 0) {
        cs_low();
        dc_data();
        err = spi_write(data, len);
        cs_high();
    }

    return err;
}

esp_err_t rm67162_init(void)
{
    if (s_initialized) {
        return ESP_OK;
    }

    board_power_on();

    gpio_config_t io = {
        .pin_bit_mask = (1ULL << AMOLED_PIN_CS) |
                        (1ULL << AMOLED_PIN_DC) |
                        (1ULL << AMOLED_PIN_RESET),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&io);
    gpio_set_level(AMOLED_PIN_CS, 1);
    gpio_set_level(AMOLED_PIN_DC, 1);

    gpio_config_t te_io = {
        .pin_bit_mask = (1ULL << AMOLED_PIN_TE),
        .mode = GPIO_MODE_INPUT,
    };
    gpio_config(&te_io);

    gpio_set_level(AMOLED_PIN_RESET, 1);
    esp_rom_delay_us(200 * 1000);
    gpio_set_level(AMOLED_PIN_RESET, 0);
    esp_rom_delay_us(300 * 1000);
    gpio_set_level(AMOLED_PIN_RESET, 1);
    esp_rom_delay_us(200 * 1000);

    spi_bus_config_t buscfg = {
        .mosi_io_num = AMOLED_PIN_MOSI,
        .miso_io_num = -1,
        .sclk_io_num = AMOLED_PIN_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = (SEND_BUF_PIXELS * 2) + 16,
        .flags = SPICOMMON_BUSFLAG_MASTER | SPICOMMON_BUSFLAG_GPIO_PINS,
    };
    esp_err_t err = spi_bus_initialize(SPI_HOST_USED, &buscfg, SPI_DMA_CH_AUTO);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }

    spi_device_interface_config_t devcfg = {
        .mode = 0,
        .clock_speed_hz = SPI_FREQUENCY_HZ,
        .spics_io_num = -1,
        .flags = SPI_DEVICE_HALFDUPLEX,
        .queue_size = 4,
    };
    err = spi_bus_add_device(SPI_HOST_USED, &devcfg, &s_spi);
    if (err != ESP_OK) {
        return err;
    }

    for (int retry = 0; retry < 2; retry++) {
        for (int i = 0; i < (int)(sizeof(k_init_seq) / sizeof(k_init_seq[0])); i++) {
            const lcd_cmd_t *c = &k_init_seq[i];
            err = reg_write(c->cmd, c->data, c->len & 0x1f);
            if (err != ESP_OK) {
                return err;
            }
            if (c->len & 0x80) {
                esp_rom_delay_us(120 * 1000);
            }
            if (c->len & 0x20) {
                esp_rom_delay_us(10 * 1000);
            }
        }
    }

    rm67162_set_rotation(0);

    s_initialized = true;
    return ESP_OK;
}

void rm67162_set_rotation(uint8_t r)
{
    if (r > 2) {
        return;
    }
    s_rotation = r;
    switch (s_rotation) {
        case 0:
            s_madctl = MADCTL_MX | MADCTL_MV | MADCTL_RGB;
            s_width = RM67162_WIDTH;
            s_height = RM67162_HEIGHT;
            break;
        case 1:
            s_madctl = MADCTL_RGB;
            s_width = RM67162_HEIGHT;
            s_height = RM67162_WIDTH;
            break;
        case 2:
            s_madctl = MADCTL_MV | MADCTL_MY | MADCTL_RGB;
            s_width = RM67162_WIDTH;
            s_height = RM67162_HEIGHT;
            break;
    }
    reg_write(0x36, &s_madctl, 1);
}

uint8_t rm67162_get_rotation(void)
{
    return s_rotation;
}

uint16_t rm67162_get_width(void)
{
    return s_width;
}

uint16_t rm67162_get_height(void)
{
    return s_height;
}

void rm67162_set_window(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1)
{
    uint8_t col[4] = { (uint8_t)(x0 >> 8), (uint8_t)x0, (uint8_t)(x1 >> 8), (uint8_t)x1 };
    uint8_t row[4] = { (uint8_t)(y0 >> 8), (uint8_t)y0, (uint8_t)(y1 >> 8), (uint8_t)y1 };
    reg_write(0x2A, col, 4);
    reg_write(0x2B, row, 4);
    reg_write(0x2C, NULL, 0);
}

void rm67162_push_pixels(const uint16_t *data, uint32_t len)
{
    const uint16_t *p = data;

    cs_low();
    dc_data();
    while (len > 0) {
        size_t chunk = len > SEND_BUF_PIXELS ? SEND_BUF_PIXELS : len;
        for (size_t i = 0; i < chunk; i++) {
            s_txbuf[i] = swap16(p[i]);
        }
        spi_write(s_txbuf, chunk * sizeof(uint16_t));
        len -= chunk;
        p += chunk;
    }
    cs_high();
}

void rm67162_fill_rect(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1, uint16_t color)
{
    uint16_t buf[SEND_BUF_PIXELS];
    uint32_t total = (uint32_t)(x1 - x0 + 1) * (y1 - y0 + 1);
    uint32_t chunk = total < SEND_BUF_PIXELS ? total : SEND_BUF_PIXELS;
    for (uint32_t i = 0; i < chunk; i++) {
        buf[i] = color;
    }
    rm67162_set_window(x0, y0, x1, y1);
    uint32_t remaining = total;
    while (remaining > 0) {
        uint32_t n = remaining < SEND_BUF_PIXELS ? remaining : SEND_BUF_PIXELS;
        rm67162_push_pixels(buf, n);
        remaining -= n;
    }
}

static const uint8_t font5x7_basic[64][5] = {
    {0x00,0x00,0x00,0x00,0x00}, // space
    {0x00,0x00,0x5f,0x00,0x00}, // !
    {0x00,0x07,0x00,0x07,0x00}, // "
    {0x14,0x7f,0x14,0x7f,0x14}, // #
    {0x24,0x2a,0x7f,0x2a,0x12}, // $
    {0x23,0x13,0x08,0x64,0x62}, // %
    {0x36,0x49,0x55,0x22,0x50}, // &
    {0x00,0x05,0x03,0x00,0x00}, // '
    {0x00,0x1c,0x22,0x41,0x00}, // (
    {0x00,0x41,0x22,0x1c,0x00}, // )
    {0x14,0x08,0x3e,0x08,0x14}, // *
    {0x08,0x08,0x3e,0x08,0x08}, // +
    {0x00,0x50,0x30,0x00,0x00}, // ,
    {0x08,0x08,0x08,0x08,0x08}, // -
    {0x00,0x60,0x60,0x00,0x00}, // .
    {0x20,0x10,0x08,0x04,0x02}, // /
    {0x3e,0x51,0x49,0x45,0x3e}, // 0
    {0x00,0x42,0x7f,0x40,0x00}, // 1
    {0x42,0x61,0x51,0x49,0x46}, // 2
    {0x21,0x41,0x45,0x4b,0x31}, // 3
    {0x18,0x14,0x12,0x7f,0x10}, // 4
    {0x27,0x45,0x45,0x45,0x39}, // 5
    {0x3c,0x4a,0x49,0x49,0x30}, // 6
    {0x01,0x71,0x09,0x05,0x03}, // 7
    {0x36,0x49,0x49,0x49,0x36}, // 8
    {0x06,0x49,0x49,0x29,0x1e}, // 9
    {0x00,0x36,0x36,0x00,0x00}, // :
    {0x00,0x56,0x36,0x00,0x00}, // ;
    {0x08,0x14,0x22,0x41,0x00}, // <
    {0x14,0x14,0x14,0x14,0x14}, // =
    {0x00,0x41,0x22,0x14,0x08}, // >
    {0x02,0x01,0x51,0x09,0x06}, // ?
    {0x32,0x49,0x79,0x41,0x3e}, // @
    {0x7e,0x11,0x11,0x11,0x7e}, // A
    {0x7f,0x49,0x49,0x49,0x36}, // B
    {0x3e,0x41,0x41,0x41,0x22}, // C
    {0x7f,0x41,0x41,0x22,0x1c}, // D
    {0x7f,0x49,0x49,0x49,0x41}, // E
    {0x7f,0x09,0x09,0x09,0x01}, // F
    {0x3e,0x41,0x49,0x49,0x7a}, // G
    {0x7f,0x08,0x08,0x08,0x7f}, // H
    {0x00,0x41,0x7f,0x41,0x00}, // I
    {0x20,0x40,0x41,0x3f,0x01}, // J
    {0x7f,0x08,0x14,0x22,0x41}, // K
    {0x7f,0x40,0x40,0x40,0x40}, // L
    {0x7f,0x02,0x0c,0x02,0x7f}, // M
    {0x7f,0x04,0x08,0x10,0x7f}, // N
    {0x3e,0x41,0x41,0x41,0x3e}, // O
    {0x7f,0x09,0x09,0x09,0x06}, // P
    {0x3e,0x41,0x51,0x21,0x5e}, // Q
    {0x7f,0x09,0x19,0x29,0x46}, // R
    {0x46,0x49,0x49,0x49,0x31}, // S
    {0x01,0x01,0x7f,0x01,0x01}, // T
    {0x3f,0x40,0x40,0x40,0x3f}, // U
    {0x1f,0x20,0x40,0x20,0x1f}, // V
    {0x3f,0x40,0x38,0x40,0x3f}, // W
    {0x63,0x14,0x08,0x14,0x63}, // X
    {0x07,0x08,0x70,0x08,0x07}, // Y
    {0x61,0x51,0x49,0x45,0x43}, // Z
    {0x00,0x7f,0x41,0x41,0x00}, // [
    {0x02,0x04,0x08,0x10,0x20}, // backslash
    {0x00,0x41,0x41,0x7f,0x00}, // ]
    {0x04,0x02,0x01,0x02,0x04}, // ^
    {0x40,0x40,0x40,0x40,0x40}, // _
};

static inline bool in_bounds(int16_t x, int16_t y)
{
    return x >= 0 && y >= 0 && x < s_width && y < s_height;
}

void rm67162_draw_pixel(int16_t x, int16_t y, uint16_t color)
{
    if (!in_bounds(x, y)) {
        return;
    }
    rm67162_fill_rect((uint16_t)x, (uint16_t)y, (uint16_t)x, (uint16_t)y, color);
}

void rm67162_draw_line(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t color)
{
    int16_t dx = x1 > x0 ? x1 - x0 : x0 - x1;
    int16_t sx = x0 < x1 ? 1 : -1;
    int16_t dy = y1 > y0 ? y0 - y1 : y1 - y0;
    int16_t sy = y0 < y1 ? 1 : -1;
    int16_t err = dx + dy;

    while (true) {
        rm67162_draw_pixel(x0, y0, color);
        if (x0 == x1 && y0 == y1) {
            break;
        }
        int16_t e2 = 2 * err;
        if (e2 >= dy) {
            err += dy;
            x0 += sx;
        }
        if (e2 <= dx) {
            err += dx;
            y0 += sy;
        }
    }
}

void rm67162_draw_rect(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t color)
{
    if (x1 < x0) {
        int16_t t = x0;
        x0 = x1;
        x1 = t;
    }
    if (y1 < y0) {
        int16_t t = y0;
        y0 = y1;
        y1 = t;
    }
    rm67162_draw_line(x0, y0, x1, y0, color);
    rm67162_draw_line(x1, y0, x1, y1, color);
    rm67162_draw_line(x1, y1, x0, y1, color);
    rm67162_draw_line(x0, y1, x0, y0, color);
}

static void draw_scaled_pixel(int16_t x, int16_t y, uint8_t scale, uint16_t color)
{
    if (scale <= 1) {
        rm67162_draw_pixel(x, y, color);
        return;
    }
    int16_t x1 = x + scale - 1;
    int16_t y1 = y + scale - 1;
    if (x1 < 0 || y1 < 0 || x >= s_width || y >= s_height) {
        return;
    }
    if (x < 0) {
        x = 0;
    }
    if (y < 0) {
        y = 0;
    }
    if (x1 >= s_width) {
        x1 = s_width - 1;
    }
    if (y1 >= s_height) {
        y1 = s_height - 1;
    }
    rm67162_fill_rect((uint16_t)x, (uint16_t)y, (uint16_t)x1, (uint16_t)y1, color);
}

static void draw_char(int16_t x, int16_t y, char ch, uint16_t color, uint8_t scale, int32_t bg)
{
    if (ch >= 'a' && ch <= 'z') {
        ch = (char)(ch - 32);
    }
    if (ch < 32 || ch > 95) {
        ch = '?';
    }

    if (bg >= 0) {
        int16_t x1 = x + (6 * scale) - 1;
        int16_t y1 = y + (8 * scale) - 1;
        if (!(x1 < 0 || y1 < 0 || x >= s_width || y >= s_height)) {
            int16_t bx0 = x < 0 ? 0 : x;
            int16_t by0 = y < 0 ? 0 : y;
            int16_t bx1 = x1 >= s_width ? s_width - 1 : x1;
            int16_t by1 = y1 >= s_height ? s_height - 1 : y1;
            rm67162_fill_rect((uint16_t)bx0, (uint16_t)by0, (uint16_t)bx1, (uint16_t)by1, (uint16_t)bg);
        }
    }

    const uint8_t *glyph = font5x7_basic[ch - 32];
    for (uint8_t col = 0; col < 5; col++) {
        uint8_t bits = glyph[col];
        for (uint8_t row = 0; row < 7; row++) {
            if (bits & (1U << row)) {
                draw_scaled_pixel(x + col * scale, y + row * scale, scale, color);
            }
        }
    }
}

void rm67162_draw_text(int16_t x, int16_t y, const char *text, uint16_t color, uint8_t scale, int32_t bg)
{
    if (scale == 0) {
        scale = 1;
    }
    int16_t cursor_x = x;
    int16_t cursor_y = y;
    while (*text) {
        char ch = *text++;
        if (ch == '\n') {
            cursor_x = x;
            cursor_y += 8 * scale;
            continue;
        }
        if (ch == '\r') {
            continue;
        }
        draw_char(cursor_x, cursor_y, ch, color, scale, bg);
        cursor_x += 6 * scale;
    }
}

void rm67162_set_brightness(uint8_t level)
{
    reg_write(0x51, &level, 1);
}

void rm67162_sleep(void)
{
    reg_write(0x10, NULL, 0);
}

void rm67162_wake(void)
{
    reg_write(0x11, NULL, 0);
    esp_rom_delay_us(120 * 1000);
}
