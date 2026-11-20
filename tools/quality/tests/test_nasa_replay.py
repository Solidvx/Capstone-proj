"""Numerical reconstruction/loader boundaries, not a battery truth model."""
import math
from copy import deepcopy
import pytest
from tools.quality.nasa_replay import Reconstruction,resample,score_loaded,float32,temperature


def source():
    return dict(Time=[0,.15,.3,1],Voltage_measured=[4.2,4.1,4,3.9],
        Current_measured=[0,-2,-1,-3],Temperature_measured=[25.1,25.6,26.1,26.6])


@pytest.mark.parametrize('mode,expected',[('linear',-1.775),('previous',-1.)])
def test_irregular_raw_knot_crossings_preserve_declared_charge(mode,expected):
    data=source();before=deepcopy(data)
    rows,stats=resample(data,mode,10)
    assert data==before and len(rows)==10
    assert [r[0] for r in rows]==[k/10 for k in range(1,11)]
    assert stats['reference_reconstruction_charge_ah']==pytest.approx(expected/3600,abs=1e-16)
    assert stats['resampled_charge_ah']==pytest.approx(expected/3600,abs=1e-16)
    assert stats['absolute_conservation_error_ah']<1e-16
    assert stats['operational_gap_limit_adopted'] is None


def test_interval_mean_not_naive_endpoint_current_preserves_steps():
    rows,stats=resample(source(),'previous',10)
    assert rows[1][2]==pytest.approx(-1.) # 0.1..0.2 crosses step at0.15.
    assert stats['endpoint_current_error_ah']!=0
    assert stats['absolute_conservation_error_ah']<1e-16


def test_two_candidates_are_not_same_physical_truth():
    _,linear=resample(source(),'linear',10);_,previous=resample(source(),'previous',10)
    assert linear['reference_reconstruction_charge_ah']!=previous['reference_reconstruction_charge_ah']
    assert 'physical current between raw samples' in linear['not_claimed']


@pytest.mark.parametrize('bounds',[(0,1.1),(-.1,.2),(.2,.2),(.5,.4),(math.nan,1)])
def test_no_extrapolation_or_empty_integral(bounds):
    with pytest.raises(ValueError):Reconstruction(source(),'linear').integral(*bounds)


@pytest.mark.parametrize('count',[0,36001,True,1.5])
def test_bounded_grid_and_full_input_coverage(count):
    with pytest.raises(ValueError):resample(source(),'linear',count)


def test_gap_nan_time_regression_and_missing_t0_are_not_repaired():
    for damage in ('short','start','nan','reverse'):
        data=source()
        if damage=='start':data['Time'][0]=.01
        elif damage=='nan':data['Voltage_measured'][1]=math.nan
        elif damage=='reverse':data['Time'][1]=0
        with pytest.raises(ValueError):resample(data,'linear',11 if damage=='short' else 10)


def test_native_float32_and_temperature_loss_are_explicit():
    rows=[(.1,4.181907184700754,-1.9969349193365222,26.5),(.2,4,-2,-9.5),(.3,4,-2,70.6)]
    loaded=[dict(zip(('voltage_v','current_a','temperature_c'),map(str,(float32(v),float32(i),temperature(t))))) for _,v,i,t in rows]
    report=score_loaded(rows,loaded)
    assert report['rows_verified']==3 and report['temperature_changed_rows']==3
    assert [int(r['temperature_c']) for r in loaded]==[27,-10,70]
    assert report['temperature_max_abs_error_c']==pytest.approx(.6)
    assert report['temperature_outside_product_range_rows']==1
    assert report['max_voltage_float_error_v']>0
    loaded[0]['temperature_c']='26'
    with pytest.raises(ValueError):score_loaded(rows,loaded)


def test_loader_missing_extra_and_nonfinite_rows_are_invalid():
    rows,_=resample(source(),'linear',10)
    loaded=[dict(zip(('voltage_v','current_a','temperature_c'),map(str,(float32(v),float32(i),temperature(t))))) for _,v,i,t in rows]
    for damage in ('missing','extra','nan'):
        values=deepcopy(loaded)
        if damage=='missing':values.pop()
        elif damage=='extra':values[0]['unexpected']='0'
        elif damage=='nan':values[0]['voltage_v']='nan'
        with pytest.raises(ValueError):score_loaded(rows,values)
