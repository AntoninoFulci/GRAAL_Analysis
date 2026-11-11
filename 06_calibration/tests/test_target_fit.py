"""Independent synthetic closure and identifiability boundaries."""
import numpy as np
import pytest

from calibration.target_fit import fit_length, observed_xy, select_vertices


def test_length_closure_with_background_and_resolution():
    rng = np.random.default_rng(27)
    # Independent event generator: a 6 cm uniform cell, Gaussian measurement
    # noise, then uniform background. Not sampled from the fit's bin model.
    z = np.r_[rng.uniform(-2.8, 3.2, 20000) + rng.normal(0, .2, 20000),
              rng.uniform(-10, 10, 1000)]
    result = fit_length(z, bootstrap=8, seed=7)
    assert result['length_cm'] == pytest.approx(6., abs=.15)
    assert result['center_cm'] == pytest.approx(.2, abs=.08)
    assert result['length_stat_error_cm'] > 0
    assert result['resolution_status'] == 'effective_fit_width_not_detector_calibration'


@pytest.mark.parametrize('length',[3.,11.1])
def test_other_cell_lengths_are_not_forced_to_six_cm(length):
    rng = np.random.default_rng(91)
    z = rng.uniform(-length/2,length/2,10000)+rng.normal(0,.2,10000)-.5
    result = fit_length(z,bootstrap=0)
    assert result['length_cm'] == pytest.approx(length,abs=.15)
    assert result['center_cm'] == pytest.approx(-.5,abs=.08)


def test_sparse_sample_has_no_invented_length():
    result = fit_length(np.array([0., .1, -.1]), bootstrap=0)
    assert result['status'] == 'insufficient_statistics'
    assert result['length_cm'] is None
    assert result['length_stat_error_cm'] is None


def test_background_saturation_is_flagged_as_boundary_fit():
    rng = np.random.default_rng(123)
    z = np.r_[rng.uniform(-3,3,3000)+rng.normal(0,.2,3000),rng.uniform(-15,15,10000)]
    result = fit_length(z,bootstrap=0)
    assert result['background_fraction'] == pytest.approx(.7)
    assert result['status'] == 'fit_at_boundary'


def test_xy_width_is_not_target_diameter_or_unfolded_beam():
    rng = np.random.default_rng(81)
    xy = rng.normal([.5, .1], [.4, .25], (10000, 2))
    result = observed_xy(xy)
    assert result['median_cm'] == pytest.approx([.5, .1], abs=.03)
    assert result['sigma68_cm'] == pytest.approx([.4, .25], abs=.03)
    assert result['target_diameter_cm'] is None
    assert result['true_beam_covariance_cm2'] is None
    assert np.sum(result['counts']) == 10000


def test_selection_uses_dca_not_coordinate_position_and_one_pair_per_event():
    data = {'status': np.array([0, 0, 0, 4]), 'n_charged': np.array([2, 2, 3, 2]),
            'dca_cm': np.array([.39, .41, .1, np.nan]),
            'x_cm': np.array([10., 0, 0, np.nan]), 'y_cm': np.zeros(4), 'z_cm': np.zeros(4),
            'source_file': np.zeros(4, dtype=int), 'source_entry': np.arange(4)}
    assert select_vertices(data, dca_max_cm=.4).tolist() == [True, False, False, False]
    data['dca_cm'][1] = .1
    data['source_entry'][1] = 0
    with pytest.raises(ValueError, match='duplicate'):
        select_vertices(data, dca_max_cm=.4)
