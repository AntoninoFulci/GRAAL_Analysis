import json

import numpy as np
import pytest

from observable_extraction.core import mass_selection


def definition(**changes):
    value = dict(schema=1, name="test-control-v1", defined_on="synthetic control",
                 axes=["eta_mass", "pi0_mass"], units="GeV", boundary="include",
                 vertices=[[.4, .1], [.7, .1], [.7, .2], [.4, .2]])
    return dict(value, **changes)


def test_polygon_keeps_interior_and_explicit_boundaries_rejects_nonfinite():
    eta = np.array([.5, .4, .7, .8, np.nan, .5, .5])
    pi0 = np.array([.15, .15, .2, .15, .15, np.inf, .1])
    included = mass_selection.MassPolygon.from_dict(definition())
    excluded = mass_selection.MassPolygon.from_dict(definition(boundary="exclude"))
    assert included.mask(eta, pi0).tolist() == [True, True, True, False, False, False, True]
    assert excluded.mask(eta, pi0).tolist() == [True, False, False, False, False, False, False]
    assert included.mask(pi0, eta).tolist() == [False] * 7


def test_concave_polygon_and_clockwise_vertices_agree():
    vertices = [[0, 0], [2, 0], [2, 2], [1, 1], [0, 2]]
    for points in (vertices, vertices[::-1], vertices + [vertices[0]]):
        polygon = mass_selection.MassPolygon.from_dict(definition(vertices=points))
        assert polygon.mask([1, .5, 1, 2], [1.5, 1.5, .5, 1]).tolist() == [False, True, True, True]


@pytest.mark.parametrize("change", [
    {"axes": ["pi0_mass", "eta_mass"]}, {"units": "MeV"}, {"schema": 2},
    {"boundary": "automatic"}, {"defined_on": ""}, {"name": ""},
    {"vertices": [[0, 0], [1, 1]]},
    {"vertices": [[0, 0], [1, 1], [2, 2]]},
    {"vertices": [[0, 0], [1, 1], [0, 1], [1, 0]]},
    {"vertices": [[0, 0], [2, 0], [1, 0], [1, 1]]},
    {"vertices": [[0, 0], [1, 0], [1, 1], [0, 0], [0, 1]]},
    {"vertices": [[0, 0], [1, float("nan")], [0, 1]]},
])
def test_invalid_or_ambiguous_polygon_is_rejected(change):
    with pytest.raises(ValueError):
        mass_selection.MassPolygon.from_dict(definition(**change))


def test_definition_roundtrip_empty_inputs_and_shape_validation(tmp_path):
    path = tmp_path / "region.json"
    path.write_text(json.dumps(definition()))
    polygon = mass_selection.MassPolygon.read(path)
    assert polygon.to_dict() == definition()
    assert polygon.mask([], []).dtype == bool
    assert polygon.mask([], []).size == 0
    with pytest.raises(ValueError, match="shape"):
        polygon.mask([.5], [.1, .2])
    with pytest.raises(ValueError, match="shape"):
        polygon.mask([[.5]], [[.1]])
