"""The public engine is shared by the command line and diagnostic consumers."""
from dataclasses import fields
import inspect

import numpy as np

from observable_extraction import beam_asymmetry, compare_gate, extraction
from observable_extraction.core.models import FluxExposure
from observable_extraction.samples import SAMPLES, SampleInput
from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events


def test_public_extraction_bundle_and_sample_contract():
    assert [field.name for field in fields(extraction.ExtractionBundle)] == [
        'points', 'ratio_objects', 'binning_candidates', 'candidate_ratio_objects']
    empty = extraction.ExtractionBundle((), ())
    assert all(isinstance(getattr(empty, field.name), tuple) for field in fields(empty))
    assert SAMPLES == {'raw': SampleInput('reco_eta_pi0_chi2', False),
                       'raw_bdt': SampleInput('reco_eta_pi0_bdt', True)}
    assert beam_asymmetry.extract_sample is extraction.extract_sample
    assert compare_gate.extract_sample is extraction.extract_sample
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in
               inspect.signature(extraction.extract_sample).parameters.values())


def test_public_engine_freezes_selected_phi_map_and_preserves_missing_bins():
    options = dict(sample_name='raw_bdt', events=_synthetic_events(phi_bins=48),
                   exposures={(811, 17): FluxExposure(811, 17, 1.15, 1.2, .9, .2, .6, .55)},
                   estimator='both', retain_ratio_objects=True,
                   energy_edges=np.array([1.1, 1.2, 1.3]))
    best = extraction.extract_sample(**options, best_binning=True)
    choices = {(p.point.pair, p.point.energy_bin, p.point.mass_bin): p.phi_bins
               for p in best.points if p.estimator == 'ratio'}
    fixed = extraction.extract_sample(**options, selected_phi_bins=choices)
    assert fixed.points == best.points
    assert len(best.binning_candidates) == len(best.candidate_ratio_objects) == 9
    assert fixed.binning_candidates == fixed.candidate_ratio_objects == ()
    for actual, expected in zip(fixed.ratio_objects, best.ratio_objects):
        for field in fields(actual):
            np.testing.assert_equal(getattr(actual, field.name), getattr(expected, field.name))
    missing_key = next(iter(choices))
    del choices[missing_key]
    missing = extraction.extract_sample(**options, selected_phi_bins=choices)
    assert missing.points == tuple(p for p in best.points if
        p.estimator != 'ratio' or (p.point.pair, p.point.energy_bin, p.point.mass_bin) != missing_key)
    assert len(missing.ratio_objects) == 2
    assert extraction.extract_sample(**{**options, 'estimator': 'ratio'},
                                     selected_phi_bins={}).points == ()
