/*
 * amoledmodule.c — MicroPython bindings for the RM67162 display and
 * CST816 touch drivers.
 *
 * Written against the MP_DEFINE_CONST_OBJ_TYPE macro API (MicroPython
 * >= v1.21). If your checked-out micropython is older, swap the type
 * declarations for the classic `const mp_obj_type_t xxx_type = { ... }`
 * struct-literal form — the method tables and call wrappers below don't
 * need to change either way.
 *
 * Python-side usage:
 *
 *     import amoled
 *     d = amoled.Display()
 *     d.rotation(1)
 *     d.brightness(200)
 *     d.fill_rect(0, 0, 239, 535, 0xF800)   # RGB565 red
 *
 *     t = amoled.Touch()
 *     p = t.read()
 *     if p:
 *         x, y, event = p
 */

#include "py/runtime.h"
#include "py/obj.h"
#include "py/builtin.h"
#include "py/stream.h"
#include <stdbool.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include "rm67162.h"
#include "cst816.h"
#include "pcf85063.h"

// ---------------------------------------------------------------------
// Display
// ---------------------------------------------------------------------

typedef struct _amoled_display_obj_t {
    mp_obj_base_t base;
} amoled_display_obj_t;

static mp_obj_t display_make_new(const mp_obj_type_t *type, size_t n_args,
                                  size_t n_kw, const mp_obj_t *args) {
    (void)n_args; (void)n_kw; (void)args;
    amoled_display_obj_t *self = mp_obj_malloc(amoled_display_obj_t, type);
    esp_err_t err = rm67162_init();
    if (err != ESP_OK) {
        mp_raise_OSError(err);
    }
    return MP_OBJ_FROM_PTR(self);
}

static mp_obj_t display_rotation(mp_obj_t self_in, mp_obj_t r_in) {
    (void)self_in;
    int rotation = mp_obj_get_int(r_in);
    if (rotation < 0 || rotation > 2) {
        mp_raise_ValueError(MP_ERROR_TEXT("rotation must be 0, 1, or 2"));
    }
    rm67162_set_rotation((uint8_t)rotation);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(display_rotation_obj, display_rotation);

static mp_obj_t display_brightness(mp_obj_t self_in, mp_obj_t level_in) {
    (void)self_in;
    rm67162_set_brightness((uint8_t)mp_obj_get_int(level_in));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(display_brightness_obj, display_brightness);

static mp_obj_t display_sleep(mp_obj_t self_in) {
    (void)self_in;
    rm67162_sleep();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(display_sleep_obj, display_sleep);

static mp_obj_t display_wake(mp_obj_t self_in) {
    (void)self_in;
    rm67162_wake();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(display_wake_obj, display_wake);

static mp_obj_t display_width(mp_obj_t self_in) {
    (void)self_in;
    return mp_obj_new_int(rm67162_get_width());
}
static MP_DEFINE_CONST_FUN_OBJ_1(display_width_obj, display_width);

static mp_obj_t display_height(mp_obj_t self_in) {
    (void)self_in;
    return mp_obj_new_int(rm67162_get_height());
}
static MP_DEFINE_CONST_FUN_OBJ_1(display_height_obj, display_height);

static void touch_apply_display_rotation(cst816_point_t *p) {
    uint16_t x = p->x;
    uint16_t y = p->y;

    switch (rm67162_get_rotation()) {
        case 1:
            p->x = (RM67162_HEIGHT - 1) - y;
            p->y = x;
            break;
        case 2:
            p->x = (RM67162_WIDTH - 1) - x;
            p->y = (RM67162_HEIGHT - 1) - y;
            break;
        default:
            break;
    }
}

static mp_obj_t display_clear(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    uint16_t color = (uint16_t)mp_obj_get_int(args[1]);
    rm67162_fill_rect(0, 0, rm67162_get_width() - 1, rm67162_get_height() - 1, color);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(display_clear_obj, 2, 2, display_clear);

static mp_obj_t display_pixel(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    rm67162_draw_pixel(
        (int16_t)mp_obj_get_int(args[1]), (int16_t)mp_obj_get_int(args[2]),
        (uint16_t)mp_obj_get_int(args[3]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(display_pixel_obj, 4, 4, display_pixel);

static mp_obj_t display_line(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    rm67162_draw_line(
        (int16_t)mp_obj_get_int(args[1]), (int16_t)mp_obj_get_int(args[2]),
        (int16_t)mp_obj_get_int(args[3]), (int16_t)mp_obj_get_int(args[4]),
        (uint16_t)mp_obj_get_int(args[5]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(display_line_obj, 6, 6, display_line);

static mp_obj_t display_rect(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    rm67162_draw_rect(
        (int16_t)mp_obj_get_int(args[1]), (int16_t)mp_obj_get_int(args[2]),
        (int16_t)mp_obj_get_int(args[3]), (int16_t)mp_obj_get_int(args[4]),
        (uint16_t)mp_obj_get_int(args[5]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(display_rect_obj, 6, 6, display_rect);

static mp_obj_t display_fill_rect(size_t n_args, const mp_obj_t *args) {
    // self, x0, y0, x1, y1, color
    (void)n_args;
    rm67162_fill_rect(
        mp_obj_get_int(args[1]), mp_obj_get_int(args[2]),
        mp_obj_get_int(args[3]), mp_obj_get_int(args[4]),
        (uint16_t)mp_obj_get_int(args[5]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(display_fill_rect_obj, 6, 6, display_fill_rect);

static mp_obj_t display_text(size_t n_args, const mp_obj_t *args) {
    // self, text, x, y, color, [scale], [bg]
    const char *text = mp_obj_str_get_str(args[1]);
    uint8_t scale = n_args >= 6 ? (uint8_t)mp_obj_get_int(args[5]) : 1;
    int32_t bg = n_args >= 7 ? mp_obj_get_int(args[6]) : -1;
    rm67162_draw_text(
        (int16_t)mp_obj_get_int(args[2]), (int16_t)mp_obj_get_int(args[3]),
        text, (uint16_t)mp_obj_get_int(args[4]), scale, bg);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(display_text_obj, 5, 7, display_text);

static mp_obj_t display_blit(size_t n_args, const mp_obj_t *args) {
    // self, buffer (bytes/bytearray of native-endian RGB565 words), x0, y0, x1, y1
    (void)n_args;
    mp_buffer_info_t buf;
    mp_get_buffer_raise(args[1], &buf, MP_BUFFER_READ);
    int x0 = mp_obj_get_int(args[2]);
    int y0 = mp_obj_get_int(args[3]);
    int x1 = mp_obj_get_int(args[4]);
    int y1 = mp_obj_get_int(args[5]);
    if (x1 < x0 || y1 < y0 || x0 < 0 || y0 < 0 ||
        x1 >= rm67162_get_width() || y1 >= rm67162_get_height()) {
        mp_raise_ValueError(MP_ERROR_TEXT("blit outside display"));
    }
    rm67162_set_window((uint16_t)x0, (uint16_t)y0, (uint16_t)x1, (uint16_t)y1);
    rm67162_push_pixels((const uint16_t *)buf.buf, buf.len / 2);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(display_blit_obj, 6, 6, display_blit);

static mp_obj_t image_open(mp_obj_t path)
{
    mp_obj_t open_args[2] = {
        path,
        mp_obj_new_str("rb", 2),
    };
    return mp_call_function_n_kw(MP_OBJ_FROM_PTR(&mp_builtin_open_obj), 2, 0, open_args);
}

static bool image_read_exact(mp_obj_t file, void *buf, size_t len, int *errcode)
{
    mp_uint_t out = mp_stream_read_exactly(file, buf, len, errcode);
    if (out == MP_STREAM_ERROR) {
        return false;
    }
    if (out != len) {
        *errcode = MP_EIO;
        return false;
    }
    return true;
}

static mp_obj_t display_draw_image(size_t n_args, const mp_obj_t *args) {
    // self, path, x, y, [w, h]
    int x = mp_obj_get_int(args[2]);
    int y = mp_obj_get_int(args[3]);
    uint16_t w = 0;
    uint16_t h = 0;
    bool raw_size_given = n_args == 6;

    mp_obj_t file = image_open(args[1]);

    if (raw_size_given) {
        w = (uint16_t)mp_obj_get_int(args[4]);
        h = (uint16_t)mp_obj_get_int(args[5]);
    } else {
        int errcode = 0;
        uint8_t header[8];
        if (!image_read_exact(file, header, sizeof(header), &errcode)) {
            mp_stream_close(file);
            mp_raise_OSError(errcode);
        }
        if (memcmp(header, "AMG0", 4) != 0) {
            mp_stream_close(file);
            mp_raise_ValueError(MP_ERROR_TEXT("bad image header"));
        }
        w = (uint16_t)(header[4] | (header[5] << 8));
        h = (uint16_t)(header[6] | (header[7] << 8));
    }

    if (w == 0 || h == 0 || x < 0 || y < 0 ||
        x + w > rm67162_get_width() || y + h > rm67162_get_height()) {
        mp_stream_close(file);
        mp_raise_ValueError(MP_ERROR_TEXT("image outside display"));
    }

    uint16_t *row = malloc((size_t)w * sizeof(uint16_t));
    if (row == NULL) {
        mp_stream_close(file);
        mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("image row alloc"));
    }

    for (uint16_t yy = 0; yy < h; yy++) {
        int errcode = 0;
        if (!image_read_exact(file, row, (size_t)w * sizeof(uint16_t), &errcode)) {
            free(row);
            mp_stream_close(file);
            mp_raise_OSError(errcode);
        }
        rm67162_set_window((uint16_t)x, (uint16_t)(y + yy), (uint16_t)(x + w - 1), (uint16_t)(y + yy));
        rm67162_push_pixels(row, w);
    }

    free(row);
    mp_stream_close(file);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(display_draw_image_obj, 4, 6, display_draw_image);

static const mp_rom_map_elem_t display_locals_dict_table[] = {
    { MP_ROM_QSTR(MP_QSTR_rotation),   MP_ROM_PTR(&display_rotation_obj) },
    { MP_ROM_QSTR(MP_QSTR_brightness), MP_ROM_PTR(&display_brightness_obj) },
    { MP_ROM_QSTR(MP_QSTR_sleep),      MP_ROM_PTR(&display_sleep_obj) },
    { MP_ROM_QSTR(MP_QSTR_wake),       MP_ROM_PTR(&display_wake_obj) },
    { MP_ROM_QSTR(MP_QSTR_width),      MP_ROM_PTR(&display_width_obj) },
    { MP_ROM_QSTR(MP_QSTR_height),     MP_ROM_PTR(&display_height_obj) },
    { MP_ROM_QSTR(MP_QSTR_clear),      MP_ROM_PTR(&display_clear_obj) },
    { MP_ROM_QSTR(MP_QSTR_pixel),      MP_ROM_PTR(&display_pixel_obj) },
    { MP_ROM_QSTR(MP_QSTR_line),       MP_ROM_PTR(&display_line_obj) },
    { MP_ROM_QSTR(MP_QSTR_rect),       MP_ROM_PTR(&display_rect_obj) },
    { MP_ROM_QSTR(MP_QSTR_fill_rect),  MP_ROM_PTR(&display_fill_rect_obj) },
    { MP_ROM_QSTR(MP_QSTR_text),       MP_ROM_PTR(&display_text_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit),       MP_ROM_PTR(&display_blit_obj) },
    { MP_ROM_QSTR(MP_QSTR_draw_image), MP_ROM_PTR(&display_draw_image_obj) },
    { MP_ROM_QSTR(MP_QSTR_WIDTH),      MP_ROM_INT(RM67162_WIDTH) },
    { MP_ROM_QSTR(MP_QSTR_HEIGHT),     MP_ROM_INT(RM67162_HEIGHT) },
};
static MP_DEFINE_CONST_DICT(display_locals_dict, display_locals_dict_table);

MP_DEFINE_CONST_OBJ_TYPE(
    amoled_display_type,
    MP_QSTR_Display,
    MP_TYPE_FLAG_NONE,
    make_new, display_make_new,
    locals_dict, &display_locals_dict
    );

// ---------------------------------------------------------------------
// Touch
// ---------------------------------------------------------------------

typedef struct _amoled_touch_obj_t {
    mp_obj_base_t base;
} amoled_touch_obj_t;

static mp_obj_t touch_make_new(const mp_obj_type_t *type, size_t n_args,
                                 size_t n_kw, const mp_obj_t *args) {
    (void)n_args; (void)n_kw; (void)args;
    amoled_touch_obj_t *self = mp_obj_malloc(amoled_touch_obj_t, type);
    esp_err_t err = cst816_init();
    if (err != ESP_OK) {
        mp_raise_OSError(err);
    }
    return MP_OBJ_FROM_PTR(self);
}

static mp_obj_t touch_read(mp_obj_t self_in) {
    (void)self_in;
    cst816_point_t p;
    if (!cst816_read(&p)) {
        return mp_const_none;
    }
    touch_apply_display_rotation(&p);
    mp_obj_t tuple[3] = {
        mp_obj_new_int(p.x),
        mp_obj_new_int(p.y),
        mp_obj_new_int(p.event),
    };
    return mp_obj_new_tuple(3, tuple);
}
static MP_DEFINE_CONST_FUN_OBJ_1(touch_read_obj, touch_read);

static mp_obj_t touch_touched(mp_obj_t self_in) {
    (void)self_in;
    return mp_obj_new_bool(cst816_touched());
}
static MP_DEFINE_CONST_FUN_OBJ_1(touch_touched_obj, touch_touched);

static mp_obj_t touch_home(mp_obj_t self_in) {
    (void)self_in;
    return mp_obj_new_bool(cst816_home_pressed());
}
static MP_DEFINE_CONST_FUN_OBJ_1(touch_home_obj, touch_home);

static mp_obj_t touch_raw(mp_obj_t self_in) {
    (void)self_in;
    uint8_t buf[7];
    if (!cst816_read_raw(buf, sizeof(buf))) {
        mp_raise_OSError(EIO);
    }
    return mp_obj_new_bytes(buf, sizeof(buf));
}
static MP_DEFINE_CONST_FUN_OBJ_1(touch_raw_obj, touch_raw);

static const mp_rom_map_elem_t touch_locals_dict_table[] = {
    { MP_ROM_QSTR(MP_QSTR_read),    MP_ROM_PTR(&touch_read_obj) },
    { MP_ROM_QSTR(MP_QSTR_touched), MP_ROM_PTR(&touch_touched_obj) },
    { MP_ROM_QSTR(MP_QSTR_home),    MP_ROM_PTR(&touch_home_obj) },
    { MP_ROM_QSTR(MP_QSTR_raw),     MP_ROM_PTR(&touch_raw_obj) },
};
static MP_DEFINE_CONST_DICT(touch_locals_dict, touch_locals_dict_table);

MP_DEFINE_CONST_OBJ_TYPE(
    amoled_touch_type,
    MP_QSTR_Touch,
    MP_TYPE_FLAG_NONE,
    make_new, touch_make_new,
    locals_dict, &touch_locals_dict
    );

// ---------------------------------------------------------------------
// RTC
// ---------------------------------------------------------------------

typedef struct _amoled_rtc_obj_t {
    mp_obj_base_t base;
} amoled_rtc_obj_t;

static mp_obj_t rtc_make_new(const mp_obj_type_t *type, size_t n_args,
                              size_t n_kw, const mp_obj_t *args) {
    (void)n_args; (void)n_kw; (void)args;
    amoled_rtc_obj_t *self = mp_obj_malloc(amoled_rtc_obj_t, type);
    esp_err_t err = pcf85063_init();
    if (err != ESP_OK) {
        mp_raise_OSError(err);
    }
    return MP_OBJ_FROM_PTR(self);
}

static mp_obj_t rtc_datetime(size_t n_args, const mp_obj_t *args) {
    if (n_args == 1) {
        pcf85063_datetime_t dt;
        if (!pcf85063_get_datetime(&dt)) {
            mp_raise_OSError(EIO);
        }
        mp_obj_t tuple[8] = {
            mp_obj_new_int(dt.year),
            mp_obj_new_int(dt.month),
            mp_obj_new_int(dt.day),
            mp_obj_new_int(dt.weekday),
            mp_obj_new_int(dt.hour),
            mp_obj_new_int(dt.minute),
            mp_obj_new_int(dt.second),
            MP_OBJ_NEW_SMALL_INT(0),
        };
        return mp_obj_new_tuple(8, tuple);
    }

    mp_obj_t *items;
    mp_obj_get_array_fixed_n(args[1], 8, &items);
    pcf85063_datetime_t dt = {
        .year = (uint16_t)mp_obj_get_int(items[0]),
        .month = (uint8_t)mp_obj_get_int(items[1]),
        .day = (uint8_t)mp_obj_get_int(items[2]),
        .weekday = (uint8_t)mp_obj_get_int(items[3]),
        .hour = (uint8_t)mp_obj_get_int(items[4]),
        .minute = (uint8_t)mp_obj_get_int(items[5]),
        .second = (uint8_t)mp_obj_get_int(items[6]),
    };
    esp_err_t err = pcf85063_set_datetime(&dt);
    if (err == ESP_ERR_INVALID_ARG) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid datetime"));
    }
    if (err != ESP_OK) {
        mp_raise_OSError(err);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(rtc_datetime_obj, 1, 2, rtc_datetime);

static mp_obj_t rtc_is_valid(mp_obj_t self_in) {
    (void)self_in;
    return mp_obj_new_bool(pcf85063_is_valid());
}
static MP_DEFINE_CONST_FUN_OBJ_1(rtc_is_valid_obj, rtc_is_valid);

static const mp_rom_map_elem_t rtc_locals_dict_table[] = {
    { MP_ROM_QSTR(MP_QSTR_datetime), MP_ROM_PTR(&rtc_datetime_obj) },
    { MP_ROM_QSTR(MP_QSTR_is_valid), MP_ROM_PTR(&rtc_is_valid_obj) },
};
static MP_DEFINE_CONST_DICT(rtc_locals_dict, rtc_locals_dict_table);

MP_DEFINE_CONST_OBJ_TYPE(
    amoled_rtc_type,
    MP_QSTR_RTC,
    MP_TYPE_FLAG_NONE,
    make_new, rtc_make_new,
    locals_dict, &rtc_locals_dict
    );

// ---------------------------------------------------------------------
// Module
// ---------------------------------------------------------------------

static mp_obj_t module_scan_i2c(void) {
    uint8_t addrs[16];
    uint32_t count = cst816_scan(addrs, sizeof(addrs));
    mp_obj_t items[16];
    for (uint32_t i = 0; i < count; i++) {
        items[i] = mp_obj_new_int(addrs[i]);
    }
    return mp_obj_new_list(count, items);
}
static MP_DEFINE_CONST_FUN_OBJ_0(module_scan_i2c_obj, module_scan_i2c);

static const mp_rom_map_elem_t amoled_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_amoled) },
    { MP_ROM_QSTR(MP_QSTR_Display),  MP_ROM_PTR(&amoled_display_type) },
    { MP_ROM_QSTR(MP_QSTR_Touch),    MP_ROM_PTR(&amoled_touch_type) },
    { MP_ROM_QSTR(MP_QSTR_RTC),      MP_ROM_PTR(&amoled_rtc_type) },
    { MP_ROM_QSTR(MP_QSTR_scan_i2c),  MP_ROM_PTR(&module_scan_i2c_obj) },
    { MP_ROM_QSTR(MP_QSTR_WIDTH),     MP_ROM_INT(RM67162_WIDTH) },
    { MP_ROM_QSTR(MP_QSTR_HEIGHT),    MP_ROM_INT(RM67162_HEIGHT) },
};
static MP_DEFINE_CONST_DICT(amoled_module_globals, amoled_module_globals_table);

const mp_obj_module_t amoled_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&amoled_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_amoled, amoled_user_cmodule);
