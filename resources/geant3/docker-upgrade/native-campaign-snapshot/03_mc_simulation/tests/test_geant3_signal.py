"""Signal pilot guards: complete denominators and physical truth invariants."""

import numpy as np
import pytest
from mc_simulation.geant3_signal import read_truth, signal_card


def _threshold_event():
    masses = np.array([0.54745, 0.13496, 0.93821])
    total = masses.sum()
    energy = (total**2 - masses[-1] ** 2) / (2 * masses[-1])
    beta = energy / (energy + masses[-1])
    gamma = 1 / np.sqrt(1 - beta**2)
    particles = np.zeros((3, 4))
    particles[:, 2] = gamma * beta * masses
    particles[:, 3] = gamma * masses
    return np.r_[3629, 1, 38, 3, energy, 0, 0, 0, particles.ravel()]


def _write(tmp_path, row, terminator=True):
    path = tmp_path / "truth.dat"
    path.write_text(" ".join(map(str, row)) + "\n" + ("-1\n" if terminator else ""))
    return path


def test_complete_truth_and_physics(tmp_path):
    data = read_truth(_write(tmp_path, _threshold_event()), expected_events=1)
    assert data.shape == (1, 20)


@pytest.mark.parametrize("column,value", [(1, 2), (2, 19), (7, 7), (8, 0.1), (0, 1)])
def test_reject_missing_identity_wrong_channel_vertex_or_momentum(
    tmp_path, column, value
):
    row = _threshold_event()
    row[column] = value
    with pytest.raises(ValueError):
        read_truth(_write(tmp_path, row), expected_events=1)


def test_reject_incomplete_generation(tmp_path):
    with pytest.raises(ValueError, match="terminator"):
        read_truth(_write(tmp_path, _threshold_event(), False))
    with pytest.raises(ValueError, match="count"):
        read_truth(_write(tmp_path, _threshold_event()), expected_events=2)


def test_card_enforces_signal_contract():
    card = signal_card(10000, 1.2, 310027)
    for line in [
        "TRIG 10000",
        "PROC 38",
        "TARG 1 4",
        "ETDK 1",
        "RUNG 3629 1",
        "RNDM 310027 310029",
    ]:
        assert line in card.splitlines()
    for kwargs in [
        {"events": 0},
        {"events": 2**24},
        {"energy": 0.8},
        {"energy": float("nan")},
        {"seed": 2},
        {"seed": 0},
    ]:
        with pytest.raises(ValueError):
            signal_card(**kwargs)


def test_uniform_energy_card_and_invalid_intervals():
    card = signal_card(10000, seed=310027, energy_range=(1.05, 1.4875))
    assert "EWIN 1.05 1.4875" in card.splitlines()
    assert "ENER 1.26875" in card.splitlines()
    assert "EWIN" not in signal_card()
    for bounds in [(1.2, 1.1), (0.9, 1.2), (1.1, 1.6), (1.1,), (1.1, np.nan)]:
        with pytest.raises(ValueError, match="energy_range"):
            signal_card(energy_range=bounds)


@pytest.mark.parametrize("failure", ["energy", "prean_count"])
def test_run_rejects_wrong_energy_or_prean_input_count(tmp_path, monkeypatch, failure):
    from types import SimpleNamespace

    from mc_simulation.geant3_signal import run_signal

    build = tmp_path / "build"
    for name in ("laggen", "lagdig", "prean"):
        (build / name).mkdir(parents=True)
        (build / name / name).write_text("binary")
    (build / "laggen/transport_probe").write_text("probe")
    out = tmp_path / "output"
    row = _threshold_event()
    requested = 1.2 if failure == "energy" else float(row[4]) + 1e-9

    def fake_run(*args, **kwargs):
        command = args[0]
        mounts = [
            part
            for part in command
            if isinstance(part, str) and "dst=/resources" in part
        ]
        assert mounts == [
            f"type=bind,src={out}/resource_snapshot,dst=/resources,readonly"
        ]
        assert (out / "resource_snapshot/run_signal_chain.sh").is_file()
        (out / "generated_signal.dat").write_text(" ".join(map(str, row)) + "\n-1\n")
        _write_decays(out / "generated_decays.dat", row)
        (out / "lagdig.log").write_text(
            "data21.base calib_3700.cal\nNUMBER OF EVENTS : 1\nEvents rejected by Tagging Condition = 0\nEvents rejected by Trigger Condition = 0\nEvents collected = 1\n"
        )
        (out / "prean.log").write_text(
            "OLD_CYL GRAAL_21 calib_3700.cal\nNormal Termination\nNumber of events in NTUPLE: "
            + ("0" if failure == "prean_count" else "1")
            + "\n"
        )
        (out / "out_prean").mkdir()
        (out / "out_prean/signal.pol").write_bytes(b"x" * 1000)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("mc_simulation.geant3_signal.subprocess.run", fake_run)
    with pytest.raises(ValueError, match="energy|PREAN input"):
        run_signal(build, out, events=1, energy=requested)


def _write_decays(path, row):
    rows = []
    for index, mother in enumerate(row[8:].reshape(3, 4)[:2], 1):
        # Collinear lab daughters from opposing longitudinal rest photons.
        first = np.array(
            [0.0, 0.0, (mother[3] + mother[2]) / 2, (mother[3] + mother[2]) / 2]
        )
        second = mother - first
        rows.append(np.r_[row[0:2], index, first, second])
    path.write_text("\n".join(" ".join(map(str, r)) for r in rows) + "\n-1\n")
    return rows


def test_prompt_photon_decay_truth_and_corruption(tmp_path):
    from mc_simulation.geant3_signal import read_decay_truth

    row = _threshold_event()
    path = tmp_path / "decays.dat"
    rows = _write_decays(path, row)
    result = read_decay_truth(path, row[None])
    assert result["decays"] == 2
    assert result["max_photon_mass_squared_gev2"] < 1e-12
    rows[0][3] += 0.01
    path.write_text("\n".join(" ".join(map(str, r)) for r in rows) + "\n-1\n")
    with pytest.raises(ValueError, match="four-momentum"):
        read_decay_truth(path, row[None])


def test_failed_transport_probe_records_failure_before_generation(
    tmp_path, monkeypatch
):
    import json
    from types import SimpleNamespace

    from mc_simulation.geant3_signal import run_signal

    build = tmp_path / "build"
    for relative in (
        "laggen/laggen",
        "laggen/transport_probe",
        "lagdig/lagdig",
        "prean/prean",
    ):
        path = build / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("binary")
    output = tmp_path / "failed"

    def failed_probe(*args, **kwargs):
        (output / "transport_probe.log").write_text("TRANSPORT PROBE 1: photon lost\n")
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr("mc_simulation.geant3_signal.subprocess.run", failed_probe)
    with pytest.raises(RuntimeError, match="transport invariant"):
        run_signal(build, output, events=100)
    record = json.loads((output / "run.json").read_text())
    assert record["status"] == "failed"
    assert record["exit_code"] == 1
    assert not (output / "generated_signal.dat").exists()
