cmake_minimum_required(VERSION 3.22)

project(adaptive_ecu LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(ECU_BUILD_TESTS "Build adaptive ECU tests" ON)
option(ENABLE_COVERAGE "Build with gcov coverage flags" OFF)
option(ENABLE_ASAN "Build with AddressSanitizer" OFF)

if(ENABLE_ASAN)
    if(ENABLE_COVERAGE)
        message(FATAL_ERROR "ENABLE_ASAN and ENABLE_COVERAGE must not be enabled together")
    endif()
    if(NOT CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        message(FATAL_ERROR "ENABLE_ASAN requires GCC or Clang")
    endif()
    add_compile_options(-fsanitize=address -fno-omit-frame-pointer -g)
    add_link_options(-fsanitize=address)
endif()

if(ENABLE_COVERAGE)
    add_compile_options(--coverage)
    add_link_options(--coverage)
endif()

find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)

add_library(ecu_core
    src/bsw/can_cdd.cpp
    src/bsw/can_tx_trace.cpp
    src/bsw/ads1115_registers.cpp
    src/bsw/ads1115_acquirer.cpp
    src/bsw/linux_i2c_transport.cpp
    src/bsw/can_publisher.cpp
    src/bsw/mock_can_driver.cpp
    src/bsw/secoc_module.cpp
    src/bsw/watchdog_manager.cpp
    src/bsw/task_recovery.cpp
    src/bsw/planned_restart.cpp
    src/app/bms_calculation_task.cpp
    src/app/ekf_soc_estimator.cpp
    src/app/failsafe_sm.cpp
    src/app/sensor_simulator.cpp
    src/app/input_lineage.cpp
    src/app/ads1115_conversion.cpp
    src/app/soh_estimator.cpp
    src/app/soh_capacity_scenario.cpp
    src/app/recovery_checkpoint.cpp
    src/app/protection_history.cpp
    src/app/checkpoint_writer.cpp
    src/app/checkpoint_store.cpp
    ../common/can_session_crypto.cpp
    ../common/can_session_frames.cpp
    ../common/can_session_exchange.cpp
    ../common/can_session_receiver.cpp
    ../common/can_diagnostic.cpp
    ../common/can_session_config.cpp
    ../common/can_restart_notice.cpp
)
target_include_directories(ecu_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/../common)
target_link_libraries(ecu_core PUBLIC OpenSSL::Crypto Threads::Threads)

# Physical acquisition/calculation is separate from the virtual pack model.
add_library(physical_sensor_core
    src/app/physical_soc_ekf.cpp
    src/app/physical_battery_meter.cpp
    src/app/physical_sensor_runtime.cpp
    src/bsw/physical_sensor_process.cpp
    src/bsw/ina219_acquirer.cpp
    src/bsw/ds18b20_acquirer.cpp
    src/bsw/bounded_sensor_read.cpp)
target_include_directories(physical_sensor_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(physical_sensor_core PUBLIC Threads::Threads OpenSSL::Crypto)
add_executable(evaluate_physical_capture tools/evaluate_physical_capture.cpp)
target_link_libraries(evaluate_physical_capture PRIVATE physical_sensor_core)

add_executable(adaptive_ecu main.cpp)
target_link_libraries(adaptive_ecu PRIVATE ecu_core physical_sensor_core)

# Read-only synthetic accuracy tool; no key, CAN or device initialization.
add_executable(evaluate_soc_profile tools/evaluate_soc_profile.cpp)
target_link_libraries(evaluate_soc_profile PRIVATE ecu_core)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    add_executable(physical_battery_worker tools/physical_battery_worker.cpp)
    target_link_libraries(physical_battery_worker PRIVATE physical_sensor_core ecu_core)
    add_dependencies(adaptive_ecu physical_battery_worker)
    add_executable(physical_battery_capture tools/physical_battery_capture.cpp)
    target_link_libraries(physical_battery_capture PRIVATE physical_sensor_core ecu_core)
    add_executable(ads1115_can_smoke tools/ads1115_can_smoke.cpp)
    target_link_libraries(ads1115_can_smoke PRIVATE ecu_core)
    add_executable(ads1115_capture tools/ads1115_capture.cpp)
    target_link_libraries(ads1115_capture PRIVATE ecu_core)
endif()

if(ECU_BUILD_TESTS)
    enable_testing()
    # Test-only probe: preserve raw single-cell input and expose existing
    # float/int temperature conversions without invoking the pack estimator.
    add_executable(profile_loader_fixture ../common/profile_loader_fixture.cpp)
    target_link_libraries(profile_loader_fixture PRIVATE ecu_core)
    find_package(Python3 QUIET COMPONENTS Interpreter)
    if(Python3_Interpreter_FOUND)
        if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
            add_executable(physical_capture_fixture tools/physical_battery_capture.cpp test/ina219_i2c_fixture.cpp)
            target_link_libraries(physical_capture_fixture PRIVATE physical_sensor_core ecu_core)
            target_link_options(physical_capture_fixture PRIVATE "-Wl,--wrap=ioctl" "-Wl,--wrap=write")
            add_executable(physical_worker_fixture tools/physical_battery_worker.cpp test/ina219_i2c_fixture.cpp)
            target_link_libraries(physical_worker_fixture PRIVATE physical_sensor_core ecu_core)
            target_link_options(physical_worker_fixture PRIVATE "-Wl,--wrap=ioctl" "-Wl,--wrap=write")
            add_test(NAME test_physical_capture_cli COMMAND ${Python3_EXECUTABLE}
                ${CMAKE_CURRENT_SOURCE_DIR}/test/test_physical_capture_cli.py
                --capture $<TARGET_FILE:physical_battery_capture>
                --fixture $<TARGET_FILE:physical_capture_fixture>
                --evaluator $<TARGET_FILE:evaluate_physical_capture>)
            set_tests_properties(test_physical_capture_cli PROPERTIES TIMEOUT 20)
        endif()
        add_test(NAME test_soc_profile_product COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_soc_profile_product.py
            --evaluator $<TARGET_FILE:evaluate_soc_profile>
            --profile-loader $<TARGET_FILE:profile_loader_fixture>
            --out-parent ${CMAKE_CURRENT_BINARY_DIR}/soc-profile-test-results)
        set_tests_properties(test_soc_profile_product PROPERTIES TIMEOUT 45 RUN_SERIAL TRUE)
    endif()
    # Cross-language/session regression targets are separate from product core.
    add_executable(test_can_session_candidate
        ../common/test_can_session_candidate.cpp
        ../common/can_session_crypto.cpp ../common/can_session_frames.cpp)
    target_link_libraries(test_can_session_candidate PRIVATE OpenSSL::Crypto)
    target_compile_definitions(test_can_session_candidate PRIVATE
        SESSION_FIXTURE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../common/testdata/session-v2-vectors.tsv")
    add_test(NAME test_can_session_candidate COMMAND test_can_session_candidate)
    add_executable(test_can_session_exchange
        ../common/test_can_session_exchange.cpp ../common/can_session_exchange.cpp
        ../common/can_session_crypto.cpp ../common/can_session_frames.cpp ../common/can_session_receiver.cpp ../common/can_diagnostic.cpp)
    target_link_libraries(test_can_session_exchange PRIVATE OpenSSL::Crypto)
    add_test(NAME test_can_session_exchange COMMAND test_can_session_exchange)
    add_executable(test_can_session_receiver
        ../common/test_can_session_receiver.cpp ../common/can_session_receiver.cpp
        ../common/can_session_crypto.cpp ../common/can_session_frames.cpp)
    target_link_libraries(test_can_session_receiver PRIVATE OpenSSL::Crypto)
    add_test(NAME test_can_session_receiver COMMAND test_can_session_receiver)
    add_executable(test_can_diagnostic
        ../common/test_can_diagnostic.cpp ../common/can_diagnostic.cpp
        ../common/can_session_crypto.cpp ../common/can_session_frames.cpp ../common/can_session_receiver.cpp ../common/can_session_exchange.cpp
        ../common/can_restart_notice.cpp src/bsw/planned_restart.cpp)
    target_include_directories(test_can_diagnostic PRIVATE include)
    target_link_libraries(test_can_diagnostic PRIVATE OpenSSL::Crypto)
    target_compile_definitions(test_can_diagnostic PRIVATE
        PHYSICAL_FIXTURE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../common/testdata/physical-v1-vectors.tsv"
        DIAGNOSTIC_INPUT_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../common/testdata/diagnostic-inputs.tsv"
        DIAGNOSTIC_FIXTURE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../common/testdata/diagnostic-v1-vectors.tsv"
        PROTECTION_FIXTURE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../common/testdata/protection-v1-vectors.tsv")
    add_test(NAME test_can_diagnostic COMMAND test_can_diagnostic)
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
        add_executable(ecu_sender_control_fixture main.cpp)
        target_compile_definitions(ecu_sender_control_fixture PRIVATE ECU_SENDER_CONTROL_FIXTURE)
        target_link_libraries(ecu_sender_control_fixture PRIVATE ecu_core physical_sensor_core)
        add_executable(ecu_rx_fault_fixture main.cpp)
        target_compile_definitions(ecu_rx_fault_fixture PRIVATE ECU_RX_FAULT_FIXTURE)
        target_link_libraries(ecu_rx_fault_fixture PRIVATE ecu_core physical_sensor_core)
        add_executable(ecu_bms_stall_fixture main.cpp test/ecu_bms_fault_fixture.cpp)
        target_compile_definitions(ecu_bms_stall_fixture PRIVATE ECU_TASK_FAULT_FIXTURE ECU_TASK_STALL_FIXTURE)
        target_link_libraries(ecu_bms_stall_fixture PRIVATE ecu_core physical_sensor_core)
        add_executable(ecu_bms_fault_fixture main.cpp test/ecu_bms_fault_fixture.cpp)
        target_compile_definitions(ecu_bms_fault_fixture PRIVATE ECU_TASK_FAULT_FIXTURE)
        target_link_libraries(ecu_bms_fault_fixture PRIVATE ecu_core physical_sensor_core)
        add_executable(ecu_bms_recover_fixture main.cpp test/ecu_bms_fault_fixture.cpp)
        target_compile_definitions(ecu_bms_recover_fixture PRIVATE ECU_TASK_FAULT_FIXTURE ECU_TASK_RECOVER_FIXTURE)
        target_link_libraries(ecu_bms_recover_fixture PRIVATE ecu_core physical_sensor_core)
        add_executable(test_ids_diagnostic_socket
            ../common/test_ids_diagnostic_socket.cpp ../common/can_diagnostic.cpp
            ../common/can_session_crypto.cpp ../common/can_session_frames.cpp)
        target_link_libraries(test_ids_diagnostic_socket PRIVATE OpenSSL::Crypto)
        add_test(NAME test_ids_diagnostic_socket COMMAND test_ids_diagnostic_socket)
        add_executable(test_can_session_vcan
            ../common/test_can_session_vcan.cpp ../common/can_session_exchange.cpp
            ../common/can_session_crypto.cpp ../common/can_session_frames.cpp
            ../common/can_session_receiver.cpp ../common/can_diagnostic.cpp
            ../common/can_restart_notice.cpp src/bsw/planned_restart.cpp)
        target_include_directories(test_can_session_vcan PRIVATE include)
        target_link_libraries(test_can_session_vcan PRIVATE OpenSSL::Crypto)
        add_test(NAME test_can_session_vcan COMMAND test_can_session_vcan)
        set_tests_properties(test_can_session_vcan PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 15)
        if(Python3_Interpreter_FOUND)
            add_test(NAME test_ecu_session_product COMMAND ${Python3_EXECUTABLE}
                ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_ecu_session_product.py
                --ecu $<TARGET_FILE:adaptive_ecu> --peer $<TARGET_FILE:test_can_session_vcan>
                --policy ${CMAKE_CURRENT_SOURCE_DIR}/data/session-v2-development.conf
                --out-parent ${CMAKE_CURRENT_BINARY_DIR}/input-lineage-test-results)
            set_tests_properties(test_ecu_session_product PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 90 RUN_SERIAL TRUE)
            add_test(NAME test_physical_ecu_product COMMAND ${Python3_EXECUTABLE}
                ${CMAKE_CURRENT_SOURCE_DIR}/test/test_physical_ecu_product.py
                --ecu $<TARGET_FILE:adaptive_ecu> --rx-fixture $<TARGET_FILE:ecu_rx_fault_fixture>
                --worker-fixture $<TARGET_FILE:physical_worker_fixture>
                --peer $<TARGET_FILE:test_can_session_vcan>
                --policy ${CMAKE_CURRENT_SOURCE_DIR}/data/session-v2-development.conf
                --config-example ${CMAKE_CURRENT_SOURCE_DIR}/data/physical-battery.conf.example
                --out-parent ${CMAKE_CURRENT_BINARY_DIR}/physical-product-results)
            set_tests_properties(test_physical_ecu_product PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 150 RUN_SERIAL TRUE)
        endif()
    endif()
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
        test_ads1115_acquirer
        test_hardware_sample_feed
        test_can_publisher
        test_can_receive_lifecycle
        test_ekf_soc
        test_soh_estimator
        test_failsafe_sm
        test_failsafe_profile
        test_watchdog_manager
        test_bms_calculation_task
        test_task_recovery
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
    set(PHYSICAL_SENSOR_TESTS test_ina219_acquirer test_ds18b20_acquirer test_physical_battery_meter test_physical_sensor_runtime)
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
        list(APPEND PHYSICAL_SENSOR_TESTS test_bounded_sensor_read)
    endif()
    foreach(test_name IN LISTS PHYSICAL_SENSOR_TESTS)
        add_executable(${test_name} test/${test_name}.cpp)
        target_include_directories(${test_name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../common)
        target_link_libraries(${test_name} PRIVATE physical_sensor_core)
        if(TARGET GTest::gtest_main)
            target_link_libraries(${test_name} PRIVATE GTest::gtest_main)
        else()
            target_link_libraries(${test_name} PRIVATE GTest::GTest GTest::Main)
        endif()
        add_test(NAME ${test_name} COMMAND ${test_name})
    endforeach()
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
        # Test executable only: inject syscall failures without a production
        # environment/CLI fault switch or a CanDriver API change.
        target_link_options(test_can_receive_lifecycle PRIVATE "-Wl,--wrap=send")
    endif()
    set_tests_properties(test_can_receive_lifecycle PROPERTIES
        SKIP_REGULAR_EXPRESSION "\\[  SKIPPED \\]")
    # Host integration test only: exercise the actual IVI verifier/service on
    # the ECU-produced frames without adding IVI dependencies to ecu_core.
    target_sources(test_soh_estimator PRIVATE
        ../ivi_platform/hal/can_parser.cpp
        ../ivi_platform/hal/secoc_verifier.cpp
        ../ivi_platform/service/vehicle_data_service.cpp)
    target_sources(test_soh_estimator PRIVATE ../ivi_platform/service/session_vehicle_data.cpp)
    target_include_directories(test_soh_estimator PRIVATE
        ../ivi_platform/hal ../ivi_platform/service)
endif()

# Packaging only. Installing files never enables/starts a system service.
install(TARGETS adaptive_ecu RUNTIME DESTINATION bin)
if(TARGET physical_battery_worker)
    install(TARGETS physical_battery_worker RUNTIME DESTINATION bin)
endif()
install(PROGRAMS scripts/supervise_ecu.py DESTINATION adaptive_ecu/scripts)
install(FILES scripts/owned_ids.py DESTINATION adaptive_ecu/scripts)
install(FILES service/capstone-ecu@.service service/ecu.conf.example
    DESTINATION share/capstone/systemd)
install(FILES data/session-v2-development.conf DESTINATION share/capstone)
