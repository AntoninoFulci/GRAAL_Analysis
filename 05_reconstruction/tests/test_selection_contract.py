"""Positive certification for the pairing/missing-mass reconstruction policy."""
from types import SimpleNamespace
import json

import pytest

from reconstruction.runtime import provenance


def source(metadata):
    record = SimpleNamespace(GetTitle=lambda: json.dumps(metadata)) if metadata is not None else None
    return SimpleNamespace(Get=lambda _: record)


def tree(branches=()):
    return SimpleNamespace(GetListOfBranches=lambda: [SimpleNamespace(GetName=lambda name=name: name) for name in branches])


def validate(metadata, branches=()):
    assert hasattr(provenance, 'validate_reconstruction_selection'), 'positive schema-2 validator missing'
    return provenance.validate_reconstruction_selection(source(metadata), tree(branches))


def test_accepts_positive_pairing_missing_mass_contract():
    metadata = dict(schema=2, selection_algorithm='pairing_missing_mass')
    assert validate(metadata) == metadata


@pytest.mark.parametrize('metadata', [None, {}, dict(schema=1, do_fit=False),
    dict(schema=2), dict(schema=2, selection_algorithm='archived'),
    dict(schema=True, selection_algorithm='pairing_missing_mass')])
def test_rejects_uncertified_raw_even_without_fitted_branches(metadata):
    with pytest.raises(ValueError, match='provenance|schema|selection'):
        validate(metadata)


@pytest.mark.parametrize('branch', ['eta_fit', 'pi0_fit', 'proton_fit', 'eta_fit_gamma1',
                                  'pi0_fit_gamma2', 'fit_chi2', 'fit_ndf', 'fit_converged'])
def test_rejects_fitted_branches_even_with_new_marker(branch):
    with pytest.raises(ValueError, match='branch'):
        validate(dict(schema=2, selection_algorithm='pairing_missing_mass'), [branch])
