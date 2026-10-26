from dataclasses import replace

import matplotlib.pyplot as plt
import numpy as np
import pytest

from graal_common.physics.channels import M_ETA, M_PI0
from observable_extraction.plotting import candle
from observable_extraction.plotting.figure4 import profile_energy_rows
from observable_extraction.tests.test_figure4 import _points


def _core_tail_points(points, *, estimator="ratio"):
    return tuple(
        replace(
            item,
            sample=sample,
            estimator=estimator,
            point=replace(
                item.point,
                sigma=item.point.sigma
                + (0.02 if sample == "raw_bdt_core" else -0.02),
            ),
        )
        for item in points
        for sample in ("raw_bdt_core", "raw_bdt_tails")
    )


def test_candle_mass_plane_uses_finite_raw_arrays_and_exact_rectangle():
    eta_mass = np.array([0.49, M_ETA, 0.61, np.nan])
    pi0_mass = np.array([0.09, M_PI0, 0.18, M_PI0])

    figure, axis = candle.build_candle_mass_plane(
        eta_mass,
        pi0_mass,
        half_width_gev=0.05,
        full_core_count=2,
        tail_count=1,
        balanced_core_count=1,
        excluded_nonfinite_count=1,
    )

    assert np.sum(axis.collections[0].get_array()) == 3
    rectangle = axis.patches[0]
    assert rectangle.get_xy() == pytest.approx((M_ETA - 0.05, M_PI0 - 0.05))
    assert rectangle.get_width() == pytest.approx(0.10)
    assert rectangle.get_height() == pytest.approx(0.10)
    annotation = "\n".join(text.get_text() for text in axis.texts)
    assert "Baseline: 4" in annotation
    assert "Core completo: 2" in annotation
    assert "Code: 1" in annotation
    assert "Campioni bilanciati: 1 + 1" in annotation
    assert "Masse non finite escluse: 1" in annotation
    x_low, x_high = axis.get_xlim()
    y_low, y_high = axis.get_ylim()
    assert x_low < M_ETA - 0.05 < M_ETA + 0.05 < x_high
    assert y_low < M_PI0 - 0.05 < M_PI0 + 0.05 < y_high
    plt.close(figure)


@pytest.mark.parametrize(
    ("eta_mass", "pi0_mass", "width", "counts", "message"),
    [
        ([], [], 0.05, (0, 0, 0, 0), "non-empty"),
        ([M_ETA], [M_PI0, M_PI0], 0.05, (1, 0, 0, 0), "same length"),
        ([M_ETA], [M_PI0], 0.0, (1, 0, 0, 0), "half_width_gev"),
        ([M_ETA], [M_PI0], 0.05, (-1, 1, 1, 0), "counts"),
        ([M_ETA], [M_PI0], 0.05, (1, 1, 0, 0), "balanced"),
        ([M_ETA], [M_PI0], 0.05, (1, 1, 1, 1), "baseline"),
    ],
)
def test_candle_mass_plane_rejects_invalid_inputs(
    eta_mass, pi0_mass, width, counts, message
):
    with pytest.raises(ValueError, match=message):
        candle.build_candle_mass_plane(
            np.asarray(eta_mass),
            np.asarray(pi0_mass),
            half_width_gev=width,
            full_core_count=counts[0],
            tail_count=counts[1],
            balanced_core_count=counts[2],
            excluded_nonfinite_count=counts[3],
        )


def test_candle_comparison_keeps_independently_unmatched_points():
    core = replace(_points()[0], sample="raw_bdt_core")
    tail = replace(_points()[4], sample="raw_bdt_tails")

    figure, axes = candle.build_candle_comparison(
        {"uv": (core, tail)},
        profile_energy_rows("uv")[:1],
        estimator="ratio",
    )

    assert len(axes[0, 0].containers) == 1
    assert axes[0, 0].containers[0].lines[0].get_ydata().tolist() == [
        core.point.sigma
    ]
    assert len(axes[0, 1].containers) == 1
    assert [text.get_text() for text in figure.legends[0].get_texts()] == [
        "Core",
        "Code",
    ]
    plt.close(figure)


@pytest.mark.parametrize("estimator", ["ratio", "likelihood"])
def test_candle_comparison_supports_both_estimators(estimator):
    figure, axes = candle.build_candle_comparison(
        {"uv": _core_tail_points(_points(), estimator=estimator)},
        profile_energy_rows("uv"),
        estimator=estimator,
    )

    assert axes.shape == (4, 3)
    assert all(len(axis.containers) == 2 for axis in axes.flat)
    plt.close(figure)


@pytest.mark.parametrize("sample", ["raw_bdt_core", "raw_bdt_tails"])
def test_candle_comparison_requires_both_samples(sample):
    point = replace(_points()[0], sample=sample)

    with pytest.raises(ValueError, match="core.*tails|tails.*core"):
        candle.build_candle_comparison(
            {"uv": (point,)},
            profile_energy_rows("uv")[:1],
            estimator="ratio",
        )


def test_candle_writers_create_valid_pdfs(tmp_path):
    mass_plane = tmp_path / "candle_mass_plane.pdf"
    comparison = tmp_path / "comparison_candle_ratio.pdf"

    candle.write_candle_mass_plane_pdf(
        mass_plane,
        np.array([M_ETA - 0.01, M_ETA + 0.08]),
        np.array([M_PI0, M_PI0]),
        half_width_gev=0.05,
        full_core_count=1,
        tail_count=1,
        balanced_core_count=1,
        excluded_nonfinite_count=0,
    )
    candle.write_candle_comparison_pdf(
        comparison,
        {"uv": _core_tail_points(_points())},
        profile_energy_rows("uv"),
        estimator="ratio",
    )

    assert mass_plane.read_bytes().startswith(b"%PDF-")
    assert comparison.read_bytes().startswith(b"%PDF-")
