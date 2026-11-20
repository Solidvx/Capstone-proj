"""Raw vector checks without installing scipy or inventing SOC labels."""
from copy import deepcopy
import pytest
from tools.quality.nasa_data import inspect_cycle


def data():
    return dict(Time=[0,10,20],Voltage_measured=[4.2,4.1,4],Current_measured=[0,-2,-2],
        Temperature_measured=[25.1,25.2,25.3],Capacity=1.5,Current_load=[0,2,2])


def test_raw_units_sign_fractional_temperature_and_time_are_preserved():
    original=data();before=deepcopy(original);report,values=inspect_cycle(original)
    assert original==before and values=={k:original[k] for k in values}
    assert report['samples']==3 and report['min_gap_s']==report['max_gap_s']==10
    assert report['measured_current_trapezoid_ah']==pytest.approx(-30/3600)
    assert report['raw_fields']==sorted(original)
    assert not report['soc_named_field_present'] and not report['soc_ground_truth_established']


@pytest.mark.parametrize('damage',['missing','length','nan','infinity','duplicate','backward','negative',
    'scalar','nested','extra_length','capacity_nan'])
def test_raw_corruption_is_rejected_without_trimming(damage):
    value=data()
    if damage=='missing':value.pop('Voltage_measured')
    elif damage=='length':value['Temperature_measured'].pop()
    elif damage=='nan':value['Voltage_measured'][0]=float('nan')
    elif damage=='infinity':value['Current_measured'][1]=float('inf')
    elif damage=='duplicate':value['Time'][1]=0
    elif damage=='backward':value['Time'][2]=9
    elif damage=='negative':value['Time'][0]=-1
    elif damage=='scalar':value['Time']=1
    elif damage=='nested':value['Time']=[[0],[10],[20]]
    elif damage=='extra_length':value['Current_load']=[0,2]
    elif damage=='capacity_nan':value['Capacity']=float('nan')
    with pytest.raises(ValueError):inspect_cycle(value)
