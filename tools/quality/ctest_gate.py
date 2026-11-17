"""Reject missing tests and unexpected skips; preserve CTest JUnit evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

EXPECTED = {
    'ecu': set(('publisher mock_can_driver sensor_simulator ads1115_conversion sensor_quality '
                'adc_acquisition_gate ads1115_registers ads1115_sample ads1115_acquirer '
                'hardware_sample_feed can_publisher ekf_soc soh_estimator failsafe_sm '
                'watchdog_manager task_recovery secoc can_session_candidate can_session_exchange '
                'can_session_receiver can_diagnostic ids_diagnostic_socket can_session_vcan '
                'ecu_session_product can_receive_lifecycle failsafe_profile bms_calculation_task soc_profile_product '
                'ina219_acquirer ds18b20_acquirer physical_battery_meter bounded_sensor_read physical_capture_cli').split()),
    'ivi': set(('can_frame_validator can_parser receive_retry_policy secoc_verifier '
                'vehicle_data_service vehicle_data_service_security vehicle_data_service_state '
                'secoc_runtime unprotected_test_receiver socketcan_receiver dashboard_security '
                'dashboard_view_model latency_recorder can_session_candidate can_session_exchange '
                'can_session_receiver can_diagnostic can_session_vcan vehicle_data_session '
                'event_journal event_history_product').split()),
}

VCAN_TESTS = {
    'ecu': {'test_can_session_vcan', 'test_ecu_session_product', 'test_can_receive_lifecycle'},
    'ivi': {'test_socketcan_receiver', 'test_can_session_vcan'},
}

# This profile requires the real ECU binary and all recovery fixtures at CMake
# configure time. Missing fixtures must fail inventory validation, not silently
# reduce the product acceptance suite.
EXPECTED['ivi-integrated'] = EXPECTED['ivi'] | set((
    'ecu_ivi_products protection_event_product session_latency_product ecu_checkpoint_crash managed_ecu_ids ecu_supervisor_recovery '
    'rejection_roundtrip incident_rejection_single incident_rejection_ambiguous '
    'session_ids_lifecycle ecu_ivi_session_ids_normal ecu_ivi_session_ids_fuzzy '
    'ecu_ivi_session_ids_replay ecu_ivi_session_ids_spoofing ecu_ivi_session_ids_flooding '
    'can_receive_recovery_product can_receive_recovery_success_product bms_recovery_success_product bms_recovery_product bms_unreclaimed_product '
    'ecu_restart_deadline ecu_restart_receipt ecu_restart_cooling').split())
VCAN_TESTS['ivi-integrated'] = set()  # Product acceptance requires a working vcan.


def validate_names(names, component):
    expected = {'test_' + name for name in EXPECTED[component]}
    if len(names) != len(set(names)) or set(names) != expected:
        raise ValueError(f'test inventory mismatch: expected {sorted(expected)}, got {sorted(names)}')


def validate_junit(root, component, allow_no_vcan):
    cases = list(root.iter('testcase'))
    validate_names([case.get('name') for case in cases], component)
    skipped = []
    for case in cases:
        if case.find('failure') is not None or case.find('error') is not None:
            raise ValueError(f"failed test: {case.get('name')}")
        if case.find('skipped') is not None:
            if not (allow_no_vcan and case.get('name') in VCAN_TESTS[component]):
                raise ValueError(f"unexpected skip: {case.get('name')}")
            skipped.append(case.get('name'))
    return {'status': 'PASS_WITH_EXPLICIT_SKIP' if skipped else 'PASS',
            'executed': len(cases) - len(skipped), 'skipped': skipped}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--component', choices=EXPECTED, required=True)
    p.add_argument('--allow-no-vcan', action='store_true')
    args = p.parse_args()
    try:
        build = args.build.resolve()
        listing = subprocess.check_output(['ctest', '--test-dir', str(build), '--show-only=json-v1'], text=True)
        validate_names([test['name'] for test in json.loads(listing)['tests']], args.component)
        junit = build / 'Testing/quality-junit.xml'
        junit.parent.mkdir(exist_ok=True)
        result = subprocess.run(['ctest', '--test-dir', str(build), '--output-on-failure',
                                 '--no-tests=error', '--timeout', '60', '--output-junit', str(junit)])
        if result.returncode:
            raise ValueError(f'CTest returned {result.returncode}')
        print(json.dumps(validate_junit(ET.parse(junit).getroot(), args.component, args.allow_no_vcan)))
        return 0
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'FAIL', 'reason': str(error)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
