import numpy as np
import pytest
from mc_simulation.response import count_response, response_probabilities


def test_response_keeps_lost_events_and_migration():
    generated, selected = count_response(
        [10, 11, 12, 13, 14],
        [0, 0, 0, 1, 1],
        [10, 12, 13, 14],
        [0, 1, 1, -1],
        2,
    )
    np.testing.assert_array_equal(generated, [3, 2])
    np.testing.assert_array_equal(selected, [[1, 0], [1, 1]])
    response, covariance = response_probabilities(generated, selected)
    np.testing.assert_allclose(response, [[1 / 3, 0], [1 / 3, 1 / 2]])
    assert covariance[0, 0, 1] == pytest.approx(-1 / 27)
    assert covariance[1, 1, 1] == pytest.approx(1 / 8)


@pytest.mark.parametrize(
    "generated_ids,selected_ids", [([1, 1], [1]), ([1, 2], [1, 1]), ([1, 2], [3])]
)
def test_response_rejects_ambiguous_or_unknown_ids(generated_ids, selected_ids):
    with pytest.raises(ValueError):
        count_response(
            generated_ids,
            [0] * len(generated_ids),
            selected_ids,
            [0] * len(selected_ids),
            1,
        )


@pytest.mark.parametrize(
    "generated,selected",
    [([0], [[0]]), ([10], [[0]]), ([2], [[3]]), ([2.5], [[1]]), ([2], [[-1]])],
)
def test_response_rejects_unsupported_or_invalid_counts(generated, selected):
    with pytest.raises(ValueError):
        response_probabilities(generated, selected)


def test_response_rejects_fractional_cell_and_identity():
    with pytest.raises(ValueError):
        count_response([1.1], [0], [1.1], [0], 1)
    with pytest.raises(ValueError):
        count_response([1], [0.5], [1], [0], 1)
