import numpy as np
import pytest

from observable_extraction.core.photon_multiplicity import (
    compare_multiplicity_selections,
)
from observable_extraction.io.reconstructed_events import EventArrays


def _events():
    count = 8
    zeros4 = np.zeros((count, 4))
    return EventArrays(
        run_number=np.ones(count, dtype=int),
        xstrip=np.ones(count, dtype=int),
        polarization=np.array([1, 2, 1, 2, 1, 2, 1, 2]),
        beam_energy_gev=np.full(count, 1.2),
        eta=zeros4.copy(),
        pi0=zeros4.copy(),
        proton=zeros4.copy(),
        missing_mass_gev=np.zeros(count),
        eta_mass_gev=np.zeros(count),
        pi0_mass_gev=np.zeros(count),
        bdt_score=np.ones(count),
        n_photons_input=np.array([4, 4, 4, 4, 4, 5, 5, 6]),
    )


def test_multiplicity_study_reports_exactly_four_shift():
    def estimator(events):
        return np.array([np.mean(events.polarization == 1)])

    result = compare_multiplicity_selections(_events(), estimator)

    assert result.inclusive_count == 8
    assert result.exactly_four_count == 5
    assert result.exactly_four_fraction == pytest.approx(5 / 8)
    np.testing.assert_allclose(
        result.sigma_shift,
        result.sigma_exactly_four - result.sigma_inclusive,
    )
    assert result.best_quartet_resolved is False


def test_multiplicity_study_rejects_sample_without_exactly_four_events():
    events = _events().take(np.array([False, False, False, False, False, True, True, True]))

    with pytest.raises(ValueError, match="exactly-four sample is empty"):
        compare_multiplicity_selections(events, lambda selected: np.array([0.0]))
