#define MICROPY_HW_BOARD_NAME               "LilyGo T-Display-S3 AMOLED Plus (Touch)"
#define MICROPY_HW_MCU_NAME                 "ESP32-S3"

#define MICROPY_PY_MACHINE_I2S              (1)
#define MICROPY_HW_ENABLE_SDCARD            (0)

// Reserved by the AMOLED family for the display TE signal - keep off
// general GPIO use even though the current driver doesn't read TE yet.
#define MICROPY_HW_RESERVED_PIN_TE          (9)

#define MICROPY_HW_I2C0_SCL                 (2)
#define MICROPY_HW_I2C0_SDA                 (3)
