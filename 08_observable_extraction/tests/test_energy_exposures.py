"""Explicit strip exposure construction never borrows masked calibration."""
from dataclasses import asdict

import numpy as np
import pytest

from observable_extraction.calibration.energy_exposures import build_projected_exposures


def _state(value=10., offset=0.):
    return dict(values=np.full(128, value), calibration_edges=np.linspace(1., 1.6, 129) + offset)


def _projected(run=811, state="POL1", value=15., offset=.02):
    return dict(**_state(value, offset), run=run, state=state,
                strip_indices=np.arange(1, 129),
                axis_source=dict(kind="inclusive_h80_calibration", input_sha256="independent"),
                audit=dict(destination_covered=True, destination_integral=128 * value,
                           source_integral=128 * value, lower_tail=0., upper_tail=0.))


def test_missing_pol_uses_projected_axis_and_retains_measured_runs():
    measured = {(811, "POL2"): _state(20.), (812, "POL1"): _state(), (812, "POL2"): _state()}
    result, audit = build_projected_exposures(measured, {(811, "POL1"): _projected()},
        polarization_model=lambda energy: energy / 2., energy_range=(1.1, 1.5))
    item = result[(811, 30)]
    native = 1. + 29.5 * .6 / 128
    assert item.flux_vertical == 15.
    assert item.flux_horizontal == 20.
    assert item.energy_gev == pytest.approx(native + .01)
    assert item.polarization_vertical == pytest.approx((native + .02) / 2.)
    assert item.polarization_horizontal == pytest.approx(native / 2.)
    assert item.flux_brem is None and item.brem_status == "missing"
    assert (812, 30) in result
    assert audit["811"]["states"]["POL1"]["axis_source"]["input_sha256"] == "independent"
    assert audit["811"]["states"]["POL1"]["audit"]["lower_tail"] == 0.


def test_measured_replacement_requires_explicit_closure_and_never_reads_hidden_fields():
    # The hidden state's opaque payload would fail any attempted conversion.
    measured = {(811, "POL1"): {"values": object(), "calibration_edges": object()},
                (811, "POL2"): _state()}
    projected = {(811, "POL1"): _projected()}
    with pytest.raises(ValueError, match="replace_measured"):
        build_projected_exposures(measured, projected, polarization_model=lambda energy: .5)
    result, audit = build_projected_exposures(measured, projected,
        polarization_model=lambda energy: .5, replace_measured=True)
    assert result[(811, 30)].flux_vertical == 15.
    assert audit["811"]["states"]["POL1"]["status"] == "projected"


@pytest.mark.parametrize("bad", [dict(values=np.zeros(128)), dict(values=np.full(128, np.nan)),
                                  dict(axis_source={}), dict(audit={"destination_covered": False}),
                                  dict(run=812), dict(strip_indices=np.arange(128))])
def test_invalid_projection_is_audited_without_borrowing_measured_state(bad):
    projected = _projected()
    projected.update(bad)
    result, audit = build_projected_exposures({(811, "POL2"): _state()},
        {(811, "POL1"): projected}, polarization_model=lambda energy: .5)
    assert result == {}
    assert audit["811"]["status"] == "no_valid_exposure"
    assert audit["811"]["states"]["POL1"]["status"] == "invalid_projection"
    assert audit["811"]["problems"]


def test_estimated_brem_never_enters_measured_control_denominator():
    result, audit = build_projected_exposures(
        {(811, "POL1"): _state(), (811, "POL2"): _state()},
        {(811, "BREM"): _projected(state="BREM")}, polarization_model=lambda energy: .5)
    assert result[(811, 30)].brem_status == "estimated"
    assert result[(811, 30)].flux_brem == 15.
    assert audit["811"]["exposure"]["brem_strata"] == 0


def test_complete_measured_states_match_native_loader_values():
    result, _ = build_projected_exposures({(811, state): _state(value)
        for state, value in (("POL1", 120.), ("POL2", 80.), ("BREM", 25.))}, {},
        polarization_model=lambda energy: .5)
    assert asdict(result[(811, 30)]) == dict(run_number=811, xstrip=30,
        energy_gev=pytest.approx(1. + 29.5 * .6 / 128), flux_vertical=120.,
        flux_horizontal=80., flux_brem=25., polarization_vertical=.5,
        polarization_horizontal=.5, brem_status="measured_valid")


def test_present_defective_state_cannot_be_replaced_even_for_closure():
    with pytest.raises(ValueError, match="defective"):
        build_projected_exposures({(811, "POL1"): dict(status="invalid_content")},
            {(811, "POL1"): _projected()}, polarization_model=lambda energy: .5, replace_measured=True)
