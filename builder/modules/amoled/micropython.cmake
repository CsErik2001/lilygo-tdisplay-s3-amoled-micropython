add_library(usermod_amoled INTERFACE)

target_sources(usermod_amoled INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/amoledmodule.c
    ${CMAKE_CURRENT_LIST_DIR}/amoled_i2c.c
    ${CMAKE_CURRENT_LIST_DIR}/rm67162.c
    ${CMAKE_CURRENT_LIST_DIR}/cst816.c
    ${CMAKE_CURRENT_LIST_DIR}/pcf85063.c
)

target_include_directories(usermod_amoled INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

# ESP-IDF components our C code links against directly (spi_master, i2c, gpio)
target_link_libraries(usermod_amoled INTERFACE
    idf::driver
    idf::esp_rom
)

target_link_libraries(usermod INTERFACE usermod_amoled)
