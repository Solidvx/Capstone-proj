cmake_minimum_required(VERSION 3.22)

project(ivi_platform LANGUAGES CXX)

include(GNUInstallDirs)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(IVI_BUILD_TESTS "Build IVI core tests" ON)
option(IVI_BUILD_QT_APP "Build the Qt Quick dashboard when Qt 6 is available" ON)
option(IVI_BUILD_EXPERIMENT_TOOLS "Build separate, unprotected CAN experiment dashboard" OFF)
option(ENABLE_ASAN "Build with AddressSanitizer" OFF)
option(ENABLE_COVERAGE "Build with GCC gcov coverage flags" OFF)
set(IVI_TEST_ECU_EXECUTABLE "" CACHE FILEPATH "Explicit built ECU for actual Qt/ECU virtual CAN integration")

if(ENABLE_COVERAGE)
    if(ENABLE_ASAN OR NOT CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        message(FATAL_ERROR "ENABLE_COVERAGE requires GCC and cannot be combined with ASan")
    endif()
    add_compile_options(--coverage)
    add_link_options(--coverage)
endif()

if(ENABLE_ASAN)
    if(NOT CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        message(FATAL_ERROR "ENABLE_ASAN requires GCC or Clang")
    endif()
    add_compile_options(-fsanitize=address -fno-omit-frame-pointer -g)
    add_link_options(-fsanitize=address)
endif()

find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)

add_library(ivi_core
    hal/can_frame_validator.cpp
    hal/can_parser.cpp
    hal/secoc_verifier.cpp
    service/vehicle_data_service.cpp
    service/session_vehicle_data.cpp
    ../common/can_session_crypto.cpp ../common/can_session_frames.cpp
    ../common/can_session_exchange.cpp ../common/can_session_receiver.cpp
    ../common/can_diagnostic.cpp ../common/can_session_config.cpp
)
target_include_directories(ivi_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/hal
    ${CMAKE_CURRENT_SOURCE_DIR}/service
    ${CMAKE_CURRENT_SOURCE_DIR}/../common
)
target_link_libraries(ivi_core PUBLIC OpenSSL::Crypto Threads::Threads)

add_library(ivi_socketcan hal/socketcan_receiver.cpp)
target_include_directories(ivi_socketcan PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/hal)
target_link_libraries(ivi_socketcan PUBLIC ivi_core Threads::Threads)

if(IVI_BUILD_TESTS)
    enable_testing()
    # Cross-language/session regression targets are separate from product core.
    add_executable(test_can_session_candidate
        ../common/test_can_session_candidate.cpp
        ../common/can_session_crypto.cpp ../common/can_session_frames.cpp)
    target_link_libraries(test_can_session_candidate PRIVATE OpenSSL::Crypto)
    target_compile_definitions(test_can_session_candidate PRIVATE
        SESSION_FIXTURE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../docs/aidlc/changes/CHG-029/session-v2-vectors.tsv")
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
        ../common/can_restart_notice.cpp ../adaptive_ecu/src/bsw/planned_restart.cpp)
    target_include_directories(test_can_diagnostic PRIVATE ../adaptive_ecu/include)
    target_link_libraries(test_can_diagnostic PRIVATE OpenSSL::Crypto)
    target_compile_definitions(test_can_diagnostic PRIVATE
        PHYSICAL_FIXTURE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../docs/aidlc/changes/CHG-031/physical-v1-vectors.tsv"
        DIAGNOSTIC_INPUT_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../docs/aidlc/changes/CHG-029/diagnostic-inputs.tsv"
        DIAGNOSTIC_FIXTURE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../docs/aidlc/changes/CHG-029/diagnostic-v1-vectors.tsv"
        PROTECTION_FIXTURE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../docs/aidlc/changes/CHG-029/protection-v1-vectors.tsv")
    add_test(NAME test_can_diagnostic COMMAND test_can_diagnostic)
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
        add_executable(test_can_session_vcan
            ../common/test_can_session_vcan.cpp ../common/can_session_exchange.cpp
            ../common/can_session_crypto.cpp ../common/can_session_frames.cpp
            ../common/can_session_receiver.cpp ../common/can_diagnostic.cpp
            ../common/can_restart_notice.cpp ../adaptive_ecu/src/bsw/planned_restart.cpp)
        target_include_directories(test_can_session_vcan PRIVATE ../adaptive_ecu/include)
        target_link_libraries(test_can_session_vcan PRIVATE OpenSSL::Crypto)
        add_test(NAME test_can_session_vcan COMMAND test_can_session_vcan)
        set_tests_properties(test_can_session_vcan PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 15)
    endif()
    foreach(test_name IN ITEMS
            test_can_frame_validator
            test_can_parser
            test_receive_retry_policy
            test_secoc_verifier
            test_vehicle_data_service
            test_vehicle_data_service_security
            test_vehicle_data_service_state
            test_vehicle_data_session
            test_secoc_runtime)
        add_executable(${test_name} test/${test_name}.cpp)
        target_include_directories(${test_name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/test)
        target_link_libraries(${test_name} PRIVATE ivi_core)
        add_test(NAME ${test_name} COMMAND ${test_name})
    endforeach()
    add_executable(test_unprotected_test_receiver test/test_unprotected_test_receiver.cpp)
    target_include_directories(test_unprotected_test_receiver PRIVATE test ui_qml)
    target_link_libraries(test_unprotected_test_receiver PRIVATE ivi_core)
    add_test(NAME test_unprotected_test_receiver COMMAND test_unprotected_test_receiver)
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
        add_executable(test_socketcan_receiver test/test_socketcan_receiver.cpp)
        target_include_directories(test_socketcan_receiver PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}/test)
        target_link_libraries(test_socketcan_receiver PRIVATE ivi_socketcan)
        add_test(NAME test_socketcan_receiver COMMAND test_socketcan_receiver)
        set_tests_properties(test_socketcan_receiver PROPERTIES SKIP_RETURN_CODE 77)
    endif()
endif()

if(IVI_BUILD_QT_APP)
    find_package(Qt6 6.8 QUIET COMPONENTS Core Gui Qml Quick QuickControls2 Test)
    if(Qt6_FOUND)
        qt_standard_project_setup(REQUIRES 6.8)
        qt_add_library(ivi_event_journal STATIC ui_qml/event_journal.cpp ui_qml/event_journal.h)
        target_include_directories(ivi_event_journal PUBLIC ui_qml)
        target_link_libraries(ivi_event_journal PUBLIC Qt6::Core Threads::Threads)
        if(IVI_BUILD_TESTS)
            qt_add_executable(test_event_journal test/test_event_journal.cpp)
            target_link_libraries(test_event_journal PRIVATE ivi_event_journal Qt6::Test)
            add_test(NAME test_event_journal COMMAND test_event_journal)
            find_package(Python3 REQUIRED COMPONENTS Interpreter)
            set(history_supervisor_args)
            if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
                add_library(test_journal_stall SHARED ../common/journal_stall_fixture.cpp)
                target_link_libraries(test_journal_stall PRIVATE ${CMAKE_DL_LIBS})
                list(APPEND history_supervisor_args
                    --supervisor ${CMAKE_CURRENT_SOURCE_DIR}/scripts/supervise_dashboard.py
                    --stall-preload $<TARGET_FILE:test_journal_stall>)
            endif()
            add_test(NAME test_event_history_product COMMAND ${Python3_EXECUTABLE}
                ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_event_history_product.py
                --ivi $<TARGET_FILE:ivi_dashboard> ${history_supervisor_args}
                --out-parent ${CMAKE_CURRENT_BINARY_DIR}/history-test-results)
            set_tests_properties(test_event_history_product PROPERTIES TIMEOUT 30 RUN_SERIAL TRUE)
            add_executable(test_latency_recorder test/test_latency_recorder.cpp)
            target_include_directories(test_latency_recorder PRIVATE ui_qml)
            target_link_libraries(test_latency_recorder PRIVATE Qt6::Core Qt6::Test)
            add_test(NAME test_latency_recorder COMMAND test_latency_recorder)
            qt_add_executable(test_dashboard_security
                test/test_dashboard_security.cpp
                ui_qml/dashboard_view_model.cpp
                ui_qml/dashboard_view_model.h)
            target_include_directories(test_dashboard_security PRIVATE test ui_qml)
            target_link_libraries(test_dashboard_security PRIVATE
                ivi_core Qt6::Core Qt6::Gui Qt6::Qml Qt6::Quick Qt6::QuickControls2)
            target_compile_definitions(test_dashboard_security PRIVATE
                IVI_QML_FILE="${CMAKE_CURRENT_SOURCE_DIR}/ui_qml/qml/Main.qml")
            add_test(NAME test_dashboard_security COMMAND test_dashboard_security)
            set_tests_properties(test_dashboard_security PROPERTIES
                ENVIRONMENT "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software")
        endif()
        qt_add_executable(ivi_dashboard
            ui_qml/main.cpp
            ui_qml/dashboard_view_model.cpp
            ui_qml/dashboard_view_model.h
        )
        target_link_libraries(ivi_dashboard PRIVATE ivi_event_journal)
        target_include_directories(ivi_dashboard PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}/hal
            ${CMAKE_CURRENT_SOURCE_DIR}/service
            ${CMAKE_CURRENT_SOURCE_DIR}/ui_qml
        )
        target_link_libraries(ivi_dashboard PRIVATE
            ivi_core
            ivi_socketcan
            Qt6::Core
            Qt6::Gui
            Qt6::Qml
            Qt6::Quick
            Qt6::QuickControls2
        )
        if(CMAKE_CXX_COMPILER_ID STREQUAL "AppleClang")
            target_compile_options(ivi_dashboard PRIVATE
                -Wno-variadic-macro-arguments-omitted)
        endif()
        qt_add_qml_module(ivi_dashboard
            URI IviDashboard
            VERSION 1.0
            QML_FILES
                ui_qml/qml/Main.qml
                ui_qml/qml/SocGauge.qml
        )
        qt_add_resources(ivi_dashboard ivi_fonts
            PREFIX "/ivi-fonts" BASE "ui_qml/fonts"
            FILES ui_qml/fonts/NanumGothic-Regular.ttf ui_qml/fonts/OFL.txt)
        install(FILES ui_qml/fonts/OFL.txt DESTINATION ${CMAKE_INSTALL_DATADIR}/licenses/ivi_dashboard
            RENAME NanumGothic-OFL.txt)
        install(PROGRAMS scripts/export_event_history.py scripts/supervise_dashboard.py scripts/dashboard_handoff.py DESTINATION ${CMAKE_INSTALL_BINDIR})
        install(FILES deploy/rpi/event-store.development.json DESTINATION ${CMAKE_INSTALL_DATADIR}/ivi_dashboard/examples)
        install(TARGETS ivi_dashboard
            RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
        if(IVI_BUILD_EXPERIMENT_TOOLS)
            qt_add_executable(ivi_dashboard_experiment
                ui_qml/main.cpp ui_qml/dashboard_view_model.cpp ui_qml/dashboard_view_model.h)
            target_include_directories(ivi_dashboard_experiment PRIVATE hal service ui_qml)
            target_compile_definitions(ivi_dashboard_experiment PRIVATE IVI_EXPERIMENT_BUILD=1)
            target_link_libraries(ivi_dashboard_experiment PRIVATE ivi_event_journal
                ivi_core ivi_socketcan Qt6::Core Qt6::Gui Qt6::Qml Qt6::Quick Qt6::QuickControls2)
            qt_add_qml_module(ivi_dashboard_experiment
                URI IviDashboard VERSION 1.0 OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/experiment-qml"
                QML_FILES ui_qml/qml/Main.qml ui_qml/qml/SocGauge.qml)
            qt_add_resources(ivi_dashboard_experiment ivi_experiment_fonts
                PREFIX "/ivi-fonts" BASE "ui_qml/fonts"
                FILES ui_qml/fonts/NanumGothic-Regular.ttf ui_qml/fonts/OFL.txt)
        endif()
        if(IVI_BUILD_TESTS)
            add_executable(test_dashboard_view_model
                test/test_dashboard_view_model.cpp
                ui_qml/dashboard_view_model.cpp
                ui_qml/dashboard_view_model.h
            )
            target_include_directories(test_dashboard_view_model PRIVATE
                ${CMAKE_CURRENT_SOURCE_DIR}/hal
                ${CMAKE_CURRENT_SOURCE_DIR}/service
                ${CMAKE_CURRENT_SOURCE_DIR}/ui_qml
            )
            target_link_libraries(test_dashboard_view_model PRIVATE
                ivi_core
                Qt6::Core
                Qt6::Test
            )
            add_test(NAME test_dashboard_view_model COMMAND test_dashboard_view_model)
            if(CMAKE_SYSTEM_NAME STREQUAL "Linux" AND IVI_TEST_ECU_EXECUTABLE)
                if(NOT EXISTS "${IVI_TEST_ECU_EXECUTABLE}")
                    message(FATAL_ERROR "IVI_TEST_ECU_EXECUTABLE must reference an existing built ECU")
                endif()
                find_package(Python3 REQUIRED COMPONENTS Interpreter)
                add_test(NAME test_ecu_ivi_products COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_ecu_ivi_products.py
                    --ecu ${IVI_TEST_ECU_EXECUTABLE} --ivi $<TARGET_FILE:ivi_dashboard>
                    --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                    --out-parent ${CMAKE_CURRENT_BINARY_DIR}/product-test-results)
                set_tests_properties(test_ecu_ivi_products PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 25 RUN_SERIAL TRUE)
                add_test(NAME test_protection_event_product COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_protection_event_product.py
                    --ecu ${IVI_TEST_ECU_EXECUTABLE} --ivi $<TARGET_FILE:ivi_dashboard>
                    --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                    --out-parent ${CMAKE_CURRENT_BINARY_DIR}/protection-event-results)
                set_tests_properties(test_protection_event_product PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 90 RUN_SERIAL TRUE)
                add_test(NAME test_session_latency_product COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_session_latency_product.py
                    --ecu ${IVI_TEST_ECU_EXECUTABLE} --ivi $<TARGET_FILE:ivi_dashboard>
                    --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                    --out-parent ${CMAKE_CURRENT_BINARY_DIR}/session-latency-results)
                set_tests_properties(test_session_latency_product PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 20 RUN_SERIAL TRUE)
                add_test(NAME test_ecu_checkpoint_crash COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_ecu_checkpoint_crash.py
                    --ecu ${IVI_TEST_ECU_EXECUTABLE}
                    --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                    --out-parent ${CMAKE_CURRENT_BINARY_DIR}/checkpoint-test-results)
                set_tests_properties(test_ecu_checkpoint_crash PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 25 RUN_SERIAL TRUE)
                add_test(NAME test_managed_ecu_ids COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_managed_ecu_ids.py
                    --ecu ${IVI_TEST_ECU_EXECUTABLE} --ivi $<TARGET_FILE:ivi_dashboard>
                    --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                    --supervisor ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/scripts/supervise_ecu.py
                    --out-parent ${CMAKE_CURRENT_BINARY_DIR}/managed-ids-test-results)
                set_tests_properties(test_managed_ecu_ids PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 45 RUN_SERIAL TRUE)
                add_test(NAME test_ecu_supervisor_recovery COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_ecu_supervisor_recovery.py
                    --ecu ${IVI_TEST_ECU_EXECUTABLE}
                    --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                    --supervisor ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/scripts/supervise_ecu.py
                    --out-parent ${CMAKE_CURRENT_BINARY_DIR}/supervisor-test-results)
                set_tests_properties(test_ecu_supervisor_recovery PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 35 RUN_SERIAL TRUE)
                add_test(NAME test_rejection_roundtrip COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_ecu_ivi_products.py
                    --ecu ${IVI_TEST_ECU_EXECUTABLE} --ivi $<TARGET_FILE:ivi_dashboard>
                    --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                    --real-ids-check --ids-attack replay --rejection-check
                    --out-parent ${CMAKE_CURRENT_BINARY_DIR}/rejection-test-results)
                set_tests_properties(test_rejection_roundtrip PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 25 RUN_SERIAL TRUE)
                foreach(link_case IN ITEMS single ambiguous)
                    if(link_case STREQUAL "single")
                        set(link_arg --incident-link-check)
                    else()
                        set(link_arg --incident-ambiguous-check)
                    endif()
                    add_test(NAME test_incident_rejection_${link_case} COMMAND ${Python3_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_ecu_ivi_products.py
                        --ecu ${IVI_TEST_ECU_EXECUTABLE} --ivi $<TARGET_FILE:ivi_dashboard>
                        --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                        --real-ids-check --ids-attack replay --rejection-check ${link_arg}
                        --out-parent ${CMAKE_CURRENT_BINARY_DIR}/incident-link-test-results)
                    set_tests_properties(test_incident_rejection_${link_case} PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 25 RUN_SERIAL TRUE)
                endforeach()
                add_test(NAME test_session_ids_lifecycle COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_session_ids_products.py
                    --ecu ${IVI_TEST_ECU_EXECUTABLE} --ivi $<TARGET_FILE:ivi_dashboard>
                    --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                    --out-parent ${CMAKE_CURRENT_BINARY_DIR}/session-ids-lifecycle-results)
                set_tests_properties(test_session_ids_lifecycle PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 110 RUN_SERIAL TRUE)
                foreach(ids_case IN ITEMS normal fuzzy replay spoofing flooding)
                    set(ids_attack_args)
                    if(NOT ids_case STREQUAL "normal")
                        set(ids_attack_args --ids-attack ${ids_case})
                    endif()
                    add_test(NAME test_ecu_ivi_session_ids_${ids_case} COMMAND ${Python3_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_ecu_ivi_products.py
                        --ecu ${IVI_TEST_ECU_EXECUTABLE} --ivi $<TARGET_FILE:ivi_dashboard>
                        --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                        --real-ids-check ${ids_attack_args}
                        --out-parent ${CMAKE_CURRENT_BINARY_DIR}/session-ids-test-results)
                    set_tests_properties(test_ecu_ivi_session_ids_${ids_case} PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 25 RUN_SERIAL TRUE)
                endforeach()
                get_filename_component(ecu_fixture_dir "${IVI_TEST_ECU_EXECUTABLE}" DIRECTORY)
                if(EXISTS "${ecu_fixture_dir}/ecu_rx_fault_fixture")
                    add_test(NAME test_can_receive_recovery_product COMMAND ${Python3_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_bms_recovery_product.py --can-receive
                        --ecu ${ecu_fixture_dir}/ecu_rx_fault_fixture --ivi $<TARGET_FILE:ivi_dashboard>
                        --supervisor ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/scripts/supervise_ecu.py
                        --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                        --out-parent ${CMAKE_CURRENT_BINARY_DIR}/can-receive-recovery-results)
                    set_tests_properties(test_can_receive_recovery_product PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 35 RUN_SERIAL TRUE)
                    add_test(NAME test_can_receive_recovery_success_product COMMAND ${Python3_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_bms_recovery_product.py --can-receive --recover-once
                        --ecu ${ecu_fixture_dir}/ecu_rx_fault_fixture --ivi $<TARGET_FILE:ivi_dashboard>
                        --supervisor ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/scripts/supervise_ecu.py
                        --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                        --out-parent ${CMAKE_CURRENT_BINARY_DIR}/task-recovery-success-results)
                    set_tests_properties(test_can_receive_recovery_success_product PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 30 RUN_SERIAL TRUE)
                endif()
                if(EXISTS "${ecu_fixture_dir}/ecu_bms_recover_fixture")
                    add_test(NAME test_bms_recovery_success_product COMMAND ${Python3_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_bms_recovery_product.py --recover-once
                        --ecu ${ecu_fixture_dir}/ecu_bms_recover_fixture --ivi $<TARGET_FILE:ivi_dashboard>
                        --supervisor ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/scripts/supervise_ecu.py
                        --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                        --out-parent ${CMAKE_CURRENT_BINARY_DIR}/task-recovery-success-results)
                    set_tests_properties(test_bms_recovery_success_product PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 30 RUN_SERIAL TRUE)
                endif()
                if(EXISTS "${ecu_fixture_dir}/ecu_bms_fault_fixture")
                    add_test(NAME test_bms_recovery_product COMMAND ${Python3_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_bms_recovery_product.py
                        --ecu ${ecu_fixture_dir}/ecu_bms_fault_fixture --ivi $<TARGET_FILE:ivi_dashboard>
                        --supervisor ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/scripts/supervise_ecu.py
                        --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                        --out-parent ${CMAKE_CURRENT_BINARY_DIR}/bms-recovery-results)
                    set_tests_properties(test_bms_recovery_product PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 35 RUN_SERIAL TRUE)
                    add_test(NAME test_bms_unreclaimed_product COMMAND ${Python3_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_bms_recovery_product.py
                        --ecu ${ecu_fixture_dir}/ecu_bms_stall_fixture --ivi $<TARGET_FILE:ivi_dashboard> --unreclaimed
                        --supervisor ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/scripts/supervise_ecu.py
                        --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                        --out-parent ${CMAKE_CURRENT_BINARY_DIR}/bms-recovery-results)
                    set_tests_properties(test_bms_unreclaimed_product PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 35 RUN_SERIAL TRUE)
                endif()
                foreach(restart_test IN ITEMS deadline receipt cooling)
                    set(restart_peer_args)
                    if(NOT restart_test STREQUAL "deadline")
                        set(restart_peer_args --ivi $<TARGET_FILE:ivi_dashboard>)
                    endif()
                    if(restart_test STREQUAL "cooling")
                        list(APPEND restart_peer_args --cooling)
                    endif()
                    add_test(NAME test_ecu_restart_${restart_test} COMMAND ${Python3_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/../common/test_ecu_restart_product.py
                        --ecu ${IVI_TEST_ECU_EXECUTABLE} ${restart_peer_args}
                        --policy ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/data/session-v2-development.conf
                        --supervisor ${CMAKE_CURRENT_SOURCE_DIR}/../adaptive_ecu/scripts/supervise_ecu.py
                        --out-parent ${CMAKE_CURRENT_BINARY_DIR}/restart-test-results)
                    set_tests_properties(test_ecu_restart_${restart_test} PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 25 RUN_SERIAL TRUE)
                endforeach()
            endif()
        endif()
    else()
        message(STATUS "Qt 6 not found: ivi_core and tests remain available")
    endif()
endif()
