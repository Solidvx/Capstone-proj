cmake_minimum_required(VERSION 3.22)

project(adaptive_ecu LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(ECU_BUILD_TESTS "Build adaptive ECU tests" ON)
option(ENABLE_COVERAGE "Build with gcov coverage flags" OFF)

if(ENABLE_COVERAGE)
    add_compile_options(--coverage)
    add_link_options(--coverage)
endif()

find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)

add_library(ecu_core
    src/bsw/can_cdd.cpp
    src/bsw/ads1115_registers.cpp
    src/bsw/can_publisher.cpp
    src/bsw/mock_can_driver.cpp
    src/bsw/secoc_module.cpp
    src/bsw/watchdog_manager.cpp
    src/app/ekf_soc_estimator.cpp
    src/app/failsafe_sm.cpp
    src/app/sensor_simulator.cpp
    src/app/ads1115_conversion.cpp
    src/app/soh_estimator.cpp
)
target_include_directories(ecu_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(ecu_core PUBLIC OpenSSL::Crypto Threads::Threads)

add_executable(adaptive_ecu main.cpp)
target_link_libraries(adaptive_ecu PRIVATE ecu_core)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    add_executable(ads1115_can_smoke tools/ads1115_can_smoke.cpp)
    target_link_libraries(ads1115_can_smoke PRIVATE ecu_core)
endif()

if(ECU_BUILD_TESTS)
    enable_testing()
    find_package(GTest REQUIRED)

    set(ECU_TESTS
        test_publisher
        test_mock_can_driver
        test_sensor_simulator
        test_ads1115_conversion
        test_sensor_quality
        test_adc_acquisition_gate
        test_ads1115_registers
        test_ads1115_sample
        test_can_publisher
        test_ekf_soc
        test_soh_estimator
        test_failsafe_sm
        test_watchdog_manager
        test_secoc
    )

    foreach(test_name IN LISTS ECU_TESTS)
        add_executable(${test_name} test/${test_name}.cpp)
        target_link_libraries(${test_name} PRIVATE ecu_core)
        if(TARGET GTest::gtest_main)
            target_link_libraries(${test_name} PRIVATE GTest::gtest_main)
        else()
            target_link_libraries(${test_name} PRIVATE GTest::GTest GTest::Main)
        endif()
        target_compile_definitions(${test_name} PRIVATE ECU_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")
        add_test(NAME ${test_name} COMMAND ${test_name})
    endforeach()
endif()
