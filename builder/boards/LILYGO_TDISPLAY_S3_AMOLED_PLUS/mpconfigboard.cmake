set(IDF_TARGET esp32s3)

set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.usb
    boards/sdkconfig.ble
    boards/sdkconfig.240mhz
    boards/sdkconfig.spiram_sx
    ${SDKCONFIG_IDF_VERSION_SPECIFIC}
    boards/LILYGO_TDISPLAY_S3_AMOLED_PLUS/sdkconfig.board
)

set(USER_C_MODULES
    ${CMAKE_CURRENT_LIST_DIR}/../../modules/amoled/micropython.cmake
)
