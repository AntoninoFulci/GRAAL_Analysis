import os

import pytest


def test_ordered_map_processes_and_order():
    from graal_common.parallel import ordered_map

    result = ordered_map(lambda x: (x * x, os.getpid()), range(6), workers=2)
    assert [value for value, _ in result] == [0, 1, 4, 9, 16, 25]
    assert all(pid != os.getpid() for _, pid in result)


def test_ordered_map_propagates_worker_failure():
    from graal_common.parallel import ordered_map

    with pytest.raises(ZeroDivisionError):
        ordered_map(lambda x: 1 / x, [1, 0], workers=2)


def test_worker_native_threads_are_limited():
    from graal_common.parallel import ordered_map

    result = ordered_map(lambda _: os.environ.get('OMP_NUM_THREADS'), range(2), workers=2)
    assert result == ['1', '1']


def test_pool_does_not_allocate_idle_workers(monkeypatch):
    import joblib
    from graal_common.parallel import ordered_map

    original = joblib.Parallel
    budgets = []

    def parallel(*args, **kwargs):
        budgets.append(kwargs['n_jobs'])
        return original(*args, **kwargs)

    monkeypatch.setattr(joblib, 'Parallel', parallel)
    assert ordered_map(abs, [-1, -2], workers=40) == [1, 2]
    assert ordered_map(abs, [], workers=40) == []
    assert budgets == [2]


@pytest.mark.parametrize('workers', [0, -1, True, 1.5])
def test_invalid_worker_count(workers):
    from graal_common.parallel import ordered_map

    with pytest.raises(ValueError):
        ordered_map(abs, [], workers=workers)
