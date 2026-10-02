cmake_minimum_required(VERSION 3.22)

project(ivi_platform LANGUAGES CXX)

include(GNUInstallDirs)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(IVI_BUILD_TESTS "Build IVI core tests" ON)
option(IVI_BUILD_QT_APP "Build the Qt Quick dashboard when Qt 6 is available" ON)

find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)

add_library(ivi_core
    hal/can_frame_validator.cpp
    hal/can_parser.cpp
    hal/secoc_verifier.cpp
    service/vehicle_data_service.cpp
)
target_include_directories(ivi_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/hal
    ${CMAKE_CURRENT_SOURCE_DIR}/service
)
target_link_libraries(ivi_core PUBLIC OpenSSL::Crypto Threads::Threads)

add_library(ivi_socketcan hal/socketcan_receiver.cpp)
target_include_directories(ivi_socketcan PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/hal)
target_link_libraries(ivi_socketcan PUBLIC ivi_core Threads::Threads)

if(IVI_BUILD_TESTS)
    enable_testing()
    foreach(test_name IN ITEMS
            test_can_frame_validator
            test_can_parser
            test_receive_retry_policy
            test_secoc_verifier
            test_vehicle_data_service
            test_vehicle_data_service_security
            test_vehicle_data_service_state
            test_secoc_runtime)
        add_executable(${test_name} test/${test_name}.cpp)
        target_include_directories(${test_name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/test)
        target_link_libraries(${test_name} PRIVATE ivi_core)
        add_test(NAME ${test_name} COMMAND ${test_name})
    endforeach()
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
        if(IVI_BUILD_TESTS)
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
            QML_FILES ui_qml/qml/Main.qml
        )
        install(TARGETS ivi_dashboard
            RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
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
        endif()
    else()
        message(STATUS "Qt 6 not found: ivi_core and tests remain available")
    endif()
endif()
