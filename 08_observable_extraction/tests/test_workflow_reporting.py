"""Publication ordering and routing at the single-result workflow boundary."""
from dataclasses import replace

import pytest

from observable_extraction import beam_asymmetry, workflow
from observable_extraction.core.models import FluxExposure
from observable_extraction.io.root_input import read_output_points, read_output_contract
from observable_extraction.samples import SAMPLES
from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events


@pytest.mark.parametrize("fail_first_plot", [False, True])
def test_root_precedes_reports_and_plot_failure_preserves_it(tmp_path, monkeypatch, capsys,
                                                            fail_first_plot):
    output, plots = tmp_path / "output", tmp_path / "plots"
    args = beam_asymmetry.build_parser().parse_args([
        "--raw-bdt", str(tmp_path / "nominal.root"),
        "--raw", str(tmp_path / "missing-optional.root"),
        "--profile", "vis", "--output-dir", str(output), "--plots-dir", str(plots),
    ])
    events = _synthetic_events(beam_energy_gev=1.0)
    prepared = ({(args.raw_bdt, SAMPLES["raw_bdt"].tree): events},
                {(811, 17): FluxExposure(811, 17, 1.0, 1.2, .9, .2, .6, .55)})
    calls = []
    writers = (
        "write_profile_figure4_pdf", "write_point_comparison_pdf",
        "write_profile_estimator_comparison_pdf", "write_profile_fit_diagnostics_pdf",
        "write_systematic_summary_pdf", "write_background_control_pdf",
        "write_false_asymmetry_controls_pdf", "write_photon_multiplicity_pdf",
    )

    def observe(name, writer):
        def checked(path, *values, **options):
            assert len(read_output_points(output / "beam_asymmetry.root")) == 6
            assert path.parent == plots
            calls.append(path.name)
            if fail_first_plot:
                raise RuntimeError("renderer failed")
            if name == "write_false_asymmetry_controls_pdf":
                assert values == ({},)  # Synthetic sample contains no BREM events.
                assert options["exposure_summary"]["brem_strata"] == 1
                assert options["exposure_summary"]["brem_runs"] == [811]
            return writer(path, *values, **options)
        return checked

    for name in writers:
        monkeypatch.setattr(workflow, name, observe(name, getattr(workflow, name)))
    if fail_first_plot:
        with pytest.raises(RuntimeError, match="renderer failed"):
            workflow._run_single(args, prepared=prepared)
        assert calls == ["figure4_experimental.pdf"]
    else:
        workflow._run_single(args, prepared=prepared)
        assert calls == [
            "figure4_experimental.pdf", "comparison_reconstruction_samples.pdf",
            "comparison_estimators.pdf", "fit_diagnostics.pdf", "systematic_summary.pdf",
            "false_asymmetry_controls.pdf", "photon_multiplicity.pdf",
        ]
        assert sorted(path.name for path in plots.iterdir()) == sorted(calls)
    assert "optional comparison sample missing: raw" in capsys.readouterr().err
    assert [path.name for path in output.iterdir()] == ["beam_asymmetry.root"]
    assert len(read_output_points(output / "beam_asymmetry.root")) == 6


@pytest.mark.parametrize('sample', ['raw', 'raw_bdt'])
def test_single_extraction_retains_pol_without_brem_and_records_policy(tmp_path, sample):
    args = beam_asymmetry.build_parser().parse_args([
        '--raw', str(tmp_path / 'raw.root'), '--raw-bdt', str(tmp_path / 'bdt.root'),
        '--nominal-sample', sample, '--profile', 'vis', '--output-dir', str(tmp_path / 'out'),
    ])
    events = _synthetic_events(beam_energy_gev=1.0)
    path = args.raw if sample == 'raw' else args.raw_bdt
    measured = FluxExposure(811, 17, 1.0, 1.2, .9, .2, .6, .55)
    missing = replace(measured, flux_brem=None, brem_status='missing')
    metadata = {}
    workflow._run_single(args, prepared=({(path, SAMPLES[sample].tree): events},
                                        {(811, 17): missing}), metadata=metadata)
    points = read_output_points(args.output_dir / 'beam_asymmetry.root')
    assert len(points) == 6
    assert {point.sample for point in points} == {sample}
    assert metadata['brem_control']['selection']['selected'] == len(events)
    assert metadata['brem_control']['exposure']['brem_strata'] == 0
    assert metadata['brem_control']['exposure']['brem'] is None
    assert read_output_contract(args.output_dir / 'beam_asymmetry.root').flux_policy == 'paired_pol_independent_brem'
