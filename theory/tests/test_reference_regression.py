import json
from pathlib import Path

from graal_theory.models.eta_pi0_p import EtaPi0PModel
from graal_theory.observables import HistogramSpec, predict_energy
from graal_theory.phase_space import SobolConfig
from graal_theory.validation import (
    compare_factor_two,
    load_figure14_reference,
    load_figure19_reference,
    validate_figure14_tree,
)


REFERENCES = Path(__file__).resolve().parents[1] / "references"


def test_published_tree_curve_and_factor_two_regression():
    model = EtaPi0PModel.from_files(REFERENCES / "central_parameters.json", REFERENCES / "sources.json")
    metadata = json.loads((REFERENCES / "digitization.json").read_text())
    config = SobolConfig(power=16)
    spectrum = predict_energy(1.2, model, config, HistogramSpec(bins=16))
    nearby = predict_energy(1.202, model, config, HistogramSpec(bins=16))
    curve = load_figure14_reference(REFERENCES, metadata)
    full = load_figure19_reference(REFERENCES)
    curve_result = validate_figure14_tree(spectrum.histograms["eta_p"], curve)
    ratio_result = compare_factor_two(
        nearby.partial_cross_section_microbarn,
        full,
        digitization_absolute_uncertainty=metadata["figure19_total_1202"]["absolute_uncertainty_microbarn"],
    )
    assert curve_result.passed, curve_result
    assert ratio_result.passed, ratio_result
