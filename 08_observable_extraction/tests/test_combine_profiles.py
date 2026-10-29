from dataclasses import replace
import hashlib
from pathlib import Path

import numpy as np
import pytest

from observable_extraction import combine_profiles
from observable_extraction.io.root_input import CandleContract, RootOutputContract
from observable_extraction.io.root_output import RootOutputPayload, write_root_output
from observable_extraction.tests.test_figure4 import _points


def test_combined_cli_defaults_use_production_layout():
    args = combine_profiles.build_parser().parse_args([])

    assert args.uv_root == Path(
        "results/production/root/uv/beam_asymmetry/beam_asymmetry.root"
    )
    assert args.vis_root == Path(
        "results/production/root/vis/beam_asymmetry/beam_asymmetry.root"
    )
    assert args.published_csv == combine_profiles.AJAKA_REFERENCE
    assert args.output_dir == Path("results/production/plots/common")


def test_ajaka_reference_is_versioned_and_compatibility_copy_matches():
    canonical = combine_profiles.AJAKA_REFERENCE
    compatibility = (
        Path(__file__).parents[2]
        / "08_observable_extraction/references/ajaka2008_figure4_digitized.csv"
    )
    expected = "aab73cc23c54f137eb46f37949911af83f266c50ef5e7f4ae6d33a9b68bedfa7"

    assert canonical.is_file()
    assert compatibility.is_file()
    assert hashlib.sha256(canonical.read_bytes()).hexdigest() == expected
    assert hashlib.sha256(compatibility.read_bytes()).hexdigest() == expected


def test_combined_cli_writes_comparison_without_duplicate_experimental(tmp_path, monkeypatch):
    uv_root = tmp_path / "uv.root"
    vis_root = tmp_path / "vis.root"
    published = tmp_path / "ajaka.csv"
    output = tmp_path / "combined"
    uv_points = _points()
    vis_point = replace(
        uv_points[0],
        point=replace(
            uv_points[0].point,
            energy_bin=0,
            energy_low_gev=0.9313,
            energy_high_gev=1.10,
        ),
    )
    monkeypatch.setattr(
        combine_profiles,
        "read_output_points",
        lambda path: (vis_point,) if path == vis_root else uv_points,
    )
    monkeypatch.setattr(
        combine_profiles,
        "read_output_contract",
        lambda path: RootOutputContract(
            profile="vis" if path == vis_root else None,
            energy_edges_gev=(0.9313, 1.10)
            if path == vis_root
            else (1.10, 1.20, 1.30, 1.40, 1.50),
        ),
    )
    monkeypatch.setattr(
        combine_profiles,
        "load_published_points",
        lambda _path: (),
    )
    calls = []

    def writer(path, points_by_profile, *args, **kwargs):
        calls.append((path.name, points_by_profile, args, kwargs))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF")

    for name in (
        "write_profile_figure4_comparison_pdf",
        "write_profile_estimator_comparison_pdf",
        "write_profile_fit_diagnostics_pdf",
    ):
        monkeypatch.setattr(combine_profiles, name, writer)

    result = combine_profiles.main(
        [
            "--uv-root", str(uv_root),
            "--vis-root", str(vis_root),
            "--published-csv", str(published),
            "--output-dir", str(output),
        ]
    )

    assert result == 0
    assert sorted(path.name for path in output.iterdir()) == sorted([
        "comparison_estimators.pdf",
        "asymmetry_comparison.pdf",
        "asymmetry_uv_ajaka.pdf",
        "fit_diagnostics.pdf",
    ])
    assert len(calls) == 4
    by_name = {call[0]: call for call in calls}
    assert set(by_name['asymmetry_uv_ajaka.pdf'][1]) == {'uv'}
    assert all(set(call[1]) == {"uv", "vis"} for call in calls
               if call[0] != 'asymmetry_uv_ajaka.pdf')
    assert by_name['asymmetry_comparison.pdf'][3]['overlay_profiles'] is True


def test_combined_cli_rejects_empty_profile_root(tmp_path, monkeypatch):
    uv_root = tmp_path / "uv.root"
    vis_root = tmp_path / "vis.root"
    monkeypatch.setattr(
        combine_profiles,
        "read_output_points",
        lambda path: () if path == vis_root else _points(),
    )

    with pytest.raises(RuntimeError, match="VIS ROOT file has no points"):
        combine_profiles.main(
            ["--uv-root", str(uv_root), "--vis-root", str(vis_root)]
        )


def _write_profile_root(path, points, energy_edges, provenance, phi_edges=None):
    write_root_output(
        path,
        RootOutputPayload(
            points=points,
            energy_edges=np.asarray(energy_edges, dtype=np.float64),
            mass_edges={},
            covariance_total=np.eye(len(points)),
            systematic_covariances={},
            ratio_objects=(),
            provenance=provenance,
            **({"phi_edges": phi_edges} if phi_edges is not None else {}),
        ),
    )


def test_combined_cli_rejects_mismatched_phi_binning_before_writing(tmp_path):
    uv_points = _points()
    vis_points = tuple(
        replace(item, point=replace(item.point, energy_bin=0,
                                    energy_low_gev=0.9313, energy_high_gev=1.10))
        for item in uv_points if item.point.energy_bin == 0
    )
    uv_root, vis_root = tmp_path / "uv.root", tmp_path / "vis.root"
    _write_profile_root(uv_root, uv_points, (1.10, 1.20, 1.30, 1.40, 1.50),
                        "profile=uv", np.linspace(0.0, 2.0 * np.pi, 9))
    _write_profile_root(vis_root, vis_points, (0.9313, 1.10),
                        "profile=vis", np.linspace(0.0, 2.0 * np.pi, 17))
    output = tmp_path / "combined"
    with pytest.raises(RuntimeError, match="phi binning"):
        combine_profiles.main(["--uv-root", str(uv_root), "--vis-root", str(vis_root),
                               "--output-dir", str(output)])
    assert not output.exists()


def test_combined_cli_rejects_mixing_corrected_and_legacy_sigma(tmp_path):
    uv_points = _points()
    vis_points = tuple(
        replace(item, point=replace(item.point, energy_bin=0,
                                    energy_low_gev=0.9313, energy_high_gev=1.10))
        for item in uv_points if item.point.energy_bin == 0
    )
    uv_root, vis_root = tmp_path / "uv.root", tmp_path / "vis.root"
    _write_profile_root(uv_root, uv_points, (1.10, 1.20, 1.30, 1.40, 1.50),
                        "profile=uv\nphi_bin_divisor=0.9549")
    _write_profile_root(vis_root, vis_points, (0.9313, 1.10), "profile=vis")
    output = tmp_path / "combined"
    with pytest.raises(RuntimeError, match="phi-bin correction"):
        combine_profiles.main(["--uv-root", str(uv_root), "--vis-root", str(vis_root),
                               "--output-dir", str(output)])
    assert not output.exists()


@pytest.mark.parametrize("vis_best", [True, False])
def test_best_binning_composition_accepts_different_choices_but_not_mixed_modes(tmp_path, vis_best):
    uv_points = tuple(replace(p, phi_bins=8 if p.estimator == "ratio" else 0) for p in _points())
    vis_points = tuple(replace(p, phi_bins=16 if p.estimator == "ratio" else 0,
        point=replace(p.point, energy_bin=0, energy_low_gev=0.9313, energy_high_gev=1.10))
        for p in uv_points if p.point.energy_bin == 0)
    uv, vis, out = tmp_path / "uv.root", tmp_path / "vis.root", tmp_path / "plots"
    adaptive = "\nphi_bins=best-binning\nphi_bin_divisor=per_point"
    _write_profile_root(uv, uv_points, (1.1, 1.2, 1.3, 1.4, 1.5), "profile=uv" + adaptive)
    _write_profile_root(vis, vis_points, (.9313, 1.10),
                        "profile=vis" + (adaptive if vis_best else "\nphi_bin_divisor=0.9745"),
                        np.linspace(0, 2 * np.pi, 17))
    args = ["--uv-root", str(uv), "--vis-root", str(vis), "--output-dir", str(out)]
    if vis_best:
        assert combine_profiles.main(args) == 0
        assert (out / "asymmetry_comparison.pdf").is_file()
    else:
        with pytest.raises(RuntimeError, match="best-binning mode"):
            combine_profiles.main(args)
        assert not out.exists()


def _stub_combined_writers(monkeypatch):
    monkeypatch.setattr(combine_profiles, "load_published_points", lambda _path: ())
    for name in (
        "write_profile_figure4_comparison_pdf",
        "write_profile_estimator_comparison_pdf",
        "write_profile_fit_diagnostics_pdf",
    ):
        monkeypatch.setattr(combine_profiles, name, lambda *_args, **_kwargs: None)


def test_combined_cli_rejects_swapped_uv_and_vis_roots(tmp_path, monkeypatch):
    uv_points = _points()
    vis_points = tuple(
        replace(
            item,
            point=replace(
                item.point,
                energy_bin=0,
                energy_low_gev=0.9313,
                energy_high_gev=1.10,
            ),
        )
        for item in uv_points if item.point.energy_bin == 0
    )
    uv_root = tmp_path / "uv.root"
    vis_root = tmp_path / "vis.root"
    _write_profile_root(
        uv_root,
        uv_points,
        (1.10, 1.20, 1.30, 1.40, 1.50),
        "legacy UV output",
    )
    _write_profile_root(
        vis_root,
        vis_points,
        (0.9313, 1.10),
        "profile=vis",
    )
    _stub_combined_writers(monkeypatch)

    with pytest.raises(RuntimeError, match="UV ROOT.*profile|UV ROOT.*energy"):
        combine_profiles.main(
            [
                "--uv-root", str(vis_root),
                "--vis-root", str(uv_root),
                "--published-csv", str(tmp_path / "published.csv"),
                "--output-dir", str(tmp_path / "output"),
            ]
        )


def test_combined_cli_rejects_mismatched_stored_energy_edges(
    tmp_path, monkeypatch
):
    uv_points = _points()
    vis_points = tuple(
        replace(
            item,
            point=replace(
                item.point,
                energy_bin=0,
                energy_low_gev=0.9313,
                energy_high_gev=1.10,
            ),
        )
        for item in uv_points if item.point.energy_bin == 0
    )
    uv_root = tmp_path / "uv.root"
    vis_root = tmp_path / "vis.root"
    _write_profile_root(
        uv_root,
        uv_points,
        (1.10, 1.20, 1.30, 1.40, 1.50),
        "legacy UV output",
    )
    _write_profile_root(
        vis_root,
        vis_points,
        (0.90, 1.10),
        "profile=vis",
    )
    _stub_combined_writers(monkeypatch)

    with pytest.raises(RuntimeError, match="VIS ROOT.*energy edges"):
        combine_profiles.main(
            [
                "--uv-root", str(uv_root),
                "--vis-root", str(vis_root),
                "--published-csv", str(tmp_path / "published.csv"),
                "--output-dir", str(tmp_path / "output"),
            ]
        )


def _candle_contract(
    *, width=0.05, baseline_count=100, full_core_count=80,
    tail_count=20, seed=20261024, tail_logic="or_complement"
):
    return CandleContract(
        eta_center_gev=0.547862,
        pi0_center_gev=0.134977,
        mass_half_width_gev=width,
        geometry="rectangular",
        core_logic="and",
        tail_logic=tail_logic,
        boundary="inclusive",
        baseline_event_count=baseline_count,
        full_core_event_count=full_core_count,
        tail_event_count=tail_count,
        balanced_core_event_count=tail_count,
        excluded_nonfinite_event_count=(
            baseline_count - full_core_count - tail_count
        ),
        balance_method="random_without_replacement",
        balance_seed=seed,
        mass_source="raw_pre_fit",
    )


def _candle_samples(points):
    return tuple(
        replace(
            item,
            sample=sample,
            estimator=estimator,
            point=replace(
                item.point,
                sigma=item.point.sigma
                + (0.01 if sample == "raw_bdt_core" else -0.01),
            ),
        )
        for item in points
        for sample in ("raw_bdt_core", "raw_bdt_tails")
        for estimator in ("ratio", "likelihood")
    )


def _vis_points(points):
    return tuple(
        replace(
            item,
            point=replace(
                item.point,
                energy_bin=0,
                energy_low_gev=0.9313,
                energy_high_gev=1.10,
            ),
        )
        for item in points
        if item.point.energy_bin == 0
    )


@pytest.mark.parametrize(
    ("estimators", "expected"),
    [
        (("ratio", "likelihood"), {"ratio", "likelihood"}),
        (("ratio",), {"ratio"}),
        (("likelihood",), {"likelihood"}),
    ],
)
def test_combined_cli_writes_only_available_candle_comparisons(
    tmp_path, monkeypatch, estimators, expected
):
    uv_root, vis_root = tmp_path / "uv.root", tmp_path / "vis.root"
    uv_points = tuple(
        item for item in _candle_samples(_points()) if item.estimator in estimators
    )
    vis_points = tuple(
        item for item in _candle_samples(_vis_points(_points()))
        if item.estimator in estimators
    )
    monkeypatch.setattr(
        combine_profiles, "read_output_points",
        lambda path: vis_points if path == vis_root else uv_points,
    )
    monkeypatch.setattr(
        combine_profiles, "read_output_contract",
        lambda path: RootOutputContract(
            profile="vis" if path == vis_root else "uv",
            energy_edges_gev=(0.9313, 1.10) if path == vis_root
            else (1.10, 1.20, 1.30, 1.40, 1.50),
            candle=_candle_contract(
                baseline_count=120, full_core_count=90,
                tail_count=30, seed=99,
            ) if path == vis_root else _candle_contract(),
        ),
    )
    monkeypatch.setattr(combine_profiles, "load_published_points", lambda _path: ())

    def legacy_writer(path, *_args, **_kwargs):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-legacy")

    for name in (
        "write_profile_figure4_comparison_pdf",
        "write_profile_estimator_comparison_pdf",
        "write_profile_fit_diagnostics_pdf",
    ):
        monkeypatch.setattr(combine_profiles, name, legacy_writer)
    output = tmp_path / "combined"

    assert combine_profiles.main([
        "--uv-root", str(uv_root), "--vis-root", str(vis_root),
        "--published-csv", str(tmp_path / "published.csv"),
        "--output-dir", str(output),
    ]) == 0
    for estimator in ("ratio", "likelihood"):
        path = output / f"comparison_candle_{estimator}.pdf"
        assert path.exists() == (estimator in expected)
        if path.exists():
            assert path.read_bytes().startswith(b"%PDF-")


@pytest.mark.parametrize(
    "case", ["one_enabled", "different_width", "different_tail_logic", "missing_tail"]
)
def test_combined_cli_rejects_inconsistent_candle_contracts(
    tmp_path, monkeypatch, case
):
    uv_root, vis_root = tmp_path / "uv.root", tmp_path / "vis.root"
    uv_points = _candle_samples(_points())
    vis_points = _candle_samples(_vis_points(_points()))
    if case == "missing_tail":
        vis_points = tuple(
            item for item in vis_points if item.sample != "raw_bdt_tails"
        )
    monkeypatch.setattr(
        combine_profiles, "read_output_points",
        lambda path: vis_points if path == vis_root else uv_points,
    )
    monkeypatch.setattr(
        combine_profiles, "read_output_contract",
        lambda path: RootOutputContract(
            profile="vis" if path == vis_root else "uv",
            energy_edges_gev=(0.9313, 1.10) if path == vis_root
            else (1.10, 1.20, 1.30, 1.40, 1.50),
            candle=None if case == "one_enabled" and path == vis_root
            else _candle_contract(
                width=0.04 if case == "different_width" and path == vis_root else 0.05,
                tail_logic="and" if case == "different_tail_logic" and path == vis_root
                else "or_complement",
            ),
        ),
    )
    output = tmp_path / "combined"

    with pytest.raises(RuntimeError, match="candle"):
        combine_profiles.main([
            "--uv-root", str(uv_root), "--vis-root", str(vis_root),
            "--output-dir", str(output),
        ])
    assert not output.exists()
