"""ROOT-free reconstruction decisions and output-vector contracts."""

from types import SimpleNamespace

import numpy as np
import pytest

from graal_common.physics.pairing import Pairing
from reconstruction.core import reco_physics as rp
from reconstruction.core.event_logic import (
    EventInput,
    ReconstructedEvent,
    RejectionReason,
    reconstruct_event,
)
from reconstruction.core.kinematic_fit import (
    PROTON_TARGET_REACTION,
    FitCovariance,
    FitResult,
)


PAIRING = Pairing(heavy=(2, 3), light=(0, 1))
FIT_PAIRING = Pairing(heavy=(0, 1), light=(2, 3))


def _event(*, beam_energy: float = 1.5) -> EventInput:
    return EventInput(
        photons=np.array(
            [
                [0.10, 0.00, 0.20, 0.30],
                [-0.10, 0.00, 0.20, 0.30],
                [0.00, 0.05, 0.10, 0.15],
                [0.00, -0.05, 0.10, 0.15],
            ]
        ),
        proton=np.array([0.0, 0.0, 0.0, rp.M_PROTON]),
        neutron=np.array([0.0, 0.0, 0.0, 0.0]),
        beam=np.array([0.0, 0.0, beam_energy, beam_energy]),
        run_number=4242,
        polarization=2,
        strip=73.0,
    )


def _config(**overrides):
    values = {
        "chi2_cut": 10.0,
        "partner_mass": rp.M_PROTON,
        "missing_mass_window": None,
        "do_fit": False,
        "fit_cl": 0.01,
        "fit_cov": FitCovariance(),
        "fit_reaction": PROTON_TARGET_REACTION,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _pairing_with(chi2: float):
    def pair(_photons, _hypothesis):
        return PAIRING, chi2

    return pair


def _fit_must_not_run(*_args, **_kwargs):
    raise AssertionError("fit must not run")


def test_accepted_event_contains_ordered_raw_vectors_masses_and_metadata():
    event = _event()

    result = reconstruct_event(
        event,
        rp.ETA_PI0,
        _config(),
        pairing_fn=_pairing_with(2.5),
        fit_fn=_fit_must_not_run,
    )

    assert isinstance(result, ReconstructedEvent)
    assert result.pairing == PAIRING
    assert result.chi2 == 2.5
    np.testing.assert_array_equal(
        result.photons,
        event.photons[[2, 3, 0, 1]],
    )
    np.testing.assert_array_equal(result.heavy, [0.0, 0.0, 0.2, 0.3])
    np.testing.assert_array_equal(result.light, [0.0, 0.0, 0.4, 0.6])
    np.testing.assert_allclose(
        result.missing,
        [0.0, 0.0, 0.9, 1.538272],
        rtol=0.0,
        atol=1e-15,
    )
    assert result.heavy_mass == pytest.approx(0.22360679774997896)
    assert result.light_mass == pytest.approx(0.4472135954999579)
    np.testing.assert_array_equal(result.beam, event.beam)
    np.testing.assert_array_equal(result.proton, event.proton)
    np.testing.assert_array_equal(result.neutron, event.neutron)
    assert result.run_number == 4242
    assert result.polarization == 2
    assert result.strip == 73.0
    assert result.fitted_photons is None
    assert result.fitted_proton is None
    assert result.fitted_heavy is None
    assert result.fitted_light is None
    assert result.fit_chi2 is None
    assert result.fit_ndf is None
    assert result.fit_converged is None


def test_mass_rounding_matches_tlorentzvector_operation_order():
    event = _event(beam_energy=2.0)
    heavy = np.array(
        [-0.5388685318452232, 0.03039689594953349, 0.0026555324871548034, 1.6011062972737309]
    )
    event.photons[0] = heavy / 2.0
    event.photons[1] = heavy / 2.0
    event.photons[2:] = 0.0

    result = reconstruct_event(
        event,
        rp.ETA_PI0,
        _config(),
        pairing_fn=lambda _photons, _hypothesis: (
            Pairing(heavy=(0, 1), light=(2, 3)),
            0.0,
        ),
        fit_fn=_fit_must_not_run,
    )

    assert isinstance(result, ReconstructedEvent)
    assert result.heavy_mass == 1.5073921379058646


def test_chi_square_rejection_happens_before_other_physics_decisions():
    result = reconstruct_event(
        _event(beam_energy=0.1),
        rp.ETA_PI0,
        _config(chi2_cut=10.0, do_fit=True),
        pairing_fn=_pairing_with(10.0),
        fit_fn=_fit_must_not_run,
    )

    assert result is RejectionReason.CHI_SQUARE


def test_impossible_energy_rejection_happens_before_fit():
    result = reconstruct_event(
        _event(beam_energy=0.2),
        rp.ETA_PI0,
        _config(do_fit=True),
        pairing_fn=_pairing_with(0.0),
        fit_fn=_fit_must_not_run,
    )

    assert result is RejectionReason.IMPOSSIBLE_ENERGY


def test_missing_mass_rejection_applies_only_without_fit():
    result = reconstruct_event(
        _event(),
        rp.ETA_PI0,
        _config(partner_mass=3.0, missing_mass_window=0.01),
        pairing_fn=_pairing_with(0.0),
        fit_fn=_fit_must_not_run,
    )

    assert result is RejectionReason.MISSING_MASS


@pytest.mark.parametrize(
    "fit_result",
    [
        FitResult(
            fitted_photons=np.zeros((4, 4)),
            fitted_proton=np.zeros(4),
            chi2=1.0,
            ndf=6,
            converged=False,
            fitted_cov=np.ones(16),
        ),
        FitResult(
            fitted_photons=np.zeros((4, 4)),
            fitted_proton=np.zeros(4),
            chi2=100.0,
            ndf=6,
            converged=True,
            fitted_cov=np.ones(16),
        ),
    ],
    ids=("not-converged", "confidence-level"),
)
def test_fit_rejection_covers_nonconvergence_and_confidence_level(fit_result):
    result = reconstruct_event(
        _event(),
        rp.ETA_PI0,
        _config(do_fit=True, fit_cl=0.01),
        pairing_fn=_pairing_with(0.0),
        fit_fn=lambda *_args, **_kwargs: fit_result,
    )

    assert result is RejectionReason.FIT


def test_accepted_fit_preserves_fit_arguments_and_vectors():
    event = _event()
    config = _config(do_fit=True, fit_cl=0.0)
    fitted_photons = np.array(
        [
            [1.0, 0.0, 0.0, 1.0],
            [0.0, 1.0, 0.0, 1.0],
            [0.0, 0.0, 1.0, 1.0],
            [-1.0, 0.0, 0.0, 1.0],
        ]
    )
    fitted_proton = np.array([0.1, 0.2, 0.3, 1.1])
    observed = {}

    def fit(photons, proton, beam, pairing, hypothesis, covariance, *, reaction):
        observed.update(
            photons=photons,
            proton=proton,
            beam=beam,
            pairing=pairing,
            hypothesis=hypothesis,
            covariance=covariance,
            reaction=reaction,
        )
        return FitResult(
            fitted_photons=fitted_photons,
            fitted_proton=fitted_proton,
            chi2=6.0,
            ndf=6,
            converged=True,
            fitted_cov=np.ones(16),
        )

    result = reconstruct_event(
        event,
        rp.ETA_PI0,
        config,
        pairing_fn=_pairing_with(0.0),
        fit_fn=fit,
    )

    assert isinstance(result, ReconstructedEvent)
    np.testing.assert_array_equal(observed["photons"], event.photons[[2, 3, 0, 1]])
    np.testing.assert_array_equal(observed["proton"], event.proton)
    np.testing.assert_array_equal(observed["beam"], event.beam)
    assert observed["pairing"] == FIT_PAIRING
    assert observed["hypothesis"] is rp.ETA_PI0.hypothesis
    assert observed["covariance"] is config.fit_cov
    assert observed["reaction"] is config.fit_reaction
    np.testing.assert_array_equal(result.fitted_photons, fitted_photons)
    np.testing.assert_array_equal(result.fitted_proton, fitted_proton)
    np.testing.assert_array_equal(result.fitted_heavy, [1.0, 1.0, 0.0, 2.0])
    np.testing.assert_array_equal(result.fitted_light, [-1.0, 0.0, 1.0, 2.0])
    assert result.fit_chi2 == 6.0
    assert result.fit_ndf == 6
    assert result.fit_converged is True
