"""Measured GEANT4 bridge products must use the real data PID and selector.

These are synthetic detector measurements, not a detector-efficiency or physics
validation. The unchanged period cut files and C++ PreAnalysis do the PID.
"""
import math
from pathlib import Path

import numpy as np
import pytest
import ROOT
import uproot

from event_selector.select_events import run as select_events
from mc_simulation.geant4.h70 import export_h70
from scripts.run_preanalysis import run as preanalyse
from tests.test_geant4_h70 import build_measured_inputs


def _central(kind, energy=.1, dedx=0., theta=45., phi=0.):
    return dict(type=kind, bgo_energy_GeV=energy, dedx_MeV=dedx,
                theta_deg=theta, phi_deg=phi)


def _four_photons(kinetic=.1, proton_theta=45.):
    """Conserving gamma p -> p + 4 gamma example, with central photons.

    No meson mass, reconstruction fit or candidate provenance is invented.
    Two opposite photon pairs in the residual system are boosted to the lab.
    """
    mass, beam = .9382720813, 1.2
    momentum = math.sqrt(kinetic * (kinetic + 2 * mass))
    angle = math.radians(proton_theta)
    recoil = np.array([-momentum * math.sin(angle), 0.,
                       beam - momentum * math.cos(angle)])
    energy = beam - kinetic
    beta = recoil / energy
    beta2 = np.dot(beta, beta)
    gamma = 1. / math.sqrt(1. - beta2)
    rest_energy = math.sqrt(energy * energy - np.dot(recoil, recoil)) / 4
    axis = recoil / np.linalg.norm(recoil)
    transverse = np.array([axis[2], 0., -axis[0]])
    photons = []
    lab_vectors = []
    for azimuth in (70., 110., 250., 290.):
        azimuth = math.radians(azimuth)
        rest = rest_energy * (math.cos(azimuth) * transverse
                              + math.sin(azimuth) * np.array([0., 1., 0.]))
        product = np.dot(beta, rest)
        lab = rest + ((gamma - 1.) * product / beta2 + gamma * rest_energy) * beta
        lab_energy = gamma * (rest_energy + product)
        theta = math.degrees(math.acos(lab[2] / lab_energy))
        assert 25. < theta < 155.
        photons.append(_central(11, lab_energy, theta=theta,
                                phi=math.degrees(math.atan2(lab[1], lab[0]))))
        lab_vectors.append([*lab, lab_energy])
    assert np.sum(lab_vectors, axis=0) == pytest.approx([*recoil, energy])
    return photons


def _read_pid(path, tree_name):
    source = ROOT.TFile.Open(str(path))
    try:
        tree = source.Get(tree_name)
        rows = []
        for event in tree:
            row = dict(entry=int(event.RawSourceEntry), run=int(event.RunNumber),
                       polarization=int(event.Polarization), strip=float(event.Xstrip),
                       beam=float(event.beam.E()), source=str(event.RawSourceFile))
            for name in ('gammas', 'protons', 'neutrons'):
                row[name] = [(float(p.E()), math.degrees(p.Theta()),
                              math.degrees(p.Phi())) for p in getattr(event, name)]
            for name in ('pions_theta', 'gamma_theta', 'fcharged_theta',
                         'fcharged_tof', 'fcharded_de', 'Itipo_track',
                         'Index_trf', 'Iass_trf'):
                row[name] = list(getattr(event, name))
                if name in ('Index_trf', 'Iass_trf'):
                    # PyROOT exposes vector<unsigned char> as characters.
                    row[name] = [ord(v) if isinstance(v, str) else int(v)
                                 for v in row[name]]
            rows.append(row)
        return rows
    finally:
        source.Close()


def _forward(link, tof=20., de=400., theta=10., phi=30.):
    return dict(source_match_index=link, tof_ns=tof, de_MeV=de,
                theta_deg=theta, phi_deg=phi)


@pytest.fixture(scope='module')
def common_pid(tmp_path_factory):
    work = tmp_path_factory.mktemp('geant4-common-pid')
    central_signal = _four_photons() + [_central(13, dedx=7.)]
    # TOF and path match the unchanged common forward proton convention.
    forward_beta = 301.53 / (20. * 29.9792458)
    forward_kinetic = .9382720813 * (1 / math.sqrt(1 - forward_beta**2) - 1)
    forward_gammas = _four_photons(forward_kinetic, 10.)
    events = [
        dict(central=[_central(13, dedx=7.), _central(14, dedx=7., theta=60.),
                      _central(13, dedx=2.8, theta=75.), _central(11, theta=90.)],
             matches=[dict(mask=1), dict(mask=7), dict(mask=1), dict(mask=6)],
             forward=[_forward(4), _forward(2, 10., 120., theta=15.),
                      _forward(1, 11., 2., theta=12.), _forward(3, 13., 3., theta=18.)]),
        dict(central=central_signal, tags=[dict(energy_GeV=1.2, strip=1.)]),
        dict(central=_four_photons() + [_central(14, dedx=7.)], partial_shape=True),
        dict(central=forward_gammas, matches=[dict(mask=6)], forward=[_forward(1, phi=0.)]),
        dict(central=forward_gammas, matches=[dict(mask=7)], forward=[_forward(1, phi=0.)]),
        # Fully observed, empty event must clear previous particle buffers.
        dict(tags=[dict(energy_GeV=1.2, strip=128.)]),
        dict(tags=[]),  # Known no tag after a tagged event must not reuse its beam.
        dict(central_available=False),
        dict(central=central_signal + [_central(13, dedx=2.8, theta=75.)]),
        dict(central=central_signal, matches=[dict(mask=6)],
             forward=[_forward(1, 10., 5.)]),
        dict(central=forward_gammas, matches=[dict(mask=6), dict(mask=7)],
             forward=[_forward(1), _forward(2, 10., 5.)]),
    ]
    for event in events:
        event.setdefault('tags', [dict(energy_GeV=1.2, strip=51.25)])
    inputs = build_measured_inputs(work / 'measured', events=events)
    bridge = work / 'bridge'
    export_h70(output=bridge, **inputs)
    raw = bridge / 'raw/1998_uv/run1321.root'
    h80_dir, h85_dir = work / 'h80', work / 'h85'
    preanalyse(bridge / 'raw', h80_dir, cpus=1)
    select_events(h80_dir, h85_dir, threads=1)
    return dict(raw=raw, bridge=bridge, h80=h80_dir / 'pre_analisi_1998_uv.root',
                h85=h85_dir / 'analisi_1998_uv.root')


def test_measured_bridge_preserves_units_and_one_based_links(common_pid):
    with uproot.open(common_pid['raw']) as source:
        rows = source['h70'].arrays(library='ak')
        assert len(rows) == 10  # Only unavailable detector event is excluded.
        assert rows[0].Idrun == 1321
        assert rows[0].Ipol == 1
        assert list(rows[0].Eclusc_track) == pytest.approx([.1] * 4)
        assert list(rows[0].Dedx_track) == pytest.approx([7., 7., 2.8, 0.])
        assert list(rows[0].Itipo_track) == [13, 14, 13, 11]
        assert list(rows[0].Index_trf) == [4, 2, 1, 3]
        assert list(rows[0].Iass_trf) == [1, 7, 1, 6]
        assert list(rows[0].Tof_trf) == pytest.approx([20., 10., 11., 13.])
        assert list(rows[0].De_trf) == pytest.approx([400., 120., 2., 3.])
        assert list(rows[1].Xstrip) == [1.]
        assert list(rows[5].Xstrip) == [128.]
        assert rows[6].Ncstrip == 0


def test_unchanged_period_pid_classifies_measured_tracks(common_pid):
    rows = _read_pid(common_pid['h80'], 'h80')
    mixed = rows[0]
    assert len(mixed['gammas']) == 1
    assert [p[1] for p in mixed['protons']] == pytest.approx([45., 60., 10.])
    assert mixed['protons'][0][0] == pytest.approx(.9382720813 + .1)
    assert mixed['pions_theta'] == pytest.approx([75., 15.])
    assert mixed['gamma_theta'] == pytest.approx([12.])
    assert len(mixed['neutrons']) == 1
    assert mixed['neutrons'][0][1] == pytest.approx(18.)
    assert mixed['fcharged_tof'] == pytest.approx([20., 10.])
    assert mixed['fcharded_de'] == pytest.approx([400., 120.])
    assert mixed['Index_trf'] == [4, 2, 1, 3]
    assert mixed['Iass_trf'] == [1, 7, 1, 6]


def test_common_selection_and_tagger_accounting(common_pid):
    with uproot.open(common_pid['bridge'] / 'ledger.root') as source:
        ledger = source['h70_events'].arrays(library='np')
        assert list(ledger['event']) == list(range(11))
        assert list(ledger['h70_entry']) == [0, 1, 2, 3, 4, 5, 6, -1, 7, 8, 9]
        assert ledger['central_available'][7] == 0
        assert ledger['reason_bits'][7] != 0
        assert np.count_nonzero(ledger['reason_bits']) == 1
        assert ledger['central_available'][2] == 1  # Partial shape remains usable.
        assert ledger['tagger_available'][6] == 1  # Known zero tags, not unavailable.
    rows = _read_pid(common_pid['h80'], 'h80')
    assert [row['entry'] for row in rows] == [0, 1, 2, 3, 4, 5, 7, 8, 9]
    assert all(row['run'] == 1321 and row['polarization'] == 1 for row in rows)
    assert all(row['beam'] == pytest.approx(1.2) for row in rows)
    assert all(Path(row['source']) == common_pid['raw'] for row in rows)
    assert rows[1]['strip'] == 1.
    assert rows[5]['strip'] == 128.
    assert rows[0]['strip'] == pytest.approx(51.25)
    by_entry = {row['entry']: row for row in rows}
    assert by_entry[7]['pions_theta'] == pytest.approx([75.])
    for entry, count in ((8, 1), (9, 2)):
        assert len(by_entry[entry]['protons']) == 1
        assert by_entry[entry]['pions_theta'] == []
        assert len(by_entry[entry]['fcharged_theta']) == count
    empty = rows[5]
    for name in ('gammas', 'protons', 'neutrons', 'pions_theta', 'gamma_theta',
                 'fcharged_theta', 'Index_trf', 'Iass_trf'):
        assert empty[name] == []
    with uproot.open(common_pid['h80']) as source:
        assert source['preanalysis_skipped_no_tagger'].member('fVal') == 1
    selected = _read_pid(common_pid['h85'], 'h85')
    # Both central 13/14 and forward masks 6/7 pass the actual common selector.
    # Partial BGO shape (entry 2) is irrelevant to these measured PID inputs.
    assert [row['entry'] for row in selected] == [1, 2, 3, 4]
    assert selected == [row for row in rows if row['entry'] in (1, 2, 3, 4)]
    with uproot.open(common_pid['h80']) as before, uproot.open(common_pid['h85']) as after:
        assert after['preanalysis_provenance'].member('fTitle') == before['preanalysis_provenance'].member('fTitle')
