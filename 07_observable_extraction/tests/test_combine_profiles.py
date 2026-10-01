from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from observable_extraction import combine_profiles
from observable_extraction.io.root_input import RootOutputContract
from observable_extraction.io.root_output import RootOutputPayload, write_root_output
from observable_extraction.tests.test_figure4 import _points


def test_combined_cli_defaults_use_test_data_layout():
    args = combine_profiles.build_parser().parse_args([])

    assert args.uv_root == Path(
        "test_data/beam_asymmetry/beam_asymmetry.root"
    )
    assert args.vis_root == Path(
        "test_data/vis/beam_asymmetry/beam_asymmetry.root"
    )
    assert args.published_csv == Path(
        "test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv"
    )
    assert args.output_dir == Path("test_data/beam_asymmetry/uv_vis")


def test_combined_cli_writes_exact_four_outputs(tmp_path, monkeypatch):
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
        "write_profile_figure4_pdf",
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
    assert sorted(path.name for path in output.iterdir()) == [
        "comparison_estimators.pdf",
        "figure4_comparison_ajaka2008.pdf",
        "figure4_experimental.pdf",
        "fit_diagnostics.pdf",
    ]
    assert len(calls) == 4
    assert all(set(call[1]) == {"uv", "vis"} for call in calls)


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


def _write_profile_root(path, points, energy_edges, provenance):
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
        ),
    )


def _stub_combined_writers(monkeypatch):
    monkeypatch.setattr(combine_profiles, "load_published_points", lambda _path: ())
    for name in (
        "write_profile_figure4_pdf",
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
        for item in uv_points
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
        for item in uv_points
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
